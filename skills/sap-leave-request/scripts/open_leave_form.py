#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["python-dotenv>=1.0"]
# ///
"""Log into SAP SuccessFactors and open the 要求休假 (request-leave) form.

This is the deterministic prelude for the `sap-leave-request` skill. The
login + open-form sequence is identical on every run, so it lives here instead
of being re-derived by the agent each time: fewer tokens, one audited place for
credential handling, and behavior that was verified once and stays put.

The script drives the `agent-browser` CLI via subprocess. When it finishes the
browser is left sitting on the open leave form, and the agent takes over to
choose the leave type, fill the dates, validate, and submit.

Usage:
    uv run open_leave_form.py [--env PATH]

Configuration and credentials come from a .env file (default: ./.env). The SAP
home URL is org-specific (datacenter host + company parameter), so it lives in
.env rather than the script:

    SAP_USERNAME='DOMAIN\\your.account'   # single-quote: keep the domain backslash
    SAP_PASSWORD='your-password'
    SAP_URL='https://<your-sf-host>/sf/home?bplte_company=<your-company>'

Exit codes: 0 ready, 1 failure, 130 SIGINT, 143 SIGTERM.
"""

from __future__ import annotations

import argparse
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values


def home_marker(url: str) -> str:
    """Host + path of the SAP home URL, used to detect an existing session."""
    parsed = urlparse(url)
    return f"{parsed.netloc}{parsed.path}"


def _handle_sigterm(signum, frame):
    sys.exit(128 + signum)


def ab(*args: str, check: bool = False) -> str:
    """Run an agent-browser command and return its stdout (stripped)."""
    result = subprocess.run(
        ["agent-browser", *args],
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        fail(f"agent-browser {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def fail(message: str) -> "None":
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def snapshot() -> str:
    return ab("snapshot", "-i")


def find_ref(role: str, name: str, snap: str | None = None) -> str | None:
    """Return the @ref for an element matching `role "name"` in the snapshot.

    Refs are assigned fresh on every snapshot and only stay valid while the page
    is unchanged, so callers pass a snapshot they just took.
    """
    snap = snap if snap is not None else snapshot()
    # The ref may carry other attributes first, e.g. `[expanded=false, ref=e57]`,
    # so match `ref=` anywhere on the element's line rather than right after `[`.
    pattern = re.compile(rf'{re.escape(role)} "{re.escape(name)}"[^\n]*?ref=(e\d+)')
    match = pattern.search(snap)
    return f"@{match.group(1)}" if match else None


def center_of(ref: str) -> tuple[int, int]:
    """Parse `agent-browser get box` output into a click point at the center."""
    box = ab("get", "box", ref, check=True)
    coords = {
        key: float(value)
        for key, value in re.findall(r"(x|y|width|height):\s*([\d.]+)", box)
    }
    if len(coords) < 4:
        fail(f"could not read the box coordinates of {ref}: {box}")
    return (
        int(coords["x"] + coords["width"] / 2),
        int(coords["y"] + coords["height"] / 2),
    )


def click_at(x: int, y: int) -> None:
    # The 要求休假 quick-action button is covered by a UI5 icon, so a plain
    # `click @ref` reports the covering element instead. A raw mouse click at
    # the button's center lands correctly.
    ab("mouse", "move", str(x), str(y))
    ab("mouse", "down")
    ab("mouse", "up")


def load_credentials(env_path: Path) -> tuple[str, str, str]:
    if not env_path.is_file():
        fail(f".env not found: {env_path}")
    values = dotenv_values(env_path)
    username = values.get("SAP_USERNAME")
    password = values.get("SAP_PASSWORD")
    url = values.get("SAP_URL")
    if not username:
        fail("SAP_USERNAME is not set")
    if not password:
        fail("SAP_PASSWORD is not set")
    if not url:
        fail("SAP_URL is not set (e.g. https://<host>/sf/home?bplte_company=<company>)")
    return username, password, url


def ensure_logged_in(username: str, password: str, url: str) -> None:
    marker = home_marker(url)
    if marker in ab("get", "url"):
        return  # Already on the SuccessFactors home page.

    ab("open", url, "--headed")
    time.sleep(4)
    ab("wait", "--load", "networkidle")

    # SAP may redirect to the org's SSO / ADFS page. Fill credentials if it's up.
    snap = snapshot()
    user_ref = find_ref("textbox", "使用者帳戶", snap)
    if user_ref:
        pass_ref = find_ref("textbox", "密碼", snap)
        login_ref = find_ref("button", "登入", snap)
        if not pass_ref or not login_ref:
            fail(
                "login page is missing the password or login field; it may have changed"
            )
        ab("fill", user_ref, username, check=True)
        ab("fill", pass_ref, password, check=True)
        ab("click", login_ref, check=True)
        time.sleep(7)
        ab("wait", "--load", "networkidle")

    if marker not in ab("get", "url"):
        fail(
            "still not on the home page after login. Common cause: the .env"
            " username was not single-quoted, so the domain backslash was eaten."
            " Check the SAP_USERNAME='DOMAIN\\\\your.account' format."
        )


def open_leave_form() -> None:
    button = find_ref("button", "要求休假")
    if not button:
        fail("could not find the 要求休假 (request-leave) button on the home page")
    click_at(*center_of(button))
    time.sleep(3)
    ab("wait", "--load", "networkidle")

    if not find_ref("combobox", "時間類型"):
        fail("the leave form did not appear after the click (no 時間類型 field found)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Open the SAP SuccessFactors leave-request form"
    )
    parser.add_argument(
        "--env",
        type=Path,
        default=Path(".env"),
        help="path to the .env holding SAP_USERNAME / SAP_PASSWORD / SAP_URL"
        " (default: ./.env)",
    )
    args = parser.parse_args()

    username, password, url = load_credentials(args.env)
    ensure_logged_in(username, password, url)
    open_leave_form()

    print(
        "READY: logged in and the leave form is open. The agent takes over to"
        " pick the leave type, fill the dates, and submit."
    )


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _handle_sigterm)
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
