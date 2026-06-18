---
name: reimburse-request
description: >-
  Submit a company expense reimbursement (請款 / 報帳) on reimburse.digital using
  the agent-browser CLI. Use this whenever the user wants to claim an expense,
  file for reimbursement, or report a cost they paid for the company — wellness
  fund, health check-up, marriage/childbirth/funeral allowance, and other
  benefit claims. Trigger on phrases like "幫我請款", "我要報帳", "報銷", "核銷",
  "報支", "claim expense", "file a reimbursement", "submit an expense", or any
  request that names an amount plus what it was for. The skill logs in
  automatically (reading the organisation id and SSO credentials from a .env
  file), opens the Benefit/Others claim form, fills the details, attaches the
  receipt, and submits.
---

# Reimburse.digital Expense Reimbursement

Submit an expense reimbursement (請款) on reimburse.digital via the
`agent-browser` CLI. Every step below was verified end-to-end against the live
system.

The app UI is in English (a language switch exists but the verified flow uses
English labels). Quoted strings like `* Benefit Type`, `Send For Approval` are
literal UI text you must match — keep them as-is.

## Scope (v1)

- **Benefit/Others claims** (the `請款` entry): one benefit type, one category,
  one receipt date, one amount, one or more receipt attachments. The other
  Add-New flows (`Travel/Claims`, `Request`, `Receipt`) are out of scope — if
  the user wants those, say plainly that this version doesn't support them.
- **Behavior: auto-submit once validation passes.** After filling and
  validating, click `Send For Approval` without stopping for a second
  confirmation. The only exception is when the user explicitly says "don't
  submit" / "just save as draft" — then click `Save as Draft` (or stop before
  submitting) instead.
- **Receipt attachment is core.** A claim needs a supporting document. If the
  user gives no file path, ask for one before submitting — don't submit a claim
  with no receipt unless the user explicitly says it has none.

## Prerequisites

1. **`agent-browser` installed** (`which agent-browser`, verified on v0.28.0)
   and **`uv` installed** (the login script runs via `uv run`; its
   `python-dotenv` dependency is auto-installed from the PEP 723 inline
   metadata).
2. **A `.env` with config + credentials.** If the login account carries a
   domain backslash (`DOMAIN\account`), the username **must be wrapped in single
   quotes**, otherwise `source` eats the `\` as an escape character:

   ```
   ORGANISATION_ID='your-org-id'
   REIMBURSE_USERNAME='your.account'
   REIMBURSE_PASSWORD='your-password'
   # REIMBURSE_URL='https://app.reimburse.digital/'   # optional override
   ```

   Copy the skill's `.env.example` to `.env` and fill it in. Lookup order for
   `.env`: current working directory → a path the user specifies explicitly. If
   it's missing, ask the user to create it — never write credentials into a
   command line in plain text, and never ask the user to paste them into the
   chat.
3. **Login depends on your organisation's SSO.** reimburse.digital asks for the
   organisation id, then redirects to the organisation's own SSO / identity
   provider. That page varies per org (different IdP, labels, language, possibly
   MFA). The login script fills the first username/password/login it recognizes
   from a list of common labels; if your org's SSO differs or uses MFA, the
   automated login may not complete — extend the `SSO_*_LABELS` in the script or
   complete the SSO step manually, then re-run.

## Security principles

- The login script passes credentials only as subprocess arguments; **never**
  let them appear in plain text in any command string you print or in the chat.
- These are real financial records. After submitting, always report a clear
  result (benefit type, category, date, amount, payable amount, receipt count,
  submission outcome) — don't be vague. If any error / red message appears,
  relay it verbatim; never treat it as success.

## Full workflow

Login and opening the form is a fixed sequence handled by
`scripts/open_reimburse_form.py`; you (the agent) then take over to fill the
claim, attach the receipt, validate, and submit. Once you take over, follow
agent-browser's core loop: **`snapshot` to get `@eN` refs → act → re-snapshot
after the page changes**. Refs are renumbered on every snapshot and go stale as
soon as the page changes, so always re-snapshot right before acting.

### Step 1 — Run the script: log in and open the form

```bash
uv run <skill-dir>/scripts/open_reimburse_form.py --env <.env-path>
```

`--env` defaults to `./.env` and can usually be omitted. The script:

1. Loads config + credentials with `python-dotenv` (literal values, so the
   backslash inside single quotes is preserved).
2. Checks whether it's already authenticated; only when not logged in does it
   open the browser (headed), enter the `ORGANISATION_ID` on the
   `Enter Your Organisation ID` page, click `Continue`, then fill the
   credentials on the organisation's SSO page (matching the username/password/
   login fields from a list of common labels — this page varies per org).
3. Opens the claim form via `Add New` → `Benefit/Others`
   (`/add-benefit-claim/benefit`, heading `Add Benefit`).

On success it prints `READY: ...` and exits 0, leaving the browser on the open
form. On failure it prints `ERROR: ...` and exits non-zero — relay that message
straight to the user (common causes: `.env` not found, username not
single-quoted so the backslash was eaten, or a wrong `ORGANISATION_ID`). After
`READY`, snapshot to confirm the fields before taking over:

```bash
agent-browser snapshot -i
# Expect: combobox "* Benefit Type", textbox "* Receipt Date",
# spinbutton "* Claim Amount", textbox "Remarks/Purpose",
# button "Add More", button "Send For Approval".
# (A "* Benefit Category" / "* Clinic Name" field appears only for some types — see Step 2.)
```

### Step 2 — Pick the benefit type (and category, if any)

The combobox has a clickable wrapper `generic [onclick]` that is the **parent**
of the `combobox` element. **Click that wrapper to open the dropdown — clicking
the `combobox` element itself silently auto-selects the first option** (it picks
"Annual Health Check-up" by mistake). Then click the option's row in the open
list (each is a `generic "<text>" clickable [onclick]`), and **verify the
displayed value changed** before moving on.

```bash
agent-browser snapshot -i                 # find the Benefit Type onclick wrapper (parent of the combobox)
agent-browser click '<benefit-type-wrapper-ref>'
agent-browser snapshot -i                 # read the option rows (5 TW-* options)
agent-browser click '<type-option-ref>'
sleep 2
agent-browser snapshot -i                 # confirm the type changed; see which extra fields appeared
```

Map the user's colloquial term to the official option text. The full
type/category lists are in `references/benefit-types.md`.

**Each benefit type renders different fields** (verified):

- `TW-Wellness Fund 健康促進津貼` — also requires a `* Benefit Category`
  (open it the same way; options carry a **rate** like `50%`/`100%`). The form
  computes `Payable Amount = Claim Amount × rate` automatically, so always enter
  the **gross** amount — never pre-multiply.
- `TW-Annual Health Check-up Subsidy 健康檢查` — also requires `* Clinic Name`
  (a textbox) and shows a TIPS panel with the annual entitlement
  (Entitled / Maximum / Remaining); respect those limits.
- `TW-Childbirth Allowance`, `TW-Funeral Allowance`, `TW-Marriage Allowance` —
  no category, no extra field; just the common fields below.

`* Currency` (TWD), `* Charge-to`, and `* Cost Centre` are **disabled defaults**;
leave them as-is.

### Step 3 — Fill the receipt date

`* Receipt Date` is an antd date picker — **typing does not work**; click it to
open the calendar, then click the day cell. The panel opens on the current
month with `<Month>` / `<Year>` header buttons to navigate. The field renders as
`DD/MM/YYYY`. Convert the user's relative dates ("yesterday", "上週五") to an
absolute date first.

```bash
agent-browser click '<receipt-date-ref>'
agent-browser snapshot -i                 # find the right day cell (navigate months if needed)
agent-browser click '<day-cell-ref>'      # e.g. cell "18"
agent-browser snapshot -i                 # confirm the date shows DD/MM/YYYY
```

### Step 4 — Fill the claim amount

`* Claim Amount` is an antd `InputNumber` **pre-filled with `0.00`**. A plain
`fill` does not stick (the control reverts on blur). You must clear it first,
then type the digits:

```bash
agent-browser click 'input.ant-input-number-input:not([disabled])'
agent-browser press End
# clear the pre-filled 0.00 (Backspace a handful of times)
for i in $(seq 1 8); do agent-browser press Backspace; done
# type the amount one key at a time (more reliable than `type`/`fill` here)
agent-browser press 1; agent-browser press 0; agent-browser press 0; agent-browser press 0
agent-browser press Tab                    # blur -> formats to 1000.00 and computes Payable
agent-browser snapshot -i
```

After blur, confirm `* Claim Amount` shows the gross value and `Payable Amount`
reflects the category rate (e.g. 1000.00 → 500.00 at 50%).

Fill the optional remarks if the user gave a purpose:

```bash
agent-browser fill '<remarks-ref>' "<what it was for>"
```

### Step 5 — Attach the receipt (core)

The `Add More` button under **Supporting Documents** is an antd dropdown
trigger, **not** a direct file dialog. Click it to open the dropdown — only then
is a hidden `input[type=file]` rendered (multiple, accepts
JPG/JPEG/PNG/JFIF/PDF/EML/MSG, ≤ 20 MB). Then `upload` to that input with an
**absolute path**; the input persists even after the dropdown closes.

```bash
agent-browser click '<add-more-ref>'       # opens the dropdown; renders the file input
agent-browser upload 'input[type=file]' "/absolute/path/receipt.pdf"
sleep 2
agent-browser snapshot -i                  # confirm "N Files Attached" appears
```

The UI shows a count like `2 Files Attached` (filenames are not shown as plain
text), with a paperclip link to view/manage them. To attach several receipts,
repeat the upload (the input is `multiple`).

### Step 6 — Validate, then submit

Snapshot and check before submitting:

1. **No red validation error** on any required field (`* Benefit Type`,
   `* Receipt Date`, `* Benefit Category`, `* Claim Amount`) and a receipt is
   attached.
2. **`Send For Approval` is enabled.**

Only when both pass, submit (auto-submit per Scope):

```bash
agent-browser snapshot -i                  # get the latest Send For Approval ref
agent-browser click '<send-for-approval-ref>'
sleep 3
agent-browser wait --load networkidle
agent-browser snapshot -i
agent-browser screenshot /tmp/reimburse_result.png
```

Report back: benefit type, category, receipt date, claim amount, payable amount,
attached-file count, and the submission result. If any error message appears (a
red note / message strip), relay it verbatim — do not treat it as success.

If the user said "just save as draft", click `Save as Draft` instead of
`Send For Approval`.

## Cancel / abort

To abandon a half-filled form, navigate away (e.g. open another menu item like
`Drafts`); the unsaved form is discarded. Use `Save as Draft` only if the user
wants to keep it for later.

## Common error reference

| Symptom | Cause | Fix |
|------|------|------|
| `ERROR: .env not found` | No `.env` in cwd or at `--env` path | Copy `.env.example` to `.env` and fill it in |
| `ERROR: ... still not authenticated`; username missing the backslash | `.env` not single-quoted, so `\` was eaten | Single-quote the account, e.g. `'DOMAIN\your.account'` |
| `ERROR: found a username field but not the password/login button` | Your org's SSO uses labels the script doesn't recognize | Add them to `SSO_*_LABELS` in the script, or log in manually then re-run |
| `ERROR: ... still not authenticated` (creds look right) | Wrong `ORGANISATION_ID`, wrong password, or the SSO needs MFA | Verify org id/credentials; for MFA, complete login manually then re-run |
| Benefit Type jumps to "Annual Health Check-up" unexpectedly | Clicked the `combobox` element, which auto-selects the first option | Click the parent `generic [onclick]` wrapper to open the dropdown, then the option row (Step 2) |
| Claim Amount stays `0.00` after filling | antd InputNumber reverts a plain `fill`; the field was pre-filled with `0.00` | Clear with End+Backspace, then `press` the digits (Step 4) |
| Receipt date won't set by typing | It's an antd date picker | Click the field and click the day cell (Step 3) |
| `upload` reports "Node is not a file input element" | The `input[type=file]` only exists while the `Add More` dropdown is open | Click `Add More` first, then `upload 'input[type=file]'` (Step 5) |
| A ref action reports element not found | Ref went stale after the page changed | Re-run `snapshot -i` before acting |
| `Payable Amount` differs from `Claim Amount` | The chosen category applies a rate (e.g. 50%) | Expected — enter the gross amount; the form computes payable |
