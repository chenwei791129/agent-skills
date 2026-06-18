# Benefit types & categories (Benefit/Others 請款)

The options in the `* Benefit Type` (and, for some types, `* Benefit Category`)
comboboxes of the `Add Benefit` form (`/add-benefit-claim/benefit`).

> **⚠ The specific type/category names, rates, and entitlement amounts below are
> ONE organisation's example scheme — yours will almost certainly differ.** They
> are reimburse.digital tenant configuration, not product defaults. Treat this
> table as an illustration of the *shape* of the data; for the real options,
> always expand the live combobox and read what your tenant actually offers. The
> interaction mechanics (how to select, how fields vary by type, how the rate
> drives Payable Amount) ARE general and apply to any tenant.

## Selecting a combobox option (important)

The Benefit Type / Category combobox has a clickable wrapper `generic [onclick]`
that is the **parent** of the `combobox` element. **Click the wrapper to open
the dropdown — clicking the `combobox` element itself auto-selects the first
option** (a real trap: it silently picks "Annual Health Check-up"). Then click
the option's row in the open list (each option is a
`generic "<text>" clickable [onclick]`). Verify the selection afterward by
reading the displayed value.

## Benefit Type — and the per-type fields

Each type renders a **different set of fields**. Verified:

| Benefit Type (visible text) | 中文 | Benefit Category | Extra field | Entitlement TIPS |
|---|---|---|---|---|
| `TW-Annual Health Check-up Subsidy健康檢查` | 健康檢查補助 | — | `* Clinic Name` (textbox) | yes (Entitled/Max/Remaining + valid period) |
| `TW-Childbirth Allowance生育獎金` | 生育獎金 | — | — | no |
| `TW-Funeral Allowance喪葬補助金` | 喪葬補助金 | — | — | no |
| `TW-Marriage Allowance結婚獎金` | 結婚獎金 | — | — | no |
| `TW-Wellness Fund健康促進津貼` | 健康促進津貼 | yes (see below) | — | — |

Common required fields on every type: `* Benefit Type`, `* Receipt Date`,
`* Currency` (TWD, disabled), `* Claim Amount`, `* Charge-to` (disabled
default), `* Cost Centre` (disabled default), plus a Supporting Documents
attachment.

- **Annual Health Check-up** additionally requires `* Clinic Name` and shows a
  TIPS panel with the annual entitlement (e.g. Entitled 5000.00 / Max 5000.00 /
  Remaining, valid 01/01–31/12). Respect `Maximum Claim Amount` /
  `Remaining Amount` when filling the amount.
- **Childbirth / Funeral / Marriage** use only the common fields — no category,
  no clinic name, no entitlement TIPS.

## Benefit Category — only for TW-Wellness Fund 健康促進津貼

The category label carries the **reimbursement rate** (`50%` / `100%`). The form
computes `Payable Amount = Claim Amount × rate` automatically (verified: Claim
1000 with a 50% category → Payable 500). Always fill the **gross** `Claim
Amount`; never pre-multiply by the rate.

| Category (visible text) | Rate |
|---|---|
| `EAP (心理支持) 100%` | 100% |
| `Leisure Activities (休閒活動) 50%` | 50% |
| `Self-Paid Medical (自費醫療) 100%` | 100% |
| `Sports Activities (運動項目) 50%` | 50% |
| `Pregnancy Transportation (好孕交通) 50%` | 50% |

The category list only populates **after** the Benefit Type is set to Wellness
Fund. Map the user's colloquial term to the visible option text; when ambiguous,
list the live options and ask.

Notes:

- `* Currency` is fixed to `New Taiwan Dollar (TWD)` (disabled).
- `* Charge-to` (default `Local cost centre`) and `* Cost Centre` (default the
  user's department) are disabled — leave them at their defaults.
- `Payable Amount`, `Tax Amount`, `Amount Before Taxes` are read-only computed
  fields; do not try to fill them.
