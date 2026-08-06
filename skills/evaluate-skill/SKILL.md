---
name: evaluate-skill
description: 'Evaluate whether a Claude Code skill improves task outcomes through repeated paired experiments, blind LLM judging, statistical tests, and a self-contained HTML report. Use when the user asks to benchmark, compare, validate, or quantify the effectiveness of a skill. This is a costly explicit-only workflow.'
disable-model-invocation: true
---

# Evaluate Skill

以相同案例重複執行「啟用 skill」與「未啟用 skill」兩組 Claude Code 配對實驗，再由獨立模型盲評，產生自包含 HTML report 與 machine-readable JSON sidecar。

## 模型用量與執行前確認

每個案例、每輪會呼叫 Claude Code 三次（with skill、without skill、judge）。總呼叫數為 `案例數 × rounds × 3`，可能產生顯著模型用量。執行前先向使用者確認 model、judge model 與 rounds，並告知總呼叫數；建議先用 1 case、1 round 驗證配置。

此 skill 設為 `disable-model-invocation: true`，只能由使用者明確呼叫，避免自動啟動昂貴實驗。

## 案例格式

案例檔為 JSON：

```json
{
  "name": "example-suite",
  "cases": [
    {
      "id": "case-1",
      "prompt": "Complete the requested task.",
      "rubric": "Score correctness, completeness, and adherence to the fixture requirements.",
      "fixture": "fixtures/case-1"
    }
  ]
}
```

`id`、`prompt`、`rubric` 必填且不得為空，`id` 不可重複。`fixture` 選填，路徑相對於案例 JSON；每組 arm/round 都會複製到獨立暫存 workspace，原始 fixture 不會被修改。可複製 `${CLAUDE_SKILL_DIR}/examples/cases.example.json` 作為起點。

### 會改變外部狀態的 CLI 案例

若受測 skill 會透過 CLI 執行 deploy、publish、send、upload、delete，或修改 repository、cloud、ticket、database 等外部狀態，一律使用 **describe-only** 案例，不得要求 agent 真正執行操作：

- `prompt` 必須要求 agent 只說明「會怎麼做」以及會建議哪些命令，並明示不得執行命令、不得使用 tools、不得修改檔案或外部狀態。
- `rubric` 必須將任何實際 tool use、workspace／external-state mutation，或聲稱已完成操作視為嚴重缺失。
- 使用 synthetic placeholders，不提供可直接操作真實資源的識別資訊或 credentials。

這項規則必須寫進每個相關 case；evaluator 不會根據關鍵字猜測案例風險。可參考 example suite 中的 `external-cli-procedure`。

## 執行

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/evaluate_skill.py \
  --skill /path/to/skill \
  --cases /path/to/cases.json \
  --claude-bin cx \
  --model claude-sonnet-5 \
  --effort high \
  --rounds 5 \
  --judge-model claude-fable-5 \
  --judge-effort high \
  --output skill-evaluation.html
```

`--claude-bin` 預設為環境變數 `CLAUDE_BIN`，未設定時使用 `claude`；CLI 旗標優先。launcher 必須支援 Claude Code 的 `--print`、JSON output、model、effort 與其他實驗旗標。腳本只會以 `--version` 與 `--help` 執行零費用的 launcher metadata／static flag validation；Claude Code 沒有官方保證不呼叫模型的 runtime argv probe，因此 wrapper forwarding 與實際 runtime compatibility 只能由最小 smoke run 或第一個實驗 invocation 驗證。命令以 argv 直接執行，不經 shell。

其他選項：

- `--seed INTEGER`：控制 arm 執行順序、judge A/B 對調與統計抽樣，預設 `0`。
- `--keep-workspaces`：保留暫存 workspace 供除錯；預設清除。
- `--effort`、`--judge-effort`：`low`、`medium`、`high`、`xhigh` 或 `max`。

第一版採序列執行以降低 rate limit 與資源干擾。進度輸出至 stderr；stdout 僅顯示完成摘要與 report 路徑。

## 實驗界線

- 兩個 arm 都取得相同的 project-local skill tree，以維持 workspace 因果對稱；with skill arm 以 `/<skill-name>` 明確啟用，without skill arm 加上 `--disable-slash-commands`。
- 禁用 user/project/local settings、外部 MCP 與 Chrome integration，judge 也禁用 tools。候選內容中的 skill 名稱與來源路徑會先遮蔽再送 judge，但風格等間接線索仍可能洩漏身份。
- 不使用 `--dangerously-skip-permissions`；採非互動 `dontAsk` 權限模式。需要額外權限的動作會失敗並記入報告。
- 對會改變外部狀態的 CLI skill，一律使用上述 describe-only case。`dontAsk` 不是 external-state sandbox，不能取代 prompt 與 rubric 中的禁止執行條款。
- fixture 與 skill tree 拒絕 symbolic links，避免複製或 snapshot 時意外越界。fixture 不得預先包含 `.claude/skills`；evaluator 必須完全控制兩個 arm 的相同 skill baseline。
- 暫存 workspace 只用來避免 fixture 回寫與 arm 互相污染，**不是 OS-level sandbox**。Claude Code 仍可能透過獲准工具存取 workspace 外的 filesystem 或 network。只評估可信任的 skill/fixture；若需要強隔離，請在另行管理的 container、VM 或 sandbox 中執行整個 evaluator。
- 每輪記錄 response、stdout、stderr、return code、duration、CLI JSON、usage/cost（launcher 有回傳時）與 workspace changes。
- 執行失敗不重試，也不交給 judge 當作低品質答案；會標記為 failed pair。
- 文字內容與 diff 有容量上限；binary 或超限檔案只記 metadata 與 SHA-256。

## 報告版面

HTML report 使用「工程筆記本」風格（藍圖方格底、深藍描邊卡片、手寫標題字），以正體中文呈現，由上而下的閱讀順序固定為：

1. **Hero**：skill 名稱、一句話結論、執行設定 chips。
2. **分數卡**：with / without 兩組平均分與長條。
3. **一句話結論**：結論標籤對應的判讀，加上說明該標籤意義的 callout。
4. **統計數字**：平均／中位差異、95% CI、p-value、Cohen's dz、勝平敗、win rate、失敗率。
5. **Per-case 結果**表格。
6. **Judge 怎麼說**：逐 trial 的 judge rationale、偏好與信心。
7. **這次怎麼測**：模型、effort、rounds、seed、launcher 版本、總時間與總成本、workspace 變更數。
8. **完整回答**：每個 trial 的 with／without 回答與原始 trial JSON，預設收起。
9. **方法與限制**：預設收起的 details。

版面完全由 `render_html()` 從 report dict 產生，沒有手寫敘述；欄位缺漏時顯示 `n/a` 而不會中斷。所有動態內容都經過 HTML escape。字型透過 Google Fonts `@import` 載入，離線時自動退回系統字型，其餘樣式與資料都內嵌在單一 HTML 檔。

## 解讀報告

報告包含平均與中位 paired difference、with/without 平均分、win/tie/loss、Cohen's dz、seeded 95% bootstrap confidence interval，以及雙尾 paired sign-flip randomization test。

只有 `p < 0.05`、95% confidence interval 不跨 0，且 failed-pair ratio 不超過 25% 時，才標示 `significant improvement` 或 `significant regression`；其餘標示 `insufficient evidence` 或 `insufficient data due to failures`，這不代表「沒有差異」。有效 pair 少於 2 或失敗過多時不要做強結論。

LLM judge 不是客觀 ground truth。結果只描述該 suite、rounds、tested model 與 judge 設定，不代表所有任務；per-case 結果應一併檢視，避免整體平均掩蓋特定案例退步。
