---
name: tw-trading-agents
description: '台股多 agent 投研分析（TradingAgents 方法論 + FinMind 資料）。當使用者要對某檔台股做完整的多面向投資分析、想要買賣決策建議、或提到「分析台股 2330」「TradingAgents 台股」「台股投研報告」「幫我研究 台積電 該不該買」時觸發。觸發於股票代碼（如 2330、2317、2454）或公司名（台積電、鴻海、聯發科）且要求深入分析或投資決策的情境。Triggers on "tw-trading-agents", "台股投研", "台股 TradingAgents".'
compatibility: Needs uv and network access to FinMind. Parallel sub-agents preferred; platforms without sub-agents (e.g. Copilot CLI) fall back to sequential execution with no loss of analytical quality.
---

# Taiwan-stock TradingAgents (multi-agent)

Applies the TradingAgents methodology (arXiv:2412.20138) — "simulate a real
brokerage's division of labor + bull/bear debate + tiered risk control" — to the
Taiwan market, with **FinMind** as the data source. Several analyst sub-agents
analyze different dimensions in parallel; their reports flow through a bull/bear
debate, a trader decision, and a risk-management review, after which the
orchestrator (you) assembles an investment-research report containing a
Buy/Sell/Hold call, a suggested position size, and a risk disclaimer.

## Cross-CLI compatibility (important)

This skill uses a **fan-out / fan-in** pattern: each phase dispatches multiple
sub-agents in parallel; each sub-agent analyzes its slice and **returns its
report as its final output**; the orchestrator collects the reports and moves to
the next phase. Sub-agents never communicate with each other directly.

- The mechanism for dispatching sub-agents is **platform-specific** — see
  `references/platform-tools.md`. The one-line rule:
  - **Parallel when possible** (Claude Code: multiple `Task` calls in one
    message; Codex: `spawn_agent`);
  - **Sequential when not** (Gemini / Copilot: the main model plays each role in
    turn, producing the same structured intermediate output).
- No team abstraction, no shared config file, no message bus, no manual
  shutdown — sub-agents "return as output."

## Architecture

```
Orchestrator (you) — doubles as Research Manager (debate facilitator) + Fund Manager (final call)
├─ Phase 1  Analyst team (4 sub-agents)
│   ├─ Fundamentals   monthly revenue / 3 statements / valuation
│   ├─ Technical      MA / RSI / MACD / KD
│   ├─ Chips          institutional flows / margin trading
│   └─ News-sentiment news + sentiment
├─ Phase 2  Researcher debate (2 sub-agents): bull / bear
├─ Phase 3  Trader (1 sub-agent): buy / sell / hold
├─ Phase 4  Risk team (3 sub-agents): aggressive / neutral / conservative
└─ Phase 5  Fund Manager (you): synthesize → final decision + disclaimer
```

- **Hit the API only once**: the orchestrator runs `snapshot` once before
  starting, producing one shared snapshot file for all sub-agents; analysts read
  only their slice via `slice`, never calling FinMind themselves.
- **Parallelism is the point**: dispatch all sub-agents of a phase at once (when
  the platform supports it). Phases are sequential and run one after another.

## Prerequisites

- `FINMIND_TOKEN` (600 req/hr). The script resolves it in order: `--token` flag
  → `.env` in the current dir → `.env` in the script dir → environment variable.
  The free tier (300 req/hr) also works but a token is recommended. `.env` is
  gitignored.
- `uv` available (the script declares its dependencies via PEP 723).

Script path (always call with an absolute path):
`~/.claude/skills/tw-trading-agents/scripts/tw_trading_data.py`

## Workflow

### Step 0 — Resolve the target and take a snapshot

Parse the stock id from the user's message (convert a company name to its id
first, e.g. 台積電 → 2330). Then run this **exactly once**:

```bash
uv run ~/.claude/skills/tw-trading-agents/scripts/tw_trading_data.py snapshot -s <stock_id>
```

Note the `Snapshot written: <path>` from the output. This `<path>` must be passed
to every sub-agent. If the output contains `Warning: no price data`, the id may
be wrong — confirm with the user before continuing.

### Step 1 — Phase 1: dispatch 4 analysts in parallel

Following the platform mechanism in `references/platform-tools.md`, **dispatch
all 4 sub-agents below at once** (play them sequentially if the platform has no
parallelism). Use this prompt template for each (an English prompt is more
stable); replace `{SECTION}` and the focus per role:

```
You are a Taiwan-stock {ROLE} analyst.

## Data (already fetched — do NOT call any API)
Run this to read your slice of the shared snapshot:
  uv run ~/.claude/skills/tw-trading-agents/scripts/tw_trading_data.py slice --file "{SNAPSHOT_PATH}" --section {SECTION}

## Task
Analyze ONLY your dimension. Cite concrete numbers from the slice.
{ROLE_SPECIFIC_FOCUS}

## Output — return this as your final response (the orchestrator will collect it)
### {ROLE} analysis: {stock_id}
- Signal: bullish / bearish / neutral
- Key findings (each backed by a number): ...
- Risks / concerns: ...
- Score for this dimension: 1 (very bearish) ~ 5 (very bullish)
```

The four analysts differ as follows:

| ROLE | SECTION | ROLE_SPECIFIC_FOCUS |
|---|---|---|
| Fundamentals | `fundamental` | Monthly revenue YoY momentum, gross/operating margin trends, EPS growth, debt structure, operating cash-flow quality, PER position within its historical range |
| Technical | `technical` | MA bull/bear alignment, RSI overbought/oversold, MACD and KD signals, distance to 60-day high/low, volume changes |
| Chips | `chips` | Net buy/sell direction and divergence of foreign / investment-trust / dealer over the last 20 days; margin-balance and short-balance trends as a proxy for retail sentiment |
| News-sentiment | `news` | Recent-month positive/negative news tilt, major events/themes. The slice provides a **list of headlines with links**; open the **3–5 most relevant links and read their full text** before judging sentiment |

> News-sentiment note: the "do NOT call any API" line in the prompt template
> refers only to the **FinMind data layer**. The news analyst **may and should**
> use the platform's web-fetch tool (see `references/platform-tools.md`) to open
> the news links listed in the slice and read the article bodies, and may use
> web search to supplement recent news. The other three analysts use their slice
> only and fetch nothing else.

### Step 2 — Phase 2: bull/bear debate

After collecting the 4 analyst reports, put the **four summaries** into the bull
and bear prompts and dispatch both in parallel. Each may only strengthen its own
side:

```
Below are the four analyst reports:
{ANALYST_REPORTS}

Build the strongest possible {BULLISH|BEARISH} case for {stock_id}, grounded in the
analysts' numbers. Acknowledge the opposing view's strongest point, then rebut it.

## Output — return this as your final response
### {Bullish|Bearish} case: {stock_id}
- Core arguments (3-5, each with data)
- Opponent's strongest counterpoint + my rebuttal
- Conclusion and confidence (0-100%)
```

You act as the **Research Manager** synthesizing both sides. If the two
conclusions are sharply opposed (e.g. both confidences > 70%), you **may
optionally** run one more round: feed each side the opponent's first-round case
as context and ask for a targeted rebuttal (at most 1 round, to avoid an endless
loop).

### Step 3 — Phase 3: trader decision (dispatch 1 sub-agent)

```
Inputs:
- Analyst reports: {ANALYST_REPORTS}
- Bull case: {BULL}
- Bear case: {BEAR}

Weigh both sides and decide.

## Output — return this as your final response
### Trader decision: {stock_id}
- Rating: buy / hold / sell
- Confidence: 0-100%
- Core reasons (3)
- Suggested entry range / stop-loss reference
```

### Step 4 — Phase 4: risk review (dispatch 3 perspectives in parallel)

Put the trader decision into the three risk sub-agent prompts and dispatch in
parallel:

```
Trader decision: {TRADER_DECISION}
From a {aggressive|neutral|conservative} risk stance, critique this decision:
position-size ceiling, what could go wrong, and whether you endorse / modify / reject it.

## Output — return this as your final response
### Risk ({stance}): position-size ceiling X%, main risks, endorse or not
```

### Step 5 — Phase 5: Fund Manager synthesis (you, no extra sub-agent)

Synthesize the three risk views and make the final call: adopt or adjust the
trader's rating, decide the suggested position (usually a compromise of the
three, with the conservative view as the position ceiling), and give entry/exit
and stop-loss references.

### Step 6 — Deliver the final report

The final report is user-facing and **must be in Traditional Chinese**:

```markdown
# 台股投研報告：{公司} ({代碼})  — {快照日期}

## 最終決策
- 評級：買進 / 持有 / 賣出
- 信心度：XX%
- 建議部位：佔投資組合 X%（保守上限 Y%）
- 參考進場區間 / 停損位

## 分析師摘要
### 基本面 / 技術面 / 籌碼面 / 新聞情緒面（各一段，附關鍵數字）

## 多空辯論
- 看多核心 vs 看空核心 → 辯論結論

## 風控評估
- 激進 / 中性 / 保守 三方意見 → 部位上限與主要風險

## 關鍵風險與未知

> ⚠️ 免責聲明：本報告由 AI agent 依 FinMind 公開資料自動產生，僅供研究參考，
> 不構成任何投資建議或要約。資料可能有誤差或延遲，AI 分析亦可能有誤。
> 投資有風險，請自行查證並承擔後果。
```

## Rules

- **Parallelism is the point**: dispatch all sub-agents of a phase at once when
  the platform supports it (see `references/platform-tools.md`); on platforms
  without parallelism, play each role sequentially, producing the same
  structured intermediate output.
- **Fetch data only once**: only the orchestrator runs `snapshot` (Step 0);
  sub-agents always read via `slice` and must not call the FinMind API
  themselves (avoids rate limits and data inconsistency).
- **Numbers rule**: require every sub-agent to cite concrete numbers from the
  slice, to reduce speculation.
- **Return as output**: sub-agents return their report as their final response;
  the orchestrator collects them — do not rely on any platform-specific dispatch
  or messaging mechanism. The exact mechanism is each platform's choice.
- **Disclaimer is mandatory**: always keep the risk disclaimer at the end of the
  final report, and never phrase anything as a guaranteed profit.
- **Language**: per CLAUDE.md, communicate with the user and write the final
  report in **Traditional Chinese**; sub-agent prompt templates and intermediate
  outputs are in English for stability.
```
