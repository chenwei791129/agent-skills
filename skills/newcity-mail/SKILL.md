---
name: newcity-mail
description: >-
  查詢 Newcity 社區物業 app(itlife.com.tw / NewcityWebApi)的待領、未領、已領信件與包裹。
  當使用者想知道「有沒有我的信/包裹到了」「未領信件」「待領信件」「已領信件」「社區管理室有沒有東西要領」
  「幫我查 newcity / itlife 的信件」,或提到要登入這個社區 app 拿信件清單時,就使用這個 skill。
  即使使用者沒明講 app 名稱,只要是查「社區/大樓管理室代收的信件或包裹」就適用。
  本 skill 透過 app 的 API 重現登入->選社區->解析住戶->查詢流程,印出信件清單。
---

# Newcity 社區信件查詢

透過 Newcity 物業 app 的後端 API（`https://www.itlife.com.tw/NewcityWebApi/api`）查詢使用者的
待領 / 已領信件。底層是一支自包含的 `uv` 腳本 `query_mail.py`，本 skill 負責在正確的前提下執行它並回報結果。

## 何時用

- 使用者想查社區/大樓管理室代收的信件、包裹是否到了、要不要去領。
- 關鍵詞：未領信件、待領信件、已領信件、有沒有我的包裹、newcity、itlife、社區 app 信件。

## 執行方式

腳本與本 skill 同目錄，直接用 `uv run` 執行（依賴由 PEP 723 inline metadata 自動安裝）：

```bash
# 查未領信件（預設）
uv run ~/.claude/skills/newcity-mail/query_mail.py

# 查已領信件
uv run ~/.claude/skills/newcity-mail/query_mail.py --status 2
```

參數：
- `--status`：`1`=未領（預設），`2`=已領。
- `--page-size`：每頁筆數（預設 50，腳本會自動翻頁取完）。

執行後把腳本輸出（社區、住戶、信件清單或「目前沒有…信件」）原樣轉述給使用者即可，不需重新排版。

## 憑證設定（重要）

腳本需要登入帳密，依下列順序查找（高 → 低優先）：

1. **執行目錄的 `.env`**（`uv run` 當下所在目錄）
2. **本 skill 目錄的 `.env`**（`~/.claude/skills/newcity-mail/.env`）
3. **環境變數** `NEWCITY_USERID` / `NEWCITY_PASSWORD`

變數：

| 變數 | 說明 |
|------|------|
| `NEWCITY_USERID` | 登入帳號（必填） |
| `NEWCITY_PASSWORD` | 登入密碼（必填） |
| `NEWCITY_BEARER` | 選填；留空則每次執行自動隨機產生 |

範本見 `.env.example`。若腳本回報找不到帳密，請引導使用者：複製 `.env.example` 為 `.env`
（放在執行目錄或 skill 目錄皆可）並填入帳密，**不要**把真實帳密寫進 SKILL.md 或提交進版控。

## 關於 Bearer token

app 每個請求（含登入）都帶相同的 `Bearer` header，伺服器把 session 綁定到「當下帶上來的這個
token」——登入回應不發 token、也不輪替。實測該 token 是 160 個隨機位元組的 base64 編碼，屬於用戶端
自行產生的裝置識別碼，因此腳本預設每次執行隨機產生一個新值即可正常查詢，不需沿用任何真實裝置的 token。
僅在日後後端開始驗證該值時，才需用 `NEWCITY_BEARER` 覆寫成擷取到的真實值。

## 背景

完整的 app 運作流程與 API 逐筆解析見 `references/app-flow-analysis.md`——只有在需要擴充功能
（例如查其他模組、調整查詢欄位）或排查 API 行為時才需要讀它，一般查信件不必載入。
