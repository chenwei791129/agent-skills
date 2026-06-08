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
import html
import re
import signal
import sys
from pathlib import Path

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

# --- announcements (最新公告) module ------------------------------------------
# Program id for the announcements module (table CO1_PU). The query requires the
# YN_APP read-status filter (IsAllowBlank=False): A=全部, N=未讀, Y=已讀 — omit it
# and the backend returns zero rows. Community-scoped, so it needs the info
# Bearer adopted in resolve_resident.
ANN_PRO_ID = "APP_PA006"
ANN_PAGE = "Head"
ANN_STATUS_CODES = {"unread": "N", "all": "A", "read": "Y"}
ANN_STATUS_NAMES = {"unread": "未讀", "all": "全部", "read": "已讀"}


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


def html_to_text(value: str) -> str:
    """Render an HtmlView field (GN_TEXT1) as plain text for the terminal.

    Announcement bodies are stored as HTML; convert <br>/<p>/<div> to newlines,
    drop the remaining tags, unescape entities, and collapse blank-line runs.
    """
    if not value:
        return ""
    text = re.sub(r"(?i)<\s*br\s*/?>", "\n", value)
    text = re.sub(r"(?i)</\s*(p|div|li|tr|h[1-6])\s*>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


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


def print_announcements(
    rows: list[dict], community: str, resident: str, status_name: str
) -> None:
    _header(community, resident)
    if not rows:
        print(f"目前沒有{status_name}公告 ✅")
        return

    print(f"共有 {len(rows)} 則{status_name}公告：\n")
    for row in rows:
        unread = "●" if row.get("YN_APP") == "未讀" else " "
        date = row.get("DT_TRN", "")
        category = row.get("SC_ANTP_text", "")
        title = row.get("GN_TITLE", "")
        no_pu = row.get("NO_PU", "")
        print(f"{unread} {date}  [{category}]  {title}  ({no_pu})")


ANN_TEXT2_PLACEHOLDER = "請在此輸入內容..."


def print_announcement_detail(
    row: dict, attachments: list[dict], community: str, resident: str
) -> None:
    _header(community, resident)
    print(f"主旨：{row.get('GN_TITLE', '')}")
    print(
        f"日期：{row.get('DT_TRN', '')}    類別：{row.get('SC_ANTP_text', '')}"
        f"    讀取狀態：{row.get('YN_APP', '')}"
    )
    print(f"公告編號：{row.get('NO_PU', '')}")
    print("-" * 40)

    body = html_to_text(row.get("GN_TEXT1", ""))
    text2 = (row.get("GN_TEXT2") or "").strip()
    if text2 and text2 != ANN_TEXT2_PLACEHOLDER:
        body = f"{body}\n\n{html_to_text(text2)}".strip()
    print(body or "（無內文）")

    if attachments:
        print("\n附件：")
        for att in attachments:
            saved = f"  → 已存：{att['saved_path']}" if att.get("saved_path") else ""
            print(f"  - {att['filename']}\n    {att['url']}{saved}")


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


def run_announcements(
    client: NewcityClient, identity: dict, args: argparse.Namespace
) -> None:
    rows = client.query(
        ANN_PRO_ID,
        ANN_PAGE,
        {"NO_COMP": identity["NO_COMP"], "YN_APP": ANN_STATUS_CODES[args.status]},
        args.page_size,
    )
    if args.limit is not None:
        rows = rows[: args.limit]
    print_announcements(
        rows, args.community, identity["NM_CUSTS"], ANN_STATUS_NAMES[args.status]
    )


ANN_FILE_FIELDS = ("GN_FILE1", "GN_FILE2", "GN_FILE3", "GN_FILE4")
# Row key fields the app sends to App/DataClicked to mark a single announcement
# read (mirrors the captured request body's RequestData).
ANN_CLICK_FIELDS = ("NO_COMP", "NO_PU", "DT_B")


def run_announcement(
    client: NewcityClient, identity: dict, args: argparse.Namespace
) -> None:
    # App/Query cannot filter by NO_PU, so fetch the full list (the list rows
    # already carry the body and attachment GUIDs) and match client-side.
    rows = client.query(
        ANN_PRO_ID,
        ANN_PAGE,
        {"NO_COMP": identity["NO_COMP"], "YN_APP": "A"},
        args.page_size,
    )
    row = next((r for r in rows if r.get("NO_PU") == args.no_pu), None)
    if row is None:
        print(f"查無公告編號 {args.no_pu}", file=sys.stderr)
        sys.exit(2)

    dest = Path(args.save) if args.save else None
    attachments = [
        client.fetch_attachment(row[field], dest)
        for field in ANN_FILE_FIELDS
        if row.get(field)
    ]
    print_announcement_detail(row, attachments, args.community, identity["NM_CUSTS"])

    if args.mark_read:
        was_unread = row.get("YN_APP") == "未讀"
        click_data = {"NO_COMP": identity["NO_COMP"]}
        click_data.update(
            {f: row.get(f, "") for f in ANN_CLICK_FIELDS if f != "NO_COMP"}
        )
        client.data_clicked(ANN_PAGE, click_data)
        print("\n（已標記為已讀）" if was_unread else "\n（本則原本就是已讀）")


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

    ann = sub.add_parser("announcements", help="查詢公告清單（預設未讀）")
    ann.add_argument(
        "--status",
        choices=("unread", "all", "read"),
        default="unread",
        help="公告狀態：unread=未讀（預設），all=全部，read=已讀",
    )
    ann.add_argument(
        "--limit", type=int, default=None, help="只顯示前 N 則（預設全部）"
    )
    ann.add_argument("--page-size", type=int, default=50, help="每頁筆數（預設 50）")
    ann.set_defaults(handler=run_announcements, pro_id=ANN_PRO_ID)

    one = sub.add_parser("announcement", help="讀取單則公告內文與附件")
    one.add_argument("no_pu", help="公告編號 NO_PU（從 announcements 清單取得）")
    one.add_argument("--save", default=None, help="把附件下載存到指定目錄")
    one.add_argument(
        "--mark-read",
        action="store_true",
        help="讀完順便把這則標記為已讀（預設不標記，純讀取）",
    )
    one.add_argument("--page-size", type=int, default=50, help="每頁筆數（預設 50）")
    one.set_defaults(handler=run_announcement, pro_id=ANN_PRO_ID)

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
