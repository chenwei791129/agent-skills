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

# SAP SuccessFactors 請假申請

用 `agent-browser` CLI 在 SAP SuccessFactors 自動提交全日請假申請。整個流程的可
行性與每一個指令都經過實測驗證。

## 適用範圍 (v1)

- **只處理全日請假**(指定開始日期、結束日期)。半日假 / 指定時段尚未支援 —
  若使用者要求半日假,明確告知此版本不支援,不要猜測填法。
- **行為:填完驗證通過後直接自動提交**,不另外停下來等使用者二次確認。
  唯一例外:使用者明確說「先別送出」「只填好不要提交」時,填到送出前停住。
- **支援上傳證明附件**。病假類假別(普通傷病假、公傷病假等)通常需附醫療證明
  或相關文件;表單本身對所有假別都有附件欄位。使用者請病假時,主動詢問是否要附
  證明檔案,有就在送出前上傳(見步驟 3.5)。

## 前置需求

1. **`agent-browser` 已安裝**(`which agent-browser`,實測 v0.28.0)、**`uv` 已安裝**
   (登入腳本以 `uv run` 執行,依賴 `python-dotenv` 由 PEP 723 內嵌自動安裝)。
2. **`.env` 內含設定與帳密**。SAP 登入帳號通常帶網域反斜線(`DOMAIN\account`),
   因此 `.env` 的帳號**必須用單引號包住**,否則 `source` 會把 `\` 當跳脫字元吃掉。
   首頁 URL 因組織而異(SAP 資料中心主機 + 公司代碼參數),所以也放在 `.env`:

   ```
   SAP_USERNAME='DOMAIN\your.account'
   SAP_PASSWORD='your-password'
   SAP_URL='https://<your-sf-host>/sf/home?bplte_company=<your-company>'
   ```

   `SAP_URL` 填你公司的 SuccessFactors 首頁網址(含公司代碼參數),登入成功後瀏覽器
   應停在這個位址。找 `.env` 的順序:目前工作目錄 → 使用者明確指定的路徑。找不到就
   請使用者建立,不要把帳密或公司網址寫進指令明文或要使用者貼到對話裡。

3. 登入**只需要帳密、沒有 MFA**,所以可全自動。

## 安全原則

- 帳密一律用 shell 變數展開(`"$SAP_USERNAME"`),**絕不**讓明文出現在你輸出的
  指令字串或對話中。載入方式固定為 `set -a; source <.env路徑>; set +a`。
- 提交的是真實人資記錄。送出後務必回報一個明確的結果(成功/失敗、假別、日期、
  天數),不要含糊帶過。

## 完整流程

登入與開啟表單這段是固定流程,交給腳本 `scripts/open_leave_form.py`;之後選假別、
填日期、送出由你(agent)接手。接手後遵循 agent-browser 的核心循環:**snapshot 取得
`@eN` ref → 操作 → 頁面變動後重新 snapshot**。ref 每次 snapshot 都重新編號,頁面一
變就失效,動作前務必重新 snapshot。

### 步驟 1 — 執行腳本:登入並開啟表單

```bash
uv run <skill目錄>/scripts/open_leave_form.py --env <.env路徑>
```

`--env` 預設為 `./.env`,通常省略即可。腳本會:

1. 用 `python-dotenv` 載入帳密(讀字面值,單引號內的反斜線天然保留)。
2. 檢查是否已在首頁(以 `SAP_URL` 的主機與路徑判斷),沒登入才開瀏覽器(headed)
   並在公司 SSO / ADFS 登入頁自動填帳密。
3. 用座標點擊繞過 UI5 圖示遮擋,開啟「要求休假」表單。

成功時印出 `READY: ...`、退出碼 0,瀏覽器停在已開啟的表單上。失敗會印 `ERROR: ...`
並以非 0 退出 — 直接把錯誤訊息回報使用者(常見:`.env` 找不到、帳號未用單引號導致
反斜線被吃掉)。腳本印 READY 後,snapshot 確認欄位再接手:

```bash
agent-browser snapshot -i
# 預期看到 combobox "時間類型"、textbox "開始日期"、textbox "結束日期"、button "提交" 等
```

### 步驟 2 — 選擇假別(時間類型)

這是 UI5 combobox,一般 click 不會展開,但 **type-ahead 可靠**:`fill` 完整假別
名稱再按 Enter:

```bash
agent-browser fill '<時間類型ref>' "Personal Leave 事假"
agent-browser press Enter
agent-browser snapshot -i        # 確認 combobox 值已變
```

假別名稱必須與系統選項**完全一致**(含中英文)。完整清單見
`references/leave-types.md`。把使用者的口語(如「特休」「事假」)對應到正式名稱;
對應不確定時,先按 F4 展開列出實際選項再決定:

```bash
agent-browser focus '<時間類型ref>'
agent-browser press F4
agent-browser snapshot           # 列出所有 option
```

預設假別是「Annual Leave 公司特休假」;若使用者要的就是特休,可略過本步驟。

### 步驟 3 — 填入日期

開始 / 結束日期是文字框,接受 `YYYY/M/D` 格式(會顯示成「2026 年 6 月 22 日」)。
先把使用者的相對日期(「下週一」「明天」)依今天日期換算成絕對日期。

```bash
agent-browser fill '<開始日期ref>' "2026/6/22"
agent-browser fill '<結束日期ref>' "2026/6/22"
agent-browser press Tab          # 觸發重算
sleep 2
agent-browser snapshot -i
```

### 步驟 3.5 — 上傳證明附件(病假等需要時)

病假類假別常需附證明。表單的附件欄位背後是一個隱藏的 `<input type="file">`,直接
對它 `upload` 即可,**不必去點「Attachment 上傳」按鈕觸發原生檔案對話框**(那個對話
框 agent-browser 無法操作)。檔案路徑要用**絕對路徑**:

```bash
agent-browser upload 'input[type=file]' "/絕對/路徑/proof.pdf"
sleep 2
agent-browser snapshot -i        # 確認附件清單已出現檔名
```

上傳成功後,snapshot 的附件 `list` 會帶出檔名、上傳日期與檔案大小(例如
`list "proof.pdf上傳日期: ... 檔案大小: 41287 位元組刪除"`),據此確認上傳成功。
附件在後續填日期重算後仍會保留。

注意:

- **檔案型別不限**:file input 的 `accept` 為空,前端不限副檔名。PDF / JPG / PNG
  均實測可上傳;其他常見格式(如 JPEG)同理。
- **一次只能掛一個附件**:上傳成功後該 file input 會從 DOM 移除
  (`input[type=file]` 數量歸 0)。要換檔案得先刪除現有附件 —— 點附件列的「刪除」
  會跳出「刪除檔案」確認框,按「確定」後 input 才重新出現,才能再上傳。
- 使用者請病假卻沒提供檔案路徑時,先問要不要附證明,不要憑空送出。
- 上傳與選假別、填日期的先後順序不拘;在送出前完成即可。

### 步驟 4 — 驗證後提交

填完後 snapshot,檢查兩件事:

1. **「正在要求」> 0 天**。若是「0 天」,代表所選日期不含工作日(碰到週末或公司
   假日),或頂部出現紅字「您要求的休假必須至少包括一個工作日」。**這種情況不要
   提交** — 回報使用者哪幾天無效,請對方改日期。
2. **「提交」按鈕未被 disabled**。日期有效後才會啟用。

兩項都通過,才點提交:

```bash
agent-browser snapshot -i        # 取得最新「提交」ref,並讀「正在要求」天數
agent-browser click '<提交ref>'
sleep 3
agent-browser wait --load networkidle
agent-browser snapshot -i
```

送出後截圖留存並確認結果:

```bash
agent-browser screenshot /tmp/sap_leave_result.png
```

向使用者回報:假別、起訖日期、天數、送出結果。若出現任何錯誤訊息(紅字 note /
訊息列),原文回報,不要當成功。

## 取消 / 中止

要放棄填到一半的表單,點對話框的「取消」按鈕即可(實測不會跳二次確認框)。

## 常見錯誤對照

| 症狀 | 原因 | 處理 |
|------|------|------|
| `Element is covered by <ui5-icon>` | 「要求休假」鈕被圖示蓋住 | 改用座標點擊(步驟 3) |
| 登入後仍停 SSO 登入頁,帳號缺反斜線 | `.env` 沒用單引號,`\` 被吃掉 | 帳號改成 `'DOMAIN\your.account'` |
| 「正在要求 0 天」/ 紅字要求工作日 | 日期落在週末或公司假日 | 換有效工作日,勿提交 |
| 時間類型 combobox 點了不展開 | UI5 自訂元件 | 用 `fill`+Enter(type-ahead)或 F4 展開 |
| ref 操作報找不到元素 | 頁面變動後 ref 失效 | 動作前重新 `snapshot -i` |
| 點「上傳」按鈕跳出原生檔案對話框卡住 | agent-browser 無法操作原生對話框 | 改用 `upload 'input[type=file]' <絕對路徑>`(步驟 3.5) |

## 半日 / 指定時段

v1 不支援。使用者要求時,明確告知並停手,不要臆測時段欄位填法。
