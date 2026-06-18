#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["python-dotenv>=1.0"]
# ///
"""Log into reimburse.digital and open the new reimbursement (請款) form.

This is the deterministic prelude for the `reimburse-request` skill. The
login + open-form sequence is identical on every run, so it lives here instead
of being re-derived by the agent each time: fewer tokens, one audited place for
credential handling, and behavior that was verified once and stays put.

The script drives the `agent-browser` CLI via subprocess. When it finishes the
browser is left sitting on the open "Add Benefit" form (the 請款 entry under
Benefit/Others), and the agent takes over to choose the benefit type/category,
fill the date/amount/remarks, attach the receipt, validate, and submit.

Usage:
    uv run open_reimburse_form.py [--env PATH]

Configuration and credentials come from a .env file (default: ./.env):

    ORGANISATION_ID='your-org-id'
    REIMBURSE_USERNAME='your.account'     # single-quote to keep any domain backslash
    REIMBURSE_PASSWORD='your-password'
    # REIMBURSE_URL='https://app.reimburse.digital/'   # optional override

Login flow:
1. Open the app URL -> reimburse.digital login page with textbox
   "Enter Your Organisation ID" and button "Continue" (product UI, same for
   every org).
2. Fill the org id, click Continue -> reimburse.digital redirects to the
   organisation's OWN SSO / IdP. That page VARIES per org (different IdP,
   labels, language, possibly MFA). This script fills the first
   username/password/login it recognizes from a set of common field labels; if
   your org's SSO differs, adjust the candidate selectors in ensure_logged_in()
   or complete the SSO step manually.
3. After login -> lands back on the app home.
4. Click button "Add New" -> a dialog with menuitems "Travel/Claims",
   "Request", "Receipt", "Benefit/Others"; 請款 is "Benefit/Others", which
   opens /add-benefit-claim/benefit with combobox "* Benefit Type".

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

DEFAULT_URL = "https://app.reimburse.digital/"


def home_marker(url: str) -> str:
    """Host of the app URL, used to detect an already-authenticated session."""
    parsed = urlparse(url)
    return parsed.netloc


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
    is unchanged, so callers pass a snapshot they just took. `name` is matched as
    a substring so callers can pass a stable fragment (e.g. "Add New" matches the
    rendered "plus Add New").
    """
    snap = snap if snap is not None else snapshot()
    # The ref may carry other attributes first, e.g. `[expanded=false, ref=e57]`,
    # so match `ref=` anywhere on the element's line rather than right after `[`.
    pattern = re.compile(
        rf'{re.escape(role)} "[^"\n]*{re.escape(name)}[^"\n]*"[^\n]*?ref=(e\d+)'
    )
    match = pattern.search(snap)
    return f"@{match.group(1)}" if match else None


def load_credentials(env_path: Path) -> tuple[str, str, str, str]:
    if not env_path.is_file():
        fail(f".env not found: {env_path}")
    values = dotenv_values(env_path)
    org_id = values.get("ORGANISATION_ID")
    username = values.get("REIMBURSE_USERNAME")
    password = values.get("REIMBURSE_PASSWORD")
    url = values.get("REIMBURSE_URL") or DEFAULT_URL
    if not org_id:
        fail("ORGANISATION_ID is not set")
    if not username:
        fail("REIMBURSE_USERNAME is not set")
    if not password:
        fail("REIMBURSE_PASSWORD is not set")
    return org_id, username, password, url


# The credential / login fields on the organisation's SSO page vary per org
# (different IdP, labels, language). Try a set of common candidates in order.
SSO_USER_LABELS = ("使用者帳戶", "Username", "User name", "User ID", "Email", "帳號")
SSO_PASS_LABELS = ("密碼", "Password")
SSO_LOGIN_LABELS = ("登入", "Sign in", "Log in", "Login", "Sign In")


def first_ref(role: str, names: tuple[str, ...], snap: str) -> str | None:
    for name in names:
        ref = find_ref(role, name, snap)
        if ref:
            return ref
    return None


def authenticated(marker: str) -> bool:
    """True when the browser is on the app host and not on a login/SSO page."""
    current = ab("get", "url")
    return marker in current and "login" not in current and "auth" not in current


def ensure_logged_in(org_id: str, username: str, password: str, url: str) -> None:
    marker = home_marker(url)
    if authenticated(marker):
        return  # Already on an authenticated app page.

    ab("open", url, "--headed")
    time.sleep(4)
    ab("wait", "--load", "networkidle")

    # --- Step A: organisation code -----------------------------------------
    org_ref = find_ref("textbox", "Organisation")
    if org_ref:
        ab("fill", org_ref, org_id, check=True)
        continue_ref = find_ref("button", "Continue")
        if continue_ref:
            ab("click", continue_ref, check=True)
        else:
            ab("press", "Enter")
        time.sleep(5)
        ab("wait", "--load", "networkidle")

    # --- Step B: credentials on the organisation's own SSO / IdP page ------
    # This page is org-specific; try common username/password/login labels.
    snap = snapshot()
    user_ref = first_ref("textbox", SSO_USER_LABELS, snap)
    if user_ref:
        pass_ref = first_ref("textbox", SSO_PASS_LABELS, snap)
        login_ref = first_ref("button", SSO_LOGIN_LABELS, snap)
        if not pass_ref or not login_ref:
            fail(
                "found a username field but not the password/login button on the"
                " SSO page. Your organisation's SSO likely uses different labels —"
                " add them to SSO_*_LABELS in this script, or log in manually."
            )
        ab("fill", user_ref, username, check=True)
        ab("fill", pass_ref, password, check=True)
        ab("click", login_ref, check=True)
        time.sleep(7)
        ab("wait", "--load", "networkidle")

    if not authenticated(marker):
        fail(
            "still not authenticated after login. Common causes: a wrong"
            " ORGANISATION_ID, wrong credentials, an SSO page whose field labels"
            " this script doesn't recognize (extend SSO_*_LABELS), MFA, or a"
            " username that lost its DOMAIN\\ backslash because .env was not"
            " single-quoted."
        )


def open_reimburse_form() -> None:
    # 請款 lives under Add New -> Benefit/Others.
    add_new = find_ref("button", "Add New")
    if not add_new:
        fail("could not find the 'Add New' button on the home page")
    ab("click", add_new, check=True)
    time.sleep(1)

    benefit = find_ref("menuitem", "Benefit/Others")
    if not benefit:
        fail(
            "the Add New dialog did not show 'Benefit/Others' (expected menuitems:"
            " Travel/Claims, Request, Receipt, Benefit/Others)"
        )
    ab("click", benefit, check=True)
    time.sleep(3)
    ab("wait", "--load", "networkidle")

    if not find_ref("combobox", "Benefit Type"):
        fail("the Add Benefit form did not appear (no '* Benefit Type' field found)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Open the reimburse.digital new-claim (Benefit/Others) form"
    )
    parser.add_argument(
        "--env",
        type=Path,
        default=Path(".env"),
        help="path to the .env holding ORGANISATION_ID / REIMBURSE_USERNAME /"
        " REIMBURSE_PASSWORD (default: ./.env)",
    )
    args = parser.parse_args()

    org_id, username, password, url = load_credentials(args.env)
    ensure_logged_in(org_id, username, password, url)
    open_reimburse_form()

    print(
        "READY: logged in and the Add Benefit (請款) form is open. The agent takes"
        " over to pick the benefit type/category, fill the date/amount/remarks,"
        " attach the receipt, and submit."
    )


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _handle_sigterm)
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
