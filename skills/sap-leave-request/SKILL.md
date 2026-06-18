---
name: sap-leave-request
description: >-
  Submit a leave / time-off request in SAP SuccessFactors using the
  agent-browser CLI. Use this whenever the user wants to take leave, apply for
  vacation, or file any kind of absence — annual leave (特休), personal leave
  (事假), sick leave (病假), marriage/birthday/compassionate leave, work-from-home,
  etc. Trigger on phrases like "幫我請假", "我要請假", "SAP 請假", "要求休假",
  "請特休", "on leave", "apply for leave", "book time off", or any request that
  names a date range plus a leave type. The skill logs in automatically (reading
  credentials from a .env file), opens the 要求休假 form, picks the leave type,
  fills the dates, and submits.
---

# SAP SuccessFactors Leave Request

Submit a full-day leave request in SAP SuccessFactors via the `agent-browser`
CLI. Every step below was verified end-to-end against the live system.

Note: the SAP UI is localized, so element labels in snapshots appear in Chinese
(e.g. `時間類型` = leave type, `開始日期` = start date, `提交` = submit). Those
quoted strings are literal UI text you must match — keep them as-is.

## Scope (v1)

- **Full-day leave only** (a start date and an end date). Half-day / specific
  time slots are not supported yet — if the user asks for a half-day, tell them
  plainly that this version doesn't support it; do not guess how to fill it.
- **Behavior: auto-submit once validation passes.** Do not stop for a second
  confirmation. The only exception is when the user explicitly says "don't
  submit" / "just fill it in" — in that case stop right before submitting.
- **Proof attachments are supported.** Sick-leave types (普通傷病假, 公傷病假,
  etc.) usually need a medical certificate or supporting document; the form
  itself exposes an attachment field for every leave type. When the user
  requests sick leave, proactively ask whether they want to attach proof, and
  if so upload it before submitting (see Step 3.5).

## Prerequisites

1. **`agent-browser` installed** (`which agent-browser`, verified on v0.28.0)
   and **`uv` installed** (the login script runs via `uv run`; its
   `python-dotenv` dependency is auto-installed from the PEP 723 inline
   metadata).
2. **A `.env` with config + credentials.** The SAP login account usually
   carries a domain backslash (`DOMAIN\account`), so the username **must be
   wrapped in single quotes**, otherwise `source` eats the `\` as an escape
   character. The home URL is org-specific (SAP datacenter host + company code),
   so it lives in `.env` too:

   ```
   SAP_USERNAME='DOMAIN\your.account'
   SAP_PASSWORD='your-password'
   SAP_URL='https://<your-sf-host>/sf/home?bplte_company=<your-company>'
   ```

   `SAP_URL` is your company's SuccessFactors home URL (including the company
   code parameter); after a successful login the browser should land on it.
   Copy the skill's `.env.example` to `.env` and fill it in. Lookup order for
   `.env`: current working directory → a path the user specifies explicitly. If
   it's missing, ask the user to create it — never write credentials or the
   company URL into a command line in plain text, and never ask the user to
   paste them into the chat.
3. Login needs **only username/password, no MFA**, so it can be fully automated.

## Security principles

- The login script passes credentials only as subprocess arguments; **never**
  let them appear in plain text in any command string you print or in the chat.
- These are real HR records. After submitting, always report a clear result
  (success/failure, leave type, dates, day count) — don't be vague.

## Full workflow

Login and opening the form is a fixed sequence handled by
`scripts/open_leave_form.py`; you (the agent) then take over to pick the leave
type, fill dates, and submit. Once you take over, follow agent-browser's core
loop: **`snapshot` to get `@eN` refs → act → re-snapshot after the page
changes**. Refs are renumbered on every snapshot and go stale as soon as the
page changes, so always re-snapshot right before acting.

### Step 1 — Run the script: log in and open the form

```bash
uv run <skill-dir>/scripts/open_leave_form.py --env <.env-path>
```

`--env` defaults to `./.env` and can usually be omitted. The script:

1. Loads credentials with `python-dotenv` (literal values, so the backslash
   inside single quotes is preserved).
2. Checks whether it's already on the home page (matched by `SAP_URL`'s host +
   path); only when not logged in does it open the browser (headed) and fill the
   company SSO / ADFS login page automatically.
3. Uses a coordinate click to bypass the UI5 icon overlay and open the
   `要求休假` (request-leave) form.

On success it prints `READY: ...` and exits 0, leaving the browser on the open
form. On failure it prints `ERROR: ...` and exits non-zero — relay that message
straight to the user (common causes: `.env` not found, or the username not
single-quoted so the backslash was eaten). After `READY`, snapshot to confirm
the fields before taking over:

```bash
agent-browser snapshot -i
# Expect: combobox "時間類型", textbox "開始日期", textbox "結束日期", button "提交", etc.
```

### Step 2 — Pick the leave type (時間類型)

This is a UI5 combobox; a plain click won't expand it, but **type-ahead is
reliable**: `fill` the full leave-type name, then press Enter:

```bash
agent-browser fill '<時間類型-ref>' "Personal Leave 事假"
agent-browser press Enter
agent-browser snapshot -i        # confirm the combobox value changed
```

The leave-type name must match the system option **exactly** (Chinese and
English included). See the full list in `references/leave-types.md`. Map the
user's colloquial term (e.g. "特休", "annual leave") to the official name; when
unsure, press F4 to expand and list the actual options first:

```bash
agent-browser focus '<時間類型-ref>'
agent-browser press F4
agent-browser snapshot           # lists every option
```

The default type is `Annual Leave 公司特休假`; if that's what the user wants,
you can skip this step.

### Step 3 — Fill the dates

Start / end dates are text boxes that accept the `YYYY/M/D` format (rendered as
`2026 年 6 月 22 日`). First convert the user's relative dates ("next Monday",
"tomorrow") into absolute dates based on today.

```bash
agent-browser fill '<start-date-ref>' "2026/6/22"
agent-browser fill '<end-date-ref>' "2026/6/22"
agent-browser press Tab          # triggers recalculation
sleep 2
agent-browser snapshot -i
```

### Step 3.5 — Upload a proof attachment (when needed, e.g. sick leave)

Sick-leave types often need proof. Behind the attachment field is a hidden
`<input type="file">`; `upload` to it directly — **do not click the
`Attachment 上傳` button**, which triggers the OS-native file dialog that
agent-browser cannot operate. Use an **absolute path** for the file:

```bash
agent-browser upload 'input[type=file]' "/absolute/path/proof.pdf"
sleep 2
agent-browser snapshot -i        # confirm the filename appears in the list
```

On success the attachment `list` in the snapshot shows the filename, upload
date, and file size (e.g.
`list "proof.pdf上傳日期: ... 檔案大小: 41287 位元組刪除"`); use that to confirm
the upload. The attachment persists through the later date recalculation.

Notes:

- **No file-type restriction**: the file input's `accept` is empty, so the
  front end doesn't restrict extensions. PDF / JPG / PNG were all verified;
  other common formats behave the same.
- **Only one attachment at a time**: after a successful upload the file input is
  removed from the DOM (`input[type=file]` count drops to 0). To swap files,
  delete the current attachment first — clicking `刪除` (delete) in the
  attachment row pops a `刪除檔案` confirmation dialog; press `確定` (confirm)
  and the input reappears so you can upload again.
- If the user requests sick leave but gives no file path, ask whether to attach
  proof first — don't submit blindly.
- Upload can happen in any order relative to picking the type and filling
  dates; just finish it before submitting.

### Step 4 — Validate, then submit

After filling, snapshot and check two things:

1. **`正在要求` (requesting) > 0 days.** If it's `0 天`, the chosen dates
   contain no working day (a weekend or a company holiday), or a red error
   appears at the top ("您要求的休假必須至少包括一個工作日"). **Do not submit in
   this case** — report which days are invalid and ask the user to change them.
2. **The `提交` (submit) button is not disabled.** It only enables once the
   dates are valid.

Only when both pass, click submit:

```bash
agent-browser snapshot -i        # get the latest 提交 ref and read the 正在要求 day count
agent-browser click '<提交-ref>'
sleep 3
agent-browser wait --load networkidle
agent-browser snapshot -i
```

Capture a screenshot for the record and confirm the result:

```bash
agent-browser screenshot /tmp/sap_leave_result.png
```

Report back to the user: leave type, start/end dates, day count, and the
submission result. If any error message appears (a red note / message strip),
relay it verbatim — do not treat it as success.

## Cancel / abort

To abandon a half-filled form, click the `取消` (cancel) button in the dialog
(verified: no second confirmation appears).

## Common error reference

| Symptom | Cause | Fix |
|------|------|------|
| `Element is covered by <ui5-icon>` | The `要求休假` button is covered by an icon | Use a coordinate click (Step 1 handles this) |
| Still on the SSO login page after login; username missing the backslash | `.env` not single-quoted, so `\` was eaten | Change the account to `'DOMAIN\your.account'` |
| `正在要求 0 天` / red "needs a working day" | Dates fall on a weekend or company holiday | Use valid working days; do not submit |
| 時間類型 combobox won't expand on click | UI5 custom element | Use `fill`+Enter (type-ahead) or F4 to expand |
| A ref action reports element not found | Ref went stale after the page changed | Re-run `snapshot -i` before acting |
| Clicking the upload button opens a stuck native file dialog | agent-browser can't operate native dialogs | Use `upload 'input[type=file]' <absolute-path>` (Step 3.5) |
