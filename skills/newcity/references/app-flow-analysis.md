# Newcity 社區物業 App — 運作流程分析

本文件根據「登入 → 查看未領信件」的實際封包（請求/回應）逐筆還原，說明這個 App 的後端架構與運作方式。

- **服務主機**：`https://www.itlife.com.tw`
- **API 根路徑**：`/NewcityWebApi/api`
- **後端技術**：ASP.NET / IIS 7.5（回應 header `X-Powered-By: ASP.NET`、`Server: Microsoft-IIS/7.5`）
- **前端**：.NET MAUI（XAML）打包的 Android App（`User-Agent: Dalvik/...`、`pack=com.newcity.tw2`、命名空間 `clr-namespace:NewcityApp.Controls`）
- **範例帳號**（以下皆為去識別化示意值）：`DEMO0000001`（住戶「王小明」，社區「範例社區」`NO_COMP=1000000`，戶號 `Z9999`，住戶代號 `NO_CUST=Z9999999`）

---

## 一、核心設計：Metadata-Driven 架構

這個 App 最關鍵的特徵是 **「畫面與查詢都不寫死在前端，而是由後端下發定義」**。理解這點就理解了整個 App：

1. **UI 由後端 XAML 下發** — App 啟動時向 `AppSetting/Xaml` 索取畫面樣板（XAML 字串），前端即時解析渲染。畫面長相、點擊行為、要打哪支 API 全寫在 XAML 裡。
2. **功能模組以 `ProID` 識別** — 每個功能（未領信件、最新公告、線上繳費…）都是一個程式代號 `APP_Pxxxx`。
3. **查詢欄位與資料表由 `GetProgramSettings` 定義** — 每個 `ProID` 對應一張資料表、一組欄位 schema、查詢條件、權限，全部由後端回傳。
4. **通用查詢入口 `App/Query`** — 前端只需帶上 `proid` + 查詢條件，後端依該 `ProID` 的定義動態組 SQL 查詢回傳。

也就是說：**新增一個功能或改版面，後端改設定即可，App 不必改版。**

---

## 二、共通請求機制

每一個請求（含登入）都帶相同的 header：

| Header | 值 | 說明 |
|--------|-----|------|
| `Bearer` | `<去識別化的固定長字串>` | 裝置/連線識別 token。**登入前後都不變**，伺服器以它綁定登入後的 session 狀態。注意：沒有看到 `Set-Cookie`，身分維持完全靠這個 token。 |
| `ProID` | `APP_PA004` | 目前所在功能頁的程式代號（此次抓包停在「未領信件」頁，故全程帶 PA004）。 |
| `User-Agent` | `Dalvik/2.1.0 (... SM-S9310 ...)` | Android 裝置資訊。 |
| `Accept-Encoding` | `gzip` | 回應皆以 gzip 壓縮（`Content-Encoding: gzip`）。 |

**統一回應格式**（envelope）：
```json
{ "result": <資料>, "success": true, "info": <附加資訊>, "totalElements": <筆數>, "pageIndex": <頁碼> }
```
所有呼叫端只需先看 `success`，再取 `result`。

---

## 三、完整流程逐筆解析

下表依檔名編號（即實際發生順序）排列。可分成四個階段：**登入認證 → 首頁初始化 → 功能頁載入 → 執行查詢**。

### 階段 A：登入與身分解析

#### `[8]` 登入
```
POST /api/User/Login
Body: {"userid":"DEMO0000001","password":"********","tc":"false"}
→ {"success":true}
```
帳密驗證。回應只有成功與否，**沒有回傳任何 token** — 證明身分是綁在 header 的 `Bearer` 上，伺服器端記住「這個 Bearer 已登入為某使用者」。

#### `[9]` 取得所屬社區
```
GET /api/User/Companys?userid=DEMO0000001&isAllUser=False
→ result: [{"NO_COMP":"1000000","NM_CMPS":"範例社區", ...}]
```
一個帳號可能屬於多個社區，回傳清單。此帳號只有一個社區。

#### `[10]` 取得使用者在該社區的完整身分（關鍵）
```
GET /api/User/Token?userid=DEMO0000001&comp=1000000
→ result: {
    "NO_USER":"DEMO0000001", "NO_COMP":"1000000", "NM_CMPS":"範例社區",
    "NO_HOUSE":"Z9999", "NM_HOUSE":"1-1號1樓",
    "NO_CUST":"Z9999999", "NM_CUSTS":"王小明", ...
  }
  info: "<另一段加密字串>"
```
用 `userid + comp` 換取在該社區的住戶身分。**`NO_CUST=Z9999999` 是後續查信件的關鍵鍵值**。回應的 `info` 是一段加密內容（推測為帶社區情境的 session 憑證）。

> **這三步就是「登入」的全部**：驗證密碼 → 選社區 → 解析住戶身分。我的 `query_mail.py` 正是走這條路徑。

---

### 階段 B：首頁初始化（App 啟動載入）

#### `[11] / [12]` 取得首頁 UI 樣板（XAML）
```
GET /api/AppSetting/Xaml?name=Templates&no_comp=1000000&pack=com.newcity.tw2&v=1.2605.01
→ result: "<Root ...> ... </Root>"  (一大段 XAML)
```
回傳的 XAML 直接定義了首頁長相，內含兩個重點：
- **`<Announce>`（公告區）**：含兩個分頁「最新公告」「系統公告」。其中「最新公告」竟然**內嵌了一段 SQL（`SELECT ... FROM CO1_PU ...`）寫在 `<TabViewItem.Api>` 的 CDATA 裡**；「系統公告」則用 `ApiBuilder` 宣告要呼叫 `App/getAll?proid=APP_PA018`。
- **`<FavoriteInfos>`（我的最愛卡片）**：宣告資料來源 `Menu/GetFavoriteInfos`，並定義每張卡片的版型與紅點 Badge。
- 點擊行為用 `<my:Navigation ProID="APP_PA006" .../>` 描述 —— 點哪裡跳到哪個功能也是資料。

> 這就是 metadata-driven 的鐵證：**畫面、資料來源、甚至 SQL，都由後端字串下發。**（[12] 為 [11] 的重複請求）

#### `[13]` 首頁摘要計數
```
GET /api/Menu/Info
→ result: { "building":[{"GN_PATH":"<樓棟圖 GUID>"}], "notice":[{"count":893}], "ad":[] }
```
首頁需要的雜項：樓棟資訊、通知總數（893）、廣告。

#### `[14]` 待辦流程數
```
GET /api/Flow/GetWait?onlyTotal=true
→ {"result":0}
```
簽核/待辦流程的待處理數量，此處為 0。

#### `[15]` 取得使用者完整選單（功能樹）
```
GET /api/Menu/UserMenuAll
→ result: [ 34 個選單項目 ]
```
回傳此帳號可見的所有功能，含階層（`Parent`）、圖示、型別（`ProType`）。整個 App 的功能地圖在此（節錄）：

| 分類 (MenuID) | 子功能 | ProID | 型別 |
|---|---|---|---|
| 大樓公告 APP_SY02 | 大樓簡介 / 最新公告 / 規約辦法 | APP_PA005/PA006/PA007 | View |
| 住戶專區 APP_SY22 | 訊息通知 / 住戶資料 / 住戶條碼 / 訪客查詢 | APP_PB001/PA015/PA016/PB003 | View / MasterDetail / MobileHtml |
| **信件通知 APP_SY03** | **未領信件 / 已領信件** | **APP_PA004 / APP_PA031** | **View** |
| 繳費專區 APP_SY04 | 繳費紀錄 / 未繳查詢 / 預收款 / 線上繳費 / 線上預繳 / 繳費查詢 | APP_PC001/PC002/PC004/PC014/PC016/PC015 | View / MobileHtml |
| 公設餐飲 APP_SY05 | 公設目錄 / 消費紀錄 / 我要預約 / 點數 / 儲值 | APP_PD007/PD003/PD001/PD010/PD012 | View / Single |
| 報修交辦 APP_SY06 | 我要報修 | APP_PE001 | MasterDetail2 |
| 生活服務 APP_SY07 | 服務廠商 / 政府金融 / 交通 / 美食 / 旅遊 / 特約商店 | APP_PG001~PG005,PG009 | View |

`ProType` 決定該功能用哪種畫面樣式渲染（`View` 列表、`MasterDetail` 主從、`MobileHtml` 內嵌網頁等）。

#### `[16]–[22]` 各功能的紅點數字（Badge）
```
GET /api/Menu/GetProBadges?menuid=<一個或多個 ProID>
→ {"result":{"APP_PA006":95}}   等
```
首頁/選單上小紅點的數字，逐功能（或批次）查詢未讀/待處理數。實測結果：

| menuid | 數量 | 意義 |
|---|---|---|
| APP_PB001 訊息通知 | 0 | |
| **APP_PA004 未領信件** | **0** | 與後面查詢結果一致（無未領信件） |
| APP_PC002/PC014/PC016 繳費 | 0/0/0 | |
| APP_PA006 最新公告 | **95** | 有 95 則新公告 |
| APP_PE001 報修 / PD001 預約 / PG005 特約商店 | 0 | |

#### `[23]` 我的最愛卡片資料
```
GET /api/Menu/GetFavoriteInfos
→ result: [
    {"Title":"未繳金額","Text":"暫無未繳","ProID":"APP_PC002", ...},
    {"Title":"待領信件","Text":"暫無信件","ProID":"APP_PA004", ...},
    {"Title":"訊息通知","Text":"暫無通知","ProID":"APP_PB001", ...}
  ]
```
對應 `[11]` XAML 裡 `<FavoriteInfos>` 區塊要綁的資料。**這裡已直接看到「待領信件 → 暫無信件」**。

#### `[24]` 加密 SQL 直查
```
POST /api/Data/Post
Body: {"Sql":"<一大段加密 base64>","Value":null,"Pageid":null,"Field":null}
→ {"result":[]}
```
`[11]` 首頁「最新公告」分頁那段內嵌 SQL，前端把它**加密後**送到 `Data/Post` 執行（避免明文 SQL 在網路上裸奔，也避免被竄改）。這是個通用「執行後端定義之查詢」的入口。

#### `[25]` 系統公告列表
```
GET /api/App/getAll?proid=APP_PA018&YN_STOP=N&SC_ANTP=0&YN_AllHouse=Y&size=4
→ {"result":[]}
```
對應 `[11]` XAML 裡「系統公告」分頁用 `ApiBuilder` 宣告的呼叫。`App/getAll` 是另一個通用列表 API（依 `proid` + 過濾條件取資料）。

---

### 階段 C：進入「未領信件」功能頁

#### `[29]` 取得功能的程式設定（欄位 schema / 資料表 / 權限）★
```
GET /api/AppSetting/GetProgramSettings?proid=APP_PA004&PackXaml=False
→ result: {
    "pro":  [{"ProName":"未領信件","ProType":"View","TableName":"ST2_POST","ProID":"APP_PA004"}],
    "page": [{"PageID":"Head", "ClickSql":"INSERT INTO APP_RECORD ..."},
             {"PageID":"Query","Permission":"1,2,3"}],
    "field":[ ...每個欄位的定義... ],
    "permission":[{"YN_ADD":"Y","YN_DEL":"Y","YN_UPD":"Y",...}]
  }
```
這是「未領信件」功能的完整定義，是理解查詢的核心：

- **資料表**：`ST2_POST`（信件主檔）。
- **`Head` 頁欄位**（顯示用）：`LET_BARCODE` 信件條碼、`NO_POST` 郵件序號、`NM_CUST` 收件人、`DT_IN` 收件時間、`CD_POST` 信件類別、`GN_UNIT` 寄件單位、`IMG_PATH` 圖片、`LET_STATUS` 信件狀態…，每個欄位附帶顯示寬度、排序、是否上列表、甚至 join 用的 SQL（如 `CD_POST` 要 left join `SY0_CODED` 取類別名稱）。
- **`Query` 頁欄位**（查詢條件）：
  - `NO_COMP` 公司 — 預設值來自 Session。
  - `NO_CUST` 住戶 — 預設值由 SQL 取（`SELECT NO_CUST FROM SY0_USERD3 WHERE NO_COMP=... AND NO_USER=...`），確保使用者只能查到自己。
  - `LET_STATUS` 信件狀態 — `DefaultValue:"1"`（**1=未領**），可選值來自 `SY0_CODED` 的 `LET_ST` 代碼（`NO_SEQ in ('1','2')`）。
  - `DT_IN` 收件日 — 區間查詢（`QueryType:"Between"`）。
- **`ClickSql`**：點進列表時順手寫一筆 `APP_RECORD` 操作紀錄（稽核）。
- **權限**：此使用者對該功能可增刪改印匯出。

> 重點：**「未領」的定義（`LET_STATUS=1`）、要查哪張表（`ST2_POST`）、用哪個欄位限制只看自己（`NO_CUST`），全來自這支 API**，前端不寫死。

#### `[30]` 取得功能頁 XAML
```
GET /api/AppSetting/Xaml?name=APP_PA004&no_comp=1000000&...
→ {"success":false}
```
索取「未領信件」專屬的畫面樣板。此處回 `false`，代表該功能沒有自訂 XAML，App 改用 `ProType:"View"` 的**通用列表樣板**搭配 `[29]` 的欄位定義來自動排版。

#### `[31]` 取得查詢條件的預設值
```
POST /api/App/GetDefaultValues
Body: {"proid":"APP_PA004","pageid":"Query",
       "field":"NO_COMP,NO_CUST,DT_IN_b,DT_IN_e,LET_STATUS"}
→ {"result":{"NO_CUST":"Z9999999","LET_STATUS":"1"}}
```
依 `[29]` 定義的「預設值來源」實際算出值：住戶自動帶 `Z9999999`、狀態自動帶 `1`（未領）。這就是打開頁面時查詢框的預設內容。

---

### 階段 D：執行查詢（本次任務的核心 API）★★

#### `[32]` 查詢未領信件
```
POST /api/App/Query
Body: {
  "proid":"APP_PA004",
  "pageid":"Head",
  "RequestData":{"NO_CUST":"Z9999999","LET_STATUS":"1","NO_COMP":"1000000"},
  "size":15, "page":1
}
→ {"result":[], "totalElements":0, "pageIndex":1, "success":true}
```
`App/Query` 是 **通用查詢引擎**：給它 `proid`（要查哪個功能）+ `RequestData`（查詢條件）+ 分頁參數，後端依 `[29]` 該 `ProID` 的 schema 動態組 SQL、查 `ST2_POST`、回傳結果。

本次 `result` 為空、`totalElements=0` → **目前沒有未領信件**（與 `[17]` Badge=0、`[23]`「暫無信件」一致）。

> 把 `LET_STATUS` 改成 `2` 即可查「已領信件」，回傳同樣結構但帶完整欄位（`DT_IN` 收件時間、`NM_CUST` 收件人、`CD_POST` 信件類別、`NO_POST` 郵件序號、`LET_BARCODE` 條碼、`IMG_PATH` 包裹照片、`DT_OUT` 領取時間…）。

---

## 四、查詢未領信件的最短路徑

從以上流程萃取出「只為查未領信件」的必要步驟（即 `query_mail.py` 的實作）：

```
1. POST /api/User/Login            帳密 → 確認登入
2. GET  /api/User/Companys         → 取 NO_COMP（社區）
3. GET  /api/User/Token            userid+comp → 取 NO_CUST（住戶代號）
4. POST /api/App/Query             proid=APP_PA004, LET_STATUS=1,
                                    NO_CUST, NO_COMP → 未領信件清單
```
其餘請求（XAML、Menu、Badge、GetDefaultValues…）都是 App **渲染畫面**用的，對「拿資料」而言並非必要 —— 因為 `LET_STATUS=1` 這個「未領」的定義我們已從 `[29]` 得知，可直接寫進查詢。

---

## 五、安全性觀察

- **身分綁在固定 `Bearer` token**：無 Cookie、token 不輪替，且登入前就存在。等同長期有效的裝置憑證，外洩即可冒用。
- **密碼明文傳輸**：`[8]` 的 body 是明文帳密（靠 HTTPS 保護傳輸層，但 body 本身未加密）。
- **SQL 加密下發 / 回傳**：`Data/Post` 的 SQL、`User/Token` 的 `info` 都是加密字串，顯示後端有意避免明文 SQL 與憑證外露、防竄改。
- **資料隔離靠後端 SQL**：使用者只能查到自己，是靠 `[29]` 裡 `NO_CUST` 預設值的 SQL（`WHERE NO_USER=當前使用者`）限制，而非前端。但 `App/Query` 的 `RequestData` 由前端送出 `NO_CUST` —— 若後端未在伺服器端再次校驗該 `NO_CUST` 屬於登入者，理論上存在改參數查他人信件的風險（需後端驗證才能確認）。

---

## 附錄：本次涉及的 API 一覽

| 編號 | Method | Endpoint | 用途 |
|---|---|---|---|
| 8 | POST | `User/Login` | 帳密登入 |
| 9 | GET | `User/Companys` | 列出所屬社區 |
| 10 | GET | `User/Token` | 解析住戶身分（NO_CUST） |
| 11/12 | GET | `AppSetting/Xaml?name=Templates` | 首頁 UI 樣板（XAML） |
| 13 | GET | `Menu/Info` | 首頁摘要（樓棟/通知數） |
| 14 | GET | `Flow/GetWait` | 待辦流程數 |
| 15 | GET | `Menu/UserMenuAll` | 完整功能選單樹 |
| 16–22 | GET | `Menu/GetProBadges` | 各功能紅點數字 |
| 23 | GET | `Menu/GetFavoriteInfos` | 我的最愛卡片資料 |
| 24 | POST | `Data/Post` | 執行加密 SQL（首頁公告） |
| 25 | GET | `App/getAll` | 通用列表（系統公告） |
| 29 | GET | `AppSetting/GetProgramSettings` | 功能的欄位/資料表/權限定義 |
| 30 | GET | `AppSetting/Xaml?name=APP_PA004` | 功能頁專屬 XAML（此功能無，回 false） |
| 31 | POST | `App/GetDefaultValues` | 查詢條件預設值 |
| **32** | **POST** | **`App/Query`** | **通用查詢引擎（查未領信件）** |

---

## 六、點數查詢模組 `APP_PD010`（後續擴充記錄）

「社區點數」沿用同一條 `App/Query` 通用查詢路徑，只是換 `ProID` 與欄位。以下為對正式環境
（社區 `水蓮山莊`）實測的結論：

- **ProID**：`APP_PD010`（`ProName` =「點數查詢」，`ProType` = `ViewDetail` 主從）。
- **資料表**：`ST3_PADD`。
- **Head 頁（彙總）**：`DT_B` 年月、`SC_BOOK` 點數使用類別、`QT_FREE` 贈送點數、`QT_PURCH` 購買點數。
- **Body 頁「贈點有效明細」**：`NO_PO` 點數單號、`SC_CPTY` 點數類別、`DT_B` 有效起日、
  `DT_E` 有效迄日、`QT_FREE` 單筆點數、**`QT_FREEU` 剩餘點數**。剩餘點數餘額即為 Body 各列
  `QT_FREEU` 之加總。

### 查詢方式

```
POST /api/App/Query
Body: {
  "proid":"APP_PD010", "pageid":"Body",
  "RequestData":{"NO_COMP":"...","NO_CUST":"...","NO_HOUSE":"...","NO_ARCH":"...","NO_BUILD":"..."},
  "size":50, "page":1
}
→ result: [{"NO_PO":"PO...","SC_CPTY":"P1","SC_CPTY_text":"批次贈送點數",
            "DT_B":"2026/06/01","DT_E":"2026/06/30","QT_FREE":"26.00","QT_FREEU":"26.00", ...}]
```

### ⚠️ 坑：RequestData 五欄位缺一不可

與信件（`APP_PA004` 只需 `NO_CUST` + `LET_STATUS` + `NO_COMP`）不同，點數查詢的
`RequestData` **必須帶齊 `NO_COMP`、`NO_CUST`、`NO_HOUSE`、`NO_ARCH`、`NO_BUILD` 五個欄位，
拿掉任一個都會回 0 筆**（實測逐一刪除驗證）。原因：`App/GetDefaultValues`（proid=`APP_PD010`、
pageid=`Query`）對此模組回 **空物件**、不代為解析這些 Query 預設值，因此必須由 client 自行從
`User/Token` 的回應補齊（`User/Token` 已一次回傳 `NO_HOUSE`/`NO_ARCH`/`NO_BUILD`/`NO_CUST`）。

> 通則：**不同 `ProID` 模組所需的 RequestData key 欄位不同**，由各自的 `Query` 頁 schema 決定。
> 擴充新模組時，先看 `GetProgramSettings` 的 `Query` 欄位、再實測 `GetDefaultValues` 是否代解析，
> 缺的就從 `User/Token` 補齊。伺服器另會回 `*_text` 伴隨欄位（如 `SC_CPTY_text`），顯示時優先採用。

### 相鄰模組（尚未實作，僅記錄）

| ProID | 功能 | 觀察到的關鍵欄位 |
|---|---|---|
| `APP_PD012` | 儲值 | `AMT_CLUB` 儲值金額、`QT_PURCH` 購買點數、`DT_TRN` 交易日 |
| `APP_PD003` | 消費紀錄 | 公設使用紀錄（`NO_BOOK_text` 設施名）、`QT_FREE` 本筆使用、`C_QT_FREE` 累計贈點 |
