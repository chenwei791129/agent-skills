---
name: finmind
description: "Query Taiwan stock financial reports via FinMind API. Use when: (1) analyzing Taiwan company financials (income statement, balance sheet, cash flow), (2) checking monthly revenue trends, (3) looking up dividend history or PER/PBR/yield, (4) comparing company financial metrics, (5) any question about Taiwan stock fundamentals. Trigger on stock codes like 2330, 2317, or company names like TSMC, Hon Hai, MediaTek."
---

# FinMind Taiwan Financial Report Query

Query Taiwan listed/OTC company financial data via FinMind REST API. Covers income statements, balance sheets, cash flows, monthly revenue, dividends, PER/PBR, and stock prices.

## Prerequisites

**Optional**: Set `FINMIND_TOKEN` for higher rate limits (600 req/hr vs 300 req/hr without token).

Register at https://finmindtrade.com/ to get a free token, then:
```bash
export FINMIND_TOKEN="your-token-here"
```

## Available Commands

All commands are run via:
```bash
uv run ~/.claude/skills/finmind/scripts/finmind_query.py <command> [options]
```

### Financial Data Commands

| Command | Description | Key Fields |
|---------|-------------|------------|
| `income` | Comprehensive Income Statement | EPS, revenue, gross profit, operating income, net income |
| `balance-sheet` | Balance Sheet | total assets, liabilities, equity, cash |
| `cash-flow` | Cash Flow Statement | operating/investing/financing cash flows |
| `revenue` | Monthly Revenue | monthly revenue, YoY growth, MoM growth |
| `dividend` | Dividend Policy | cash dividend, stock dividend |
| `per` | PER / PBR / Dividend Yield | price-to-earnings, price-to-book, yield |
| `price` | Daily Stock Price | open, high, low, close, volume |

### Utility Commands

| Command | Description |
|---------|-------------|
| `datasets` | List all available FinMind datasets |
| `translate --dataset <name>` | Show Chinese-English field name mapping |

## Date Range Guidelines

**IMPORTANT**: Choose `--start` dynamically based on today's date and the analysis goal. Do NOT hardcode dates from examples — calculate them relative to the current date.

| Analysis Goal | Recommended --start | Reasoning |
|--------------|---------------------|-----------|
| Recent quarterly financials | 2 years ago (e.g. today minus 2Y) | Captures ~8 quarters for trend analysis |
| Monthly revenue trend | 1 year ago | 12 months shows seasonal patterns |
| Dividend history | 5 years ago | Enough to assess dividend growth stability |
| PER/PBR valuation | 3 months ago with `--limit 30` | Recent trading days for current valuation |
| Stock price | 1-3 months ago with `--limit 20` | Recent price action |
| Full fundamental deep-dive | 3 years ago | Comprehensive multi-year trend |

Example: if today is 2026-04-06, use `--start 2024-04-06` for 2-year income analysis, not a fixed date.

## Usage Examples

### Query income statement (recent 2 years)
```bash
uv run ~/.claude/skills/finmind/scripts/finmind_query.py income -s 2330 --start <2-years-ago>
```

### Query balance sheet with row limit
```bash
uv run ~/.claude/skills/finmind/scripts/finmind_query.py balance-sheet -s 2330 --start <2-years-ago> --limit 20
```

### Query monthly revenue (recent 1 year)
```bash
uv run ~/.claude/skills/finmind/scripts/finmind_query.py revenue -s 2317 --start <1-year-ago>
```

### Query PER/PBR/yield (recent)
```bash
uv run ~/.claude/skills/finmind/scripts/finmind_query.py per -s 2330 --start <3-months-ago> --limit 30
```

### Output as JSON (for programmatic processing)
```bash
uv run ~/.claude/skills/finmind/scripts/finmind_query.py income -s 2330 --start <2-years-ago> --format json
```

### Translate field names
```bash
uv run ~/.claude/skills/finmind/scripts/finmind_query.py translate --dataset TaiwanStockFinancialStatements
```

## Common Arguments

| Argument | Description |
|----------|-------------|
| `--stock`, `-s` | Stock ID (e.g. 2330) — **required** for data commands |
| `--start` | Start date YYYY-MM-DD — **required** for data commands |
| `--end` | End date YYYY-MM-DD (default: today) |
| `--format`, `-f` | Output format: `table` (default) or `json` |
| `--token` | API token (overrides `FINMIND_TOKEN` env var) |
| `--limit`, `-l` | Limit number of rows returned |

## Common Stock Codes

| Code | Company | Industry |
|------|---------|----------|
| 2330 | TSMC (台積電) | Semiconductor |
| 2317 | Hon Hai / Foxconn (鴻海) | Electronics Manufacturing |
| 2454 | MediaTek (聯發科) | IC Design |
| 2308 | Delta Electronics (台達電) | Power Supplies |
| 2881 | Fubon FHC (富邦金) | Financial Holding |
| 2882 | Cathay FHC (國泰金) | Financial Holding |
| 2891 | CTBC FHC (中信金) | Financial Holding |
| 2886 | Mega FHC (兆豐金) | Financial Holding |
| 2412 | Chunghwa Telecom (中華電) | Telecom |
| 1301 | Formosa Plastics (台塑) | Petrochemical |
| 2303 | UMC (聯電) | Semiconductor |
| 3711 | ASE Technology (日月光投控) | Semiconductor Packaging |
| 2002 | China Steel (中鋼) | Steel |
| 1216 | Uni-President (統一) | Food |
| 2382 | Quanta Computer (廣達) | Server / Cloud |

## Analysis Patterns

Use these query combinations for common analysis scenarios:

### Full Fundamental Analysis
```bash
# Run these 3 commands in parallel (use --start <3-years-ago>):
uv run ~/.claude/skills/finmind/scripts/finmind_query.py income -s 2330 --start <3-years-ago>
uv run ~/.claude/skills/finmind/scripts/finmind_query.py balance-sheet -s 2330 --start <3-years-ago>
uv run ~/.claude/skills/finmind/scripts/finmind_query.py cash-flow -s 2330 --start <3-years-ago>
```

### Revenue Momentum Tracking
```bash
uv run ~/.claude/skills/finmind/scripts/finmind_query.py revenue -s 2330 --start <1-year-ago>
```

### Dividend Investment Assessment
```bash
uv run ~/.claude/skills/finmind/scripts/finmind_query.py dividend -s 2330 --start <5-years-ago>
uv run ~/.claude/skills/finmind/scripts/finmind_query.py per -s 2330 --start <3-months-ago> --limit 30
```

### Quick Valuation Check
```bash
uv run ~/.claude/skills/finmind/scripts/finmind_query.py per -s 2330 --start <3-months-ago> --limit 10
uv run ~/.claude/skills/finmind/scripts/finmind_query.py price -s 2330 --start <3-months-ago> --limit 10
```

### Multi-Company Comparison
```bash
# Compare revenue of TSMC vs UMC:
uv run ~/.claude/skills/finmind/scripts/finmind_query.py revenue -s 2330 --start <1-year-ago>
uv run ~/.claude/skills/finmind/scripts/finmind_query.py revenue -s 2303 --start <1-year-ago>
```

## Rate Limits

| Tier | Limit | How to Get |
|------|-------|------------|
| No token | 300 requests/hour | Default |
| With token | 600 requests/hour | Register at https://finmindtrade.com/ |

When rate-limited (HTTP 402), the script will suggest setting a token.

## Data Coverage

- **Income Statement**: from 1990-03-01
- **Balance Sheet**: from 2011-12-01
- **Cash Flow Statement**: from 2008-06-01
- **Monthly Revenue**: from 2002-02-01
- **Dividend Policy**: from 2005-05-01
- **PER/PBR/Yield**: varies
- **Stock Price**: varies

Data is updated daily by FinMind.
