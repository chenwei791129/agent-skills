#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14"
# dependencies = ["requests>=2.31", "python-dotenv>=1.0"]
# ///
"""Query mail (待領/已領信件) from the Newcity community property app.

Reproduces the app's login -> resolve company -> resolve resident -> query
flow against the NewcityWebApi, then prints any mail rows for the requested
status (uncollected by default).

Credentials are resolved with layered precedence (highest first):
  1. a .env in the current working directory
  2. a .env next to this script (the skill directory)
  3. the process environment (NEWCITY_USERID / NEWCITY_PASSWORD / NEWCITY_BEARER)
See .env.example for the variable names. Run with: uv run query_mail.py
"""

import argparse
import base64
import os
import secrets
import signal
import sys
from pathlib import Path

import requests
from dotenv import dotenv_values

BASE_URL = "https://www.itlife.com.tw/NewcityWebApi/api"

# Program id for the "未領信件" (uncollected mail) module, and its mail-status
# code: 1 = uncollected, 2 = collected (per SY0_CODED / LET_ST).
PRO_ID = "APP_PA004"
STATUS_UNCOLLECTED = "1"

# Human-readable names for the LET_STATUS codes.
STATUS_NAMES = {"1": "未領", "2": "已領"}

# Length (in bytes) of the device/session token the app sends as the `Bearer`
# header. Captured tokens decode to a 160-byte opaque blob (base64 -> 216 chars
# ending in "=="), consistent with a client-generated random device identifier.
BEARER_BYTES = 160

USER_AGENT = "Dalvik/2.1.0 (Linux; U; Android 16; SM-S9310 Build/BP4A.251205.006)"


def generate_bearer() -> str:
    """Generate a fresh Bearer token in the app's format.

    The app sends the same opaque token as the `Bearer` header on every
    request, including login, and the server binds the login state to whatever
    token is presented (login returns no token and the value never rotates).
    A freshly generated random token therefore works just like a captured one,
    so we avoid hardcoding any real device's token. Overridable via
    NEWCITY_BEARER for the case where the backend later starts validating it.
    """
    return base64.b64encode(secrets.token_bytes(BEARER_BYTES)).decode("ascii")


def load_config() -> dict[str, str | None]:
    """Resolve credentials with layered precedence.

    Lookup order (highest first): a .env in the current working directory, then
    a .env next to this script (the skill directory), then the process
    environment. This lets the skill stay self-contained without baking in any
    real secret — a user can keep per-project credentials, fall back to a
    personal .env stored beside the skill, or inject values via the environment
    (e.g. in CI). dotenv_values reads the files without mutating os.environ, so
    the precedence stays explicit instead of depending on load order.
    """
    cwd_env = dotenv_values(Path.cwd() / ".env")
    skill_env = dotenv_values(Path(__file__).resolve().parent / ".env")

    def resolve(key: str) -> str | None:
        return cwd_env.get(key) or skill_env.get(key) or os.getenv(key)

    return {
        "userid": resolve("NEWCITY_USERID"),
        "password": resolve("NEWCITY_PASSWORD"),
        "bearer": resolve("NEWCITY_BEARER"),
    }


class ApiError(RuntimeError):
    """Raised when the API returns a non-success response."""


class NewcityClient:
    def __init__(self, bearer: str):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Bearer": bearer,
                "ProID": PRO_ID,
                "User-Agent": USER_AGENT,
                "Accept-Encoding": "gzip",
            }
        )

    def _post(self, path: str, payload: dict) -> dict:
        resp = self.session.post(f"{BASE_URL}/{path}", json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _get(self, path: str, params: dict | None = None) -> dict:
        resp = self.session.get(f"{BASE_URL}/{path}", params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def login(self, userid: str, password: str) -> None:
        data = self._post(
            "User/Login", {"userid": userid, "password": password, "tc": "false"}
        )
        if not data.get("success"):
            raise ApiError("Login failed — check NEWCITY_USERID / NEWCITY_PASSWORD")

    def resolve_company(self, userid: str) -> tuple[str, str]:
        """Return (NO_COMP, community name) for the user's first community."""
        data = self._get("User/Companys", {"userid": userid, "isAllUser": "False"})
        results = data.get("result") or []
        if not data.get("success") or not results:
            raise ApiError("No community found for this account")
        first = results[0]
        return first["NO_COMP"], first.get("NM_CMPS", "")

    def resolve_resident(self, userid: str, no_comp: str) -> tuple[str, str]:
        """Return (NO_CUST, resident name) by exchanging userid+company."""
        data = self._get("User/Token", {"userid": userid, "comp": no_comp})
        result = data.get("result") or {}
        if not data.get("success") or not result.get("NO_CUST"):
            raise ApiError("Failed to resolve resident id (NO_CUST)")
        return result["NO_CUST"], result.get("NM_CUSTS", "")

    def query_mail(
        self, no_comp: str, no_cust: str, status: str, size: int = 50
    ) -> list[dict]:
        """Fetch all mail rows for the given status, following pagination."""
        rows: list[dict] = []
        page = 1
        while True:
            data = self._post(
                "App/Query",
                {
                    "proid": PRO_ID,
                    "pageid": "Head",
                    "RequestData": {
                        "NO_CUST": no_cust,
                        "LET_STATUS": status,
                        "NO_COMP": no_comp,
                    },
                    "size": size,
                    "page": page,
                },
            )
            if not data.get("success"):
                raise ApiError("Mail query failed")
            batch = data.get("result") or []
            rows.extend(batch)
            if len(batch) < size:
                break
            page += 1
        return rows


# Friendly labels for the known ST2_POST fields (see GetProgramSettings schema).
FIELD_LABELS = [
    ("DT_IN", "收件時間"),
    ("NM_CUST", "收件人"),
    ("CD_POST", "信件類別"),
    ("GN_UNIT", "寄件單位"),
    ("NO_POST", "郵件序號"),
    ("LET_BARCODE", "信件條碼"),
]


def print_mail(
    rows: list[dict], community: str, resident: str, status_name: str
) -> None:
    header = f"社區：{community}    住戶：{resident}"
    print(header)
    print("=" * max(len(header), 40))
    if not rows:
        print(f"目前沒有{status_name}信件 ✅")
        return

    print(f"共有 {len(rows)} 件{status_name}信件：\n")
    for i, row in enumerate(rows, 1):
        print(f"[{i}]")
        shown = set()
        for key, label in FIELD_LABELS:
            if key in row and row[key] not in (None, ""):
                print(f"    {label}: {row[key]}")
                shown.add(key)
        # Surface any remaining fields we did not explicitly map.
        for key, value in row.items():
            if key not in shown and value not in (None, ""):
                print(f"    {key}: {value}")
        print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="查詢社區未領信件")
    parser.add_argument(
        "--status",
        default=STATUS_UNCOLLECTED,
        help="信件狀態：1=未領（預設），2=已領",
    )
    parser.add_argument("--page-size", type=int, default=50, help="每頁筆數（預設 50）")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config()

    userid = config["userid"]
    password = config["password"]
    if not userid or not password:
        print(
            "錯誤：找不到 NEWCITY_USERID 與 NEWCITY_PASSWORD。"
            "請在執行目錄或 skill 目錄放一份 .env（參考 .env.example），"
            "或設定對應環境變數。",
            file=sys.stderr,
        )
        sys.exit(1)

    bearer = config["bearer"] or generate_bearer()
    client = NewcityClient(bearer)

    try:
        client.login(userid, password)
        no_comp, community = client.resolve_company(userid)
        no_cust, resident = client.resolve_resident(userid, no_comp)
        rows = client.query_mail(no_comp, no_cust, args.status, args.page_size)
    except (ApiError, requests.RequestException) as exc:
        print(f"查詢失敗：{exc}", file=sys.stderr)
        sys.exit(2)

    status_name = STATUS_NAMES.get(args.status, "")
    print_mail(rows, community, resident, status_name)


def _handle_sigterm(signum, frame):
    sys.exit(128 + signum)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _handle_sigterm)
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
