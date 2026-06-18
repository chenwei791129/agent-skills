# reimburse-request

A Claude Code skill that submits an expense reimbursement (請款 / 報帳) on
[reimburse.digital](https://app.reimburse.digital/) by driving a real browser
with the [`agent-browser`](https://github.com/) CLI. It logs in through your
organisation's SSO, opens the **Benefit/Others** claim form, fills in the
details, attaches the receipt, and submits — all from a natural-language request
like "幫我請款 1000 元的運動補助，收據在 ~/receipt.pdf".

> **Scope:** this skill covers the **Benefit/Others** claim flow only. The other
> Add-New flows (`Travel/Claims`, `Request`, `Receipt`) are not implemented.

## How it works

1. A small Python prelude (`scripts/open_reimburse_form.py`) handles the
   deterministic part: log in and open the claim form. It's run via `uv run`
   (dependencies are declared inline with PEP 723, so no manual install).
2. Once the form is open, the agent (Claude) takes over the variable part —
   picking the benefit type/category, filling the date/amount/remarks,
   uploading the receipt, validating, and submitting — following the steps in
   `SKILL.md`.

```
reimburse-request/
├── SKILL.md                     # the workflow the agent follows
├── README.md                    # this file
├── .env.example                 # copy to .env and fill in
├── .gitignore                   # ignores your real .env
├── references/
│   └── benefit-types.md         # benefit type/category mechanics (+ one org's example scheme)
└── scripts/
    └── open_reimburse_form.py   # login + open-form prelude
```

## Prerequisites

- [`agent-browser`](https://www.npmjs.com/) installed and on your `PATH`
  (verified on v0.28.0): `which agent-browser`.
- [`uv`](https://docs.astral.sh/uv/) installed (runs the login script).
- A reimburse.digital account and your organisation id.

## Setup

Copy the template and fill in your details:

```bash
cp .env.example .env
$EDITOR .env
```

```dotenv
ORGANISATION_ID='your-org-id'
REIMBURSE_USERNAME='your.account'
REIMBURSE_PASSWORD='your-password'
# REIMBURSE_URL='https://app.reimburse.digital/'   # optional override
```

Notes:

- **Single-quote the values.** If your username carries a domain backslash
  (`DOMAIN\account`), single quotes keep the `\` from being eaten as a shell
  escape.
- `.env` is git-ignored. **Never commit it**, and if you share this skill by
  zipping the folder, delete or exclude your real `.env` first — ship only
  `.env.example`.

## Usage

Ask Claude Code in plain language, e.g.:

- "幫我請款健康促進津貼 1000 元，收據在 /Users/me/Downloads/receipt.pdf"
- "submit a reimbursement for the marriage allowance, receipt at ~/cert.jpg"

The skill triggers automatically on reimbursement-style requests (see the
description in `SKILL.md`). It logs in, fills the form, attaches the receipt,
and — once validation passes — **submits for approval automatically**. Say
"just save as draft" or "don't submit" to stop before submitting.

You can also run the login prelude on its own to land on the open form:

```bash
uv run scripts/open_reimburse_form.py --env ./.env
```

## Per-organisation differences (important)

reimburse.digital is multi-tenant, so two things vary by organisation and are
**not** hard-coded as universal truth:

- **SSO login.** After the organisation id, reimburse.digital redirects to your
  organisation's own identity provider. That page differs per org (IdP, field
  labels, language, possibly MFA). The login script tries a list of common
  username/password/login labels (`SSO_*_LABELS` in the script); if your org's
  SSO uses different labels or requires MFA, extend that list or complete the
  SSO step manually, then re-run.
- **Benefit catalog.** The benefit types, categories, reimbursement rates, and
  entitlement amounts are tenant configuration. The table in
  `references/benefit-types.md` is **one organisation's example** — yours will
  differ. The agent reads the live options from the form; the reference only
  documents the *mechanics* (which are universal).

## Security

- Credentials are read from `.env` and passed only as subprocess arguments —
  never printed in chat or embedded in command strings.
- These are real financial records. The skill reports a clear result after
  submitting and relays any error message verbatim instead of assuming success.

## Limitations

- Full-form **Benefit/Others** claims only (one type, one category where
  applicable, one amount, one receipt date, one or more attachments).
- No MFA automation — if your SSO enforces MFA, the automated login won't
  complete on its own.
- Verified against reimburse.digital as of mid-2026; UI changes may require
  updating the selectors in `SKILL.md` / `scripts/open_reimburse_form.py`.
