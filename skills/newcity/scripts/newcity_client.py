"""Shared client for the Newcity community property app (NewcityWebApi).

This module is imported by newcity.py (the uv entry point); it is not run
directly, so it declares no PEP 723 metadata. Its dependencies (requests,
python-dotenv) are installed into the same environment by newcity.py's inline
metadata when run via `uv run`.

It reproduces the app's login -> resolve company -> resolve resident flow and
exposes a generic App/Query helper. Each feature module (mail, points, ...) has
its own ProID and its own required RequestData fields, so callers build the
RequestData and the client just runs the paginated query.

Credentials are resolved with layered precedence (highest first):
  1. a .env in the current working directory
  2. a .env at the skill root (the parent of this scripts/ directory)
  3. the process environment (NEWCITY_USERID / NEWCITY_PASSWORD / NEWCITY_BEARER)
See .env.example for the variable names.
"""

import base64
import os
import secrets
from pathlib import Path

import requests
from dotenv import dotenv_values

BASE_URL = "https://www.itlife.com.tw/NewcityWebApi/api"

# Length (in bytes) of the device/session token the app sends as the `Bearer`
# header. Captured tokens decode to a 160-byte opaque blob (base64 -> 216 chars
# ending in "=="), consistent with a client-generated random device identifier.
BEARER_BYTES = 160

USER_AGENT = "Dalvik/2.1.0 (Linux; U; Android 16; SM-S9310 Build/BP4A.251205.006)"

# Skill root holds the .env / .env.example; this module lives in scripts/.
SKILL_ROOT = Path(__file__).resolve().parent.parent


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
    a .env at the skill root (the parent of this scripts/ directory), then the
    process environment. This keeps the skill self-contained without baking in
    any real secret. dotenv_values reads the files without mutating os.environ,
    so the precedence stays explicit instead of depending on load order.
    """
    cwd_env = dotenv_values(Path.cwd() / ".env")
    skill_env = dotenv_values(SKILL_ROOT / ".env")

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
    def __init__(self, bearer: str, pro_id: str):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Bearer": bearer,
                "ProID": pro_id,
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

    def resolve_resident(self, userid: str, no_comp: str) -> dict[str, str]:
        """Return the user's full identity in the community by exchanging userid+company.

        Different feature modules key their queries on different identity
        fields: mail (APP_PA004) only needs NO_CUST, but points (APP_PD010)
        requires NO_CUST + NO_HOUSE + NO_ARCH + NO_BUILD all together — drop any
        and the query returns zero rows. The server's GetDefaultValues does not
        resolve these for the points module, so the client must supply them.
        We therefore return the whole identity and let each caller pick.
        """
        data = self._get("User/Token", {"userid": userid, "comp": no_comp})
        result = data.get("result") or {}
        if not data.get("success") or not result.get("NO_CUST"):
            raise ApiError("Failed to resolve resident id (NO_CUST)")
        return {
            "NO_COMP": result.get("NO_COMP", no_comp),
            "NO_CUST": result["NO_CUST"],
            "NM_CUSTS": result.get("NM_CUSTS", ""),
            "NO_HOUSE": result.get("NO_HOUSE", ""),
            "NO_ARCH": result.get("NO_ARCH", ""),
            "NO_BUILD": result.get("NO_BUILD", ""),
        }

    def query(
        self, proid: str, pageid: str, request_data: dict, size: int = 50
    ) -> list[dict]:
        """Fetch all rows for a module's App/Query, following pagination.

        Generic over the metadata-driven backend: the caller supplies the
        module's ProID, the page id, and the RequestData filter; the server
        builds the SQL from that ProID's schema and returns the rows.
        """
        rows: list[dict] = []
        page = 1
        while True:
            data = self._post(
                "App/Query",
                {
                    "proid": proid,
                    "pageid": pageid,
                    "RequestData": request_data,
                    "size": size,
                    "page": page,
                },
            )
            if not data.get("success"):
                raise ApiError(f"Query failed for {proid}/{pageid}")
            batch = data.get("result") or []
            rows.extend(batch)
            if len(batch) < size:
                break
            page += 1
        return rows
