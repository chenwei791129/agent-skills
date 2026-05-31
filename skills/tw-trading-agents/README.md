# tw-trading-agents

A multi-agent Taiwan-stock investment-research skill that applies the
**TradingAgents** methodology ([arXiv:2412.20138](https://arxiv.org/abs/2412.20138))
to the Taiwan market, using **FinMind** as the data source.

Multiple analyst sub-agents analyze different dimensions in parallel; their
structured reports flow through a bull/bear debate, a trader decision, and a
risk-management review, after which the orchestrator (the main agent) assembles
a final report containing a Buy/Sell/Hold call, a suggested position size, and a
risk disclaimer.

## Design goals

1. **Faithful to the TradingAgents paper** — preserve the five-phase pipeline,
   the facilitator/fund-manager roles, and the structured-report communication
   protocol.
2. **Cross-CLI compatible** — runnable on Claude Code, Codex CLI, Gemini CLI,
   and (with sequential fallback) Copilot CLI. The skill body describes *intent*
   only; platform-specific sub-agent dispatch is mapped in
   `references/platform-tools.md`.

## Architecture

```
Orchestrator (main agent) ── doubles as Research Manager (debate facilitator) + Fund Manager (final call)
├─ Phase 1  Analyst team (4 sub-agents, parallel)
│   ├─ Fundamentals   monthly revenue / 3 statements / valuation
│   ├─ Technical      MA / RSI / MACD / KD
│   ├─ Chips          institutional flows / margin trading   (Taiwan localization)
│   └─ News-sentiment news headlines + fetched article bodies
├─ Phase 2  Researcher debate (2 sub-agents): bull / bear
├─ Phase 3  Trader (1 sub-agent): buy / sell / hold
├─ Phase 4  Risk team (3 sub-agents): aggressive / neutral / conservative
└─ Phase 5  Fund Manager (orchestrator): synthesize → final decision + disclaimer
```

## Cross-CLI model: fan-out / fan-in

The skill uses a **fan-out / fan-in** pattern: each phase dispatches multiple
sub-agents in parallel; each sub-agent analyzes its slice and **returns its
report as its final output**; the orchestrator collects the reports and moves to
the next phase. Sub-agents never talk to each other directly.

- Dispatch mechanism is platform-specific — see `references/platform-tools.md`
  (Claude Code `Task`, Codex `spawn_agent`, Gemini `@generalist`, or sequential
  fallback for CLIs without sub-agents).
- No team abstraction, no shared config file, no message bus, no manual
  shutdown — sub-agents "return as output."

The data layer (`scripts/tw_trading_data.py`, invoked via `uv run`) is
platform-agnostic and unchanged across CLIs. The orchestrator runs `snapshot`
once to produce a shared snapshot; each analyst reads only its slice via
`slice --section`, so FinMind is called exactly once per run.

The one exception is the **news-sentiment analyst**: the FinMind news dataset
(`TaiwanStockNews`) returns only headlines, sources, and links — no article body
and no sentiment score. The `news` slice therefore renders each item with its
link, and the news analyst is instructed to fetch the full text of the most
relevant 3–5 articles (via the platform's web-fetch tool) before judging
sentiment. This web fetch is not a FinMind call, so the "FinMind once per run"
guarantee still holds; the other three analysts use their slice only.

## Alignment with the TradingAgents paper

### Five-phase pipeline — fully aligned

| Paper phase (Fig. 1) | Paper content | This skill | Aligned |
|---|---|---|---|
| I. Analysts Team | 4 analysts gather data concurrently | Phase 1: 4 parallel sub-agents | ✅ |
| II. Research Team | Bull/Bear multi-round debate, facilitator decides | Phase 2: bull/bear + orchestrator as research manager + optional 1 round | ✅ |
| III. Trader | Decision from analyst + researcher input | Phase 3: trader | ✅ |
| IV. Risk Mgmt Team | Aggressive / neutral / conservative, n rounds | Phase 4: 3 risk perspectives in parallel | ✅ |
| V. Fund Manager | Review risk team → final call & execute | Phase 5: orchestrator as fund manager | ✅ |

### Communication protocol — the refactor is *closer* to the paper

Paper §4.1–4.2 explicitly **criticizes** natural-language-only / message-history
/ pool-of-information communication for causing a "telephone effect" (information
lost or corrupted as conversations lengthen). Its solution (inspired by MetaGPT)
is a **structured communication protocol**: "each role only extracts or queries
the necessary information, processes it, and **returns a completed report**";
agents query a **global state** for structured reports, and natural-language
dialogue is used **only during debates**.

| Paper design | This skill | Note |
|---|---|---|
| "returns a completed report" | Each sub-agent "returns this as its final response" with a fixed output template | Near-verbatim match |
| "only the necessary information" | `slice --section` reads only one slice; orchestrator passes only relevant reports downstream | Match |
| "query the global state" | The snapshot file is the shared global state; each agent takes its slice | Match |
| "natural language only in debates" | Only bull/bear and the risk perspectives are debate-style | Match |

The original Agent Teams version relied on `SendMessage` (message passing),
which is closer to the message-history pattern the paper warns against. The
cross-CLI refactor — sub-agents return structured reports that the orchestrator
holds and aggregates — is therefore **more faithful** to the paper's protocol,
not less.

### Known deviation (a pre-existing Taiwan localization, not from the refactor)

The paper's analyst team is **Fundamental / Sentiment (social media) / News
(macro) / Technical**. This skill uses **Fundamentals / Technical / Chips /
News-sentiment**:

| Paper analyst | This skill | Difference |
|---|---|---|
| Fundamental | Fundamentals | Same |
| Technical | Technical | Same |
| News (macro) | News-sentiment | Merged with Sentiment |
| Sentiment (social media) | — | Replaced by Chips (institutional flows / margin) |

Rationale: in Taiwan, "chips" analysis (three major institutional investors and
margin balances) is central to retail decision-making, while FinMind's social
sentiment coverage is weak. This is a defensible localization, but it diverges
from the paper's exact analyst lineup. It predates the cross-CLI refactor.

To partially recover the paper's sentiment dimension, the news-sentiment analyst
reads the full text of the most relevant news articles (see the data layer
section above) rather than judging sentiment from headlines alone.

### Minor notes

- **Debate rounds**: the paper allows n rounds decided by a facilitator; this
  skill caps extra debate at 1 round. Minor simplification, pre-existing.
- **Model tiering**: the paper uses quick-thinking models for analysts and
  deep-thinking models for researchers/traders; this skill leaves model choice
  to each CLI.

## Prerequisites

- `FINMIND_TOKEN` (600 req/hr). The script resolves it in order: `--token` flag
  → `.env` in the current dir → `.env` in the script dir → environment variable.
  The free tier (300 req/hr) also works but a token is recommended. `.env` is
  gitignored.
- `uv` available (the script declares its dependencies via PEP 723).

## Files

| Path | Role |
|---|---|
| `SKILL.md` | The skill definition (intent-level workflow, no platform tool names) |
| `references/platform-tools.md` | Per-platform sub-agent dispatch mapping |
| `scripts/tw_trading_data.py` | FinMind data layer: `snapshot` and `slice` sub-commands |

## Disclaimer

Reports produced by this skill are generated automatically by AI agents from
FinMind public data for research reference only. They are not investment advice.
Data may contain errors or delays, and AI analysis may be wrong. Investing
carries risk; verify independently and bear your own consequences.
