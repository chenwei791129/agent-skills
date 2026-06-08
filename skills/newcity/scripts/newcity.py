#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14"
# dependencies = ["requests>=2.31", "python-dotenv>=1.0"]
# ///
"""Query the Newcity community property app (itlife.com.tw / NewcityWebApi).

A subcommand CLI over a shared login flow:
  newcity.py mail   [--status 1|2]   待領/已領信件與包裹
  newcity.py points                  社區剩餘點數總和與明細

The login -> resolve company -> resolve resident chain lives in
newcity_client.py; each subcommand only builds its own RequestData and formats
the rows. Run with: uv run newcity.py <subcommand>
"""

import argparse
import signal
import sys

import requests

from newcity_client import ApiError, NewcityClient, generate_bearer, load_config

# --- mail (信件通知) module ---------------------------------------------------
# Program id for the mail module and its status codes (per SY0_CODED / LET_ST).
MAIL_PRO_ID = "APP_PA004"
MAIL_STATUS_UNCOLLECTED = "1"
MAIL_STATUS_NAMES = {"1": "未領", "2": "已領"}

# Friendly labels for the known ST2_POST mail fields.
MAIL_FIELD_LABELS = [
    ("DT_IN", "收件時間"),
    ("NM_CUST", "收件人"),
    ("CD_POST", "信件類別"),
    ("GN_UNIT", "寄件單位"),
    ("NO_POST", "郵件序號"),
    ("LET_BARCODE", "信件條碼"),
]

# --- points (點數查詢) module -------------------------------------------------
# Program id for the points module. Its 贈點有效明細 (Body page) carries the
# remaining-points field QT_FREEU. The query requires the full resident identity
# (NO_COMP/NO_CUST/NO_HOUSE/NO_ARCH/NO_BUILD) — dropping any one returns 0 rows.
POINTS_PRO_ID = "APP_PD010"
POINTS_PAGE = "Body"
POINTS_REMAINING_FIELD = "QT_FREEU"
POINTS_KEY_FIELDS = ("NO_COMP", "NO_CUST", "NO_HOUSE", "NO_ARCH", "NO_BUILD")

# Friendly labels for the known ST3_PADD points-detail fields. SC_CPTY resolves
# to SC_CPTY_text on the server side; print_points prefers the *_text companion.
POINTS_FIELD_LABELS = [
    ("SC_CPTY", "點數類別"),
    ("QT_FREE", "單筆點數"),
    ("QT_FREEU", "剩餘點數"),
    ("NO_PO", "點數單號"),
]


def _header(community: str, resident: str) -> None:
    header = f"社區：{community}    住戶：{resident}"
    print(header)
    print("=" * max(len(header), 40))


def _label_value(row: dict, key: str) -> object:
    """Prefer the server-resolved *_text companion when present."""
    text = row.get(f"{key}_text")
    return text if text not in (None, "") else row.get(key)


def print_mail(
    rows: list[dict], community: str, resident: str, status_name: str
) -> None:
    _header(community, resident)
    if not rows:
        print(f"目前沒有{status_name}信件 ✅")
        return

    print(f"共有 {len(rows)} 件{status_name}信件：\n")
    for i, row in enumerate(rows, 1):
        print(f"[{i}]")
        shown = set()
        for key, label in MAIL_FIELD_LABELS:
            if key in row and row[key] not in (None, ""):
                print(f"    {label}: {row[key]}")
                shown.add(key)
        # Surface any remaining fields we did not explicitly map.
        for key, value in row.items():
            if key not in shown and value not in (None, ""):
                print(f"    {key}: {value}")
        print()


def _to_number(value: object) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0


def _fmt_points(value: float) -> str:
    """Render points without a trailing .0 when they are whole numbers."""
    return str(int(value)) if value == int(value) else str(value)


def print_points(rows: list[dict], community: str, resident: str) -> None:
    _header(community, resident)

    total = sum(_to_number(row.get(POINTS_REMAINING_FIELD)) for row in rows)
    print(f"目前剩餘點數總和：{_fmt_points(total)} 點\n")

    if not rows:
        print("目前沒有點數明細 ✅（剩餘 0 點）")
        return

    print(f"共有 {len(rows)} 筆贈點明細：\n")
    for i, row in enumerate(rows, 1):
        print(f"[{i}]")
        # Seed with the identity keys we supplied ourselves so the defensive
        # dump below surfaces only genuinely unexpected fields, not our filters.
        shown = set(POINTS_KEY_FIELDS)
        for key, label in POINTS_FIELD_LABELS:
            value = _label_value(row, key)
            if value not in (None, ""):
                print(f"    {label}: {value}")
                shown.update({key, f"{key}_text"})
        # Validity window: 有效起日 ~ 有效迄日.
        dt_b, dt_e = row.get("DT_B"), row.get("DT_E")
        if dt_b or dt_e:
            print(f"    有效期間: {dt_b or '—'} ~ {dt_e or '—'}")
            shown.update({"DT_B", "DT_E"})
        # Surface any remaining fields we did not explicitly map.
        for key, value in row.items():
            if key not in shown and value not in (None, ""):
                print(f"    {key}: {value}")
        print()


def run_mail(client: NewcityClient, identity: dict, args: argparse.Namespace) -> None:
    rows = client.query(
        MAIL_PRO_ID,
        "Head",
        {
            "NO_CUST": identity["NO_CUST"],
            "LET_STATUS": args.status,
            "NO_COMP": identity["NO_COMP"],
        },
        args.page_size,
    )
    status_name = MAIL_STATUS_NAMES.get(args.status, "")
    print_mail(rows, args.community, identity["NM_CUSTS"], status_name)


def run_points(client: NewcityClient, identity: dict, args: argparse.Namespace) -> None:
    rows = client.query(
        POINTS_PRO_ID,
        POINTS_PAGE,
        {key: identity[key] for key in POINTS_KEY_FIELDS},
        args.page_size,
    )
    print_points(rows, args.community, identity["NM_CUSTS"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="查詢 Newcity 社區 app")
    sub = parser.add_subparsers(dest="command", required=True)

    mail = sub.add_parser("mail", help="查詢待領/已領信件與包裹")
    mail.add_argument(
        "--status",
        default=MAIL_STATUS_UNCOLLECTED,
        help="信件狀態：1=未領（預設），2=已領",
    )
    mail.add_argument("--page-size", type=int, default=50, help="每頁筆數（預設 50）")
    mail.set_defaults(handler=run_mail, pro_id=MAIL_PRO_ID)

    points = sub.add_parser("points", help="查詢社區剩餘點數總和與明細")
    points.add_argument("--page-size", type=int, default=50, help="每頁筆數（預設 50）")
    points.set_defaults(handler=run_points, pro_id=POINTS_PRO_ID)

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
    client = NewcityClient(bearer, args.pro_id)

    try:
        client.login(userid, password)
        no_comp, community = client.resolve_company(userid)
        identity = client.resolve_resident(userid, no_comp)
    except (ApiError, requests.RequestException) as exc:
        print(f"查詢失敗：{exc}", file=sys.stderr)
        sys.exit(2)

    args.community = community
    try:
        args.handler(client, identity, args)
    except (ApiError, requests.RequestException) as exc:
        print(f"查詢失敗：{exc}", file=sys.stderr)
        sys.exit(2)


def _handle_sigterm(signum, frame):
    sys.exit(128 + signum)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _handle_sigterm)
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
