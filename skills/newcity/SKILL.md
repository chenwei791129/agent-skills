---
name: newcity
description: >-
  查詢 Newcity 社區物業 app(itlife.com.tw / NewcityWebApi)的信件包裹與社區點數。
  信件:當使用者想知道「有沒有我的信/包裹到了」「未領信件」「待領信件」「已領信件」
  「社區管理室有沒有東西要領」「幫我查 newcity / itlife 的信件」時使用。
  點數:當使用者想知道「我還有多少社區點數」「剩餘點數」「公設/餐飲點數還剩多少」
  「點數什麼時候過期」時使用。
  公告:當使用者想知道「社區有什麼新公告」「最新公告」「未讀公告」「管委會公告」
  「公告內容/附件」時使用。
  即使使用者沒明講 app 名稱,只要是查「社區/大樓管理室代收的信件包裹」「社區點數餘額」或社區公告就適用。
  本 skill 透過 app 的 API 重現登入->選社區->解析住戶->查詢流程,印出結果。
---

# Newcity 社區查詢

透過 Newcity 物業 app 的後端 API（`https://www.itlife.com.tw/NewcityWebApi/api`）查詢使用者的
信件與社區點數。底層是一支以 `uv` 執行的子指令 CLI `scripts/newcity.py`，共用的登入/身分解析邏輯
放在 `scripts/newcity_client.py`。本 skill 負責在正確的前提下執行它並回報結果。

## 何時用

- **信件**：查社區/大樓管理室代收的信件、包裹是否到了、要不要去領。
  關鍵詞：未領信件、待領信件、已領信件、有沒有我的包裹。
- **點數**：查社區剩餘點數餘額、點數有效期。
  關鍵詞：剩餘點數、社區點數、公設點數、點數過期。
- **公告**：查社區最新公告（預設未讀），讀取單則內文與附件。
  關鍵詞：最新公告、未讀公告、管委會公告、公告內容、公告附件。
- 通用關鍵詞：newcity、itlife、社區 app。

## 執行方式

腳本在本 skill 的 `scripts/` 下，直接用 `uv run` 執行（依賴由 PEP 723 inline metadata 自動安裝）：

```bash
# 查未領信件（預設）
uv run ~/.claude/skills/newcity/scripts/newcity.py mail

# 查已領信件
uv run ~/.claude/skills/newcity/scripts/newcity.py mail --status 2

# 查社區剩餘點數（總和 + 每筆明細與有效期）
uv run ~/.claude/skills/newcity/scripts/newcity.py points

# 查未讀公告（預設）
uv run ~/.claude/skills/newcity/scripts/newcity.py announcements

# 查全部公告、只看前 20 則
uv run ~/.claude/skills/newcity/scripts/newcity.py announcements --status all --limit 20

# 讀取單則公告內文與附件（NO_PU 來自清單），並把附件存到指定目錄
uv run ~/.claude/skills/newcity/scripts/newcity.py announcement PU2026010100001 --save ~/Downloads

# 讀取單則公告並順便標記為已讀（badge 會 -1）
uv run ~/.claude/skills/newcity/scripts/newcity.py announcement PU2026010100001 --mark-read
```

子指令與參數：
- `mail`：查信件。
  - `--status`：`1`=未領（預設），`2`=已領。
  - `--page-size`：每頁筆數（預設 50，腳本會自動翻頁取完）。
- `points`：查剩餘點數。印出剩餘點數總和與每筆贈點明細（類別、單筆/剩餘點數、有效起迄日、單號）。
  - `--page-size`：每頁筆數（預設 50）。
- `announcements`：查公告清單。
  - `--status`：`unread`=未讀（預設），`all`=全部，`read`=已讀。
  - `--limit`：只顯示前 N 則。
- `announcement <NO_PU>`：讀取單則公告內文與附件。
  - `--save <dir>`：把附件下載存到指定目錄。
  - `--mark-read`：讀完順便把這則標記為已讀（預設不標記，純讀取）。

執行後把腳本輸出原樣轉述給使用者即可，不需重新排版。

## 憑證設定（重要）

腳本需要登入帳密，依下列順序查找（高 → 低優先）：

1. **執行目錄的 `.env`**（`uv run` 當下所在目錄）
2. **本 skill 根目錄的 `.env`**（`~/.claude/skills/newcity/.env`，即 `scripts/` 的父層）
3. **環境變數** `NEWCITY_USERID` / `NEWCITY_PASSWORD`

變數：

| 變數 | 說明 |
|------|------|
| `NEWCITY_USERID` | 登入帳號（必填） |
| `NEWCITY_PASSWORD` | 登入密碼（必填） |
| `NEWCITY_BEARER` | 選填；留空則每次執行自動隨機產生 |

範本見 `.env.example`。若腳本回報找不到帳密，請引導使用者：複製 `.env.example` 為 `.env`
（放在執行目錄或 skill 根目錄皆可）並填入帳密，**不要**把真實帳密寫進 SKILL.md 或提交進版控。

## 關於 Bearer token

app 每個請求（含登入）都帶相同的 `Bearer` header，伺服器把 session 綁定到「當下帶上來的這個
token」——登入回應不發 token、也不輪替。實測該 token 是 160 個隨機位元組的 base64 編碼，屬於用戶端
自行產生的裝置識別碼，因此腳本預設每次執行隨機產生一個新值即可正常查詢，不需沿用任何真實裝置的 token。
僅在日後後端開始驗證該值時，才需用 `NEWCITY_BEARER` 覆寫成擷取到的真實值。

## 背景

完整的 app 運作流程與 API 逐筆解析見 `references/app-flow-analysis.md`——只有在需要擴充功能
（例如查其他模組、調整查詢欄位）或排查 API 行為時才需要讀它，一般查詢不必載入。
