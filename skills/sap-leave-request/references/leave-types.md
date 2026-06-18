# Leave types (時間類型)

The full set of options in the `時間類型` (leave type) combobox of the SAP
SuccessFactors `要求休假` (request-leave) form. To select one, `fill` the
**full name (Chinese and English included)** then press Enter; the name must
match the table below exactly.

The `常見口語` column lists the colloquial terms (Chinese and English) a user
might say — map those to the official name in the first column.

| Official name (fill this) | 常見口語 |
|---|---|
| `Annual Leave 公司特休假` | 特休、年假、特休假、annual leave、AL、paid leave、vacation |
| `Award Leave 獎勵假` | 獎勵假、award leave |
| `Birthday Leave 生日假` | 生日假、birthday leave |
| `Compassionate Leave 喪假` | 喪假、bereavement leave、compassionate leave、funeral leave |
| `Compensated Rest Day 補休假` | 補休、comp day、compensated rest、time off in lieu |
| `Family Care Leave 家庭照顧假` | 家庭照顧假、家照假、family care leave |
| `Full-Paid Sick Leave 普通傷病假(全薪)` | 病假(全薪)、全薪病假、full-paid sick leave、paid sick leave |
| `Half-Paid Sick Leave 普通傷病假(半薪)` | 病假(半薪)、半薪病假、half-paid sick leave |
| `Indigenous Ritual Leave 原住民祭儀假` | 祭儀假、indigenous ritual leave |
| `Job Search Leave 謀職假` | 謀職假、job search leave、job-hunting leave |
| `Marriage Leave 婚假` | 婚假、marriage leave、wedding leave |
| `Occupational Injury Sick Leave 公傷病假` | 公傷病假、職災假、occupational injury leave、work injury leave |
| `Official Leave 公假` | 公假、official leave、official duty leave |
| `Paternity Leave / Paternity Checkup Leave 陪產(檢)假` | 陪產假、陪產檢假、paternity leave、paternity checkup leave |
| `Personal Leave 事假` | 事假、personal leave、unpaid personal leave |
| `Present without Access Card 出勤未刷卡` | 忘刷卡、未刷卡、forgot to badge、missed clock-in、no card swipe |
| `Training Leave 培訓假` | 培訓假、訓練假、training leave |
| `Unlimited Leave 無上限休假` | 無上限休假、unlimited leave |
| `Unpaid Military Service Leave 兵役留停` | 兵役留停、military service leave、conscription leave |
| `Unpaid Parental Leave 育嬰留職停薪假` | 育嬰假、育嬰留停、parental leave、childcare leave |
| `Volunteer Leave 公益假` | 公益假、志工假、volunteer leave |
| `Work From Home Permit 在家工作` | 在家工作、WFH、遠端、work from home、remote work |

Notes:

- For a plain "sick leave" with full/half pay unspecified, ask the user which
  one (full-paid vs half-paid) before selecting.
- Sick-leave types (full/half-paid 普通傷病假, 公傷病假, etc.) usually need a
  medical certificate; upload the file per Step 3.5 in SKILL.md before
  submitting. If no file path was given, ask the user whether to attach proof.
- When a colloquial term is ambiguous, press `F4` on the form to expand and
  trust the system's actual current options (the list may change with company
  policy).
- The default value is `Annual Leave 公司特休假`.
