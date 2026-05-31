#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["requests", "python-dotenv"]
# ///

"""
Taiwan-stock data collector for the tw-trading-agents skill.

Builds a single consolidated snapshot of one Taiwan stock from the FinMind API
(price + technical indicators, fundamentals, valuation, chips, news) so that a
team of analyst agents can each read its own slice without re-hitting the API.

FINMIND_TOKEN resolution order (first non-empty wins):
  1. --token CLI flag
  2. .env in the current working directory
  3. .env in this script's directory
  4. FINMIND_TOKEN environment variable

Usage:
  uv run tw_trading_data.py snapshot -s 2330
  uv run tw_trading_data.py snapshot -s 2330 --months 18 --outdir ./runs
  uv run tw_trading_data.py slice --file <snapshot.json> --section technical
  uv run tw_trading_data.py slice --file <snapshot.json> --section fundamental
  uv run tw_trading_data.py slice --file <snapshot.json> --section chips
  uv run tw_trading_data.py slice --file <snapshot.json> --section news
"""

import argparse
import json
import os
import signal
import sys
from datetime import date, timedelta

import requests
from dotenv import dotenv_values

API_BASE = "https://api.finmindtrade.com/api/v4"


def resolve_token(cli_token=None):
    """Resolve FINMIND_TOKEN. First non-empty source wins, in order:
    --token flag, cwd/.env, script-dir/.env, then the environment variable.
    `.env` files are read without mutating os.environ.
    """
    if cli_token:
        return cli_token
    script_dir = os.path.dirname(os.path.abspath(__file__))
    for env_path in (
        os.path.join(os.getcwd(), ".env"),
        os.path.join(script_dir, ".env"),
    ):
        if os.path.isfile(env_path):
            token = dotenv_values(env_path).get("FINMIND_TOKEN")
            if token:
                return token
    return os.environ.get("FINMIND_TOKEN", "")


# Candidate FinMind `type` names per pivoted financial-statement metric. The
# first key present in a period wins; this keeps us robust to FinMind naming.
INCOME_KEYS = {
    "Revenue": ["Revenue"],
    "GrossProfit": ["GrossProfit"],
    "OperatingIncome": ["OperatingIncome"],
    "PreTaxIncome": ["IncomeBeforeIncomeTax", "PreTaxIncome"],
    "NetIncome": ["IncomeAfterTaxes", "NetIncome", "ProfitAfterTax"],
    "EPS": ["EPS"],
}
BALANCE_KEYS = {
    "TotalAssets": ["TotalAssets"],
    "TotalLiabilities": ["TotalLiabilities", "Liabilities"],
    "Equity": ["Equity", "TotalEquity", "StockholdersEquity"],
    "CurrentAssets": ["CurrentAssets"],
    "CurrentLiabilities": ["CurrentLiabilities"],
}
CASHFLOW_KEYS = {
    "OperatingCashFlow": [
        "CashFlowsFromOperatingActivities",
        "CashProvidedByOperatingActivities",
        "NetCashProvidedByOperatingActivities",
    ],
    "InvestingCashFlow": ["CashFlowsFromInvestingActivities"],
    "FinancingCashFlow": ["CashFlowsFromFinancingActivities"],
}


# --------------------------------------------------------------------------- #
# Signal handling
# --------------------------------------------------------------------------- #
def _handle_sigterm(signum, frame):
    sys.exit(128 + signum)


# --------------------------------------------------------------------------- #
# FinMind API access
# --------------------------------------------------------------------------- #
def _api_get(endpoint, params=None, token=""):
    """Send a GET request to the FinMind API with unified error handling."""
    if params is None:
        params = {}
    if token:
        params["token"] = token

    try:
        resp = requests.get(f"{API_BASE}/{endpoint}", params=params, timeout=30)
    except requests.exceptions.Timeout:
        print("Error: request timed out after 30 seconds.", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        print("Error: unable to connect to FinMind API.", file=sys.stderr)
        sys.exit(1)

    if resp.status_code == 402:
        print(
            "Error: rate limit exceeded. Set FINMIND_TOKEN env var or use "
            "--token for higher limits (600 req/hr).",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError:
        print(f"Error: FinMind API returned HTTP {resp.status_code}.", file=sys.stderr)
        sys.exit(1)

    return resp.json()


def fetch_data(dataset, token, data_id=None, start_date=None, end_date=None):
    """Fetch one dataset and return its `data` list (empty list on no data)."""
    params = {"dataset": dataset}
    if data_id is not None:
        params["data_id"] = data_id
    if start_date is not None:
        params["start_date"] = start_date
    if end_date is not None:
        params["end_date"] = end_date

    result = _api_get("data", params=params, token=token)
    if result.get("status") != 200:
        # Non-fatal: a single missing dataset should not abort the whole
        # snapshot. Warn and continue with empty data.
        print(
            f"Warning: dataset {dataset} returned status "
            f"{result.get('status')}: {result.get('msg', 'unknown')}",
            file=sys.stderr,
        )
        return []
    return result.get("data", []) or []


# --------------------------------------------------------------------------- #
# Numeric helpers
# --------------------------------------------------------------------------- #
def _f(value):
    """Best-effort float conversion; returns None on failure."""
    try:
        if value in (None, "", "None"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value, ndigits=2):
    return round(value, ndigits) if isinstance(value, (int, float)) else value


def sma(values, n):
    if len(values) < n:
        return None
    return sum(values[-n:]) / n


def ema_series(values, n):
    """Return the full EMA series for `values` (seeded with the first value)."""
    if not values:
        return []
    k = 2 / (n + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def rsi(values, n=14):
    if len(values) <= n:
        return None
    gains, losses = [], []
    for i in range(1, len(values)):
        diff = values[i] - values[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    # Wilder's smoothing.
    avg_gain = sum(gains[:n]) / n
    avg_loss = sum(losses[:n]) / n
    for i in range(n, len(gains)):
        avg_gain = (avg_gain * (n - 1) + gains[i]) / n
        avg_loss = (avg_loss * (n - 1) + losses[i]) / n
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(values, fast=12, slow=26, signal_n=9):
    if len(values) < slow:
        return None
    ema_fast = ema_series(values, fast)
    ema_slow = ema_series(values, slow)
    dif = [f - s for f, s in zip(ema_fast, ema_slow)]
    dea = ema_series(dif, signal_n)
    return {
        "dif": _round(dif[-1]),
        "dea": _round(dea[-1]),
        "hist": _round(dif[-1] - dea[-1]),
    }


def kd(highs, lows, closes, n=9):
    """Stochastic KD with the standard 1/3 smoothing, seeded at 50."""
    if len(closes) < n:
        return None
    k, d = 50.0, 50.0
    for i in range(n - 1, len(closes)):
        window_high = max(highs[i - n + 1 : i + 1])
        window_low = min(lows[i - n + 1 : i + 1])
        if window_high == window_low:
            rsv = 50.0
        else:
            rsv = (closes[i] - window_low) / (window_high - window_low) * 100
        k = k * 2 / 3 + rsv / 3
        d = d * 2 / 3 + k / 3
    return {"k": _round(k), "d": _round(d)}


# --------------------------------------------------------------------------- #
# Section builders
# --------------------------------------------------------------------------- #
def build_technical(rows):
    """Compute indicators from a TaiwanStockPrice list (date ascending)."""
    if not rows:
        return {}
    rows = sorted(rows, key=lambda r: r.get("date", ""))
    closes = [_f(r.get("close")) for r in rows]
    highs = [_f(r.get("max")) for r in rows]
    lows = [_f(r.get("min")) for r in rows]
    vols = [_f(r.get("Trading_Volume")) for r in rows]
    # Drop rows with missing close to keep indicator math clean.
    clean = [
        (h, l, c, v) for h, l, c, v in zip(highs, lows, closes, vols) if c is not None
    ]
    if not clean:
        return {}
    highs = [x[0] if x[0] is not None else x[2] for x in clean]
    lows = [x[1] if x[1] is not None else x[2] for x in clean]
    closes = [x[2] for x in clean]
    vols = [x[3] for x in clean if x[3] is not None]

    high_60 = max(closes[-60:]) if len(closes) >= 1 else None
    low_60 = min(closes[-60:]) if len(closes) >= 1 else None
    latest_close = closes[-1]

    indicators = {
        "latest_close": _round(latest_close),
        "ma5": _round(sma(closes, 5)),
        "ma10": _round(sma(closes, 10)),
        "ma20": _round(sma(closes, 20)),
        "ma60": _round(sma(closes, 60)),
        "rsi14": _round(rsi(closes, 14)),
        "macd": macd(closes),
        "kd": kd(highs, lows, closes, 9),
        "vol_ma5": _round(sma(vols, 5)) if vols else None,
        "vol_ma20": _round(sma(vols, 20)) if vols else None,
        "high_60d": _round(high_60),
        "low_60d": _round(low_60),
    }
    if high_60 and latest_close is not None:
        indicators["pct_from_high_60d"] = _round((latest_close / high_60 - 1) * 100)
    if low_60 and latest_close is not None:
        indicators["pct_from_low_60d"] = _round((latest_close / low_60 - 1) * 100)

    recent = []
    for r in rows[-20:]:
        recent.append(
            {
                "date": r.get("date"),
                "open": _f(r.get("open")),
                "high": _f(r.get("max")),
                "low": _f(r.get("min")),
                "close": _f(r.get("close")),
                "volume": _f(r.get("Trading_Volume")),
            }
        )
    return {"indicators": indicators, "recent_prices": recent}


def _pivot_statement(rows, key_map):
    """Pivot a long-format financial statement into per-period highlights.

    FinMind returns one row per (date, type, value). We group by date and pull
    the curated metrics defined in `key_map`, newest period last.
    """
    by_date = {}
    for r in rows:
        d = r.get("date")
        t = r.get("type")
        if d is None or t is None:
            continue
        by_date.setdefault(d, {})[t] = _f(r.get("value"))

    periods = []
    for d in sorted(by_date):
        raw = by_date[d]
        period = {"date": d}
        for label, candidates in key_map.items():
            value = None
            for c in candidates:
                if c in raw and raw[c] is not None:
                    value = raw[c]
                    break
            period[label] = value
        periods.append(period)
    return periods


def build_revenue(rows):
    """Monthly revenue with YoY / MoM growth."""
    if not rows:
        return {}
    rows = sorted(
        rows, key=lambda r: (r.get("revenue_year", 0), r.get("revenue_month", 0))
    )
    by_ym = {
        (r.get("revenue_year"), r.get("revenue_month")): _f(r.get("revenue"))
        for r in rows
    }
    out = []
    for i, r in enumerate(rows):
        y, m = r.get("revenue_year"), r.get("revenue_month")
        rev = _f(r.get("revenue"))
        prev_year = by_ym.get((y - 1, m)) if y is not None else None
        prev_month = by_ym.get((y, m - 1)) if m and m > 1 else by_ym.get((y - 1, 12))
        yoy = (rev / prev_year - 1) * 100 if rev and prev_year else None
        mom = (rev / prev_month - 1) * 100 if rev and prev_month else None
        out.append(
            {
                "year": y,
                "month": m,
                "revenue": rev,
                "yoy_pct": _round(yoy),
                "mom_pct": _round(mom),
            }
        )
    return {"recent": out[-18:]}


def build_valuation(per_rows, dividend_rows):
    out = {}
    if per_rows:
        per_rows = sorted(per_rows, key=lambda r: r.get("date", ""))
        latest = per_rows[-1]
        out["latest"] = {
            "date": latest.get("date"),
            "PER": _f(latest.get("PER")),
            "PBR": _f(latest.get("PBR")),
            "dividend_yield": _f(latest.get("dividend_yield")),
        }
        pers = [_f(r.get("PER")) for r in per_rows if _f(r.get("PER"))]
        if pers:
            out["per_min"] = _round(min(pers))
            out["per_max"] = _round(max(pers))
            out["per_avg"] = _round(sum(pers) / len(pers))
    if dividend_rows:
        dividend_rows = sorted(dividend_rows, key=lambda r: r.get("date", ""))
        out["dividend"] = [
            {
                "date": r.get("date"),
                "cash": _f(r.get("CashEarningsDistribution"))
                or _f(r.get("CashExDividendTradingDate")),
                "stock": _f(r.get("StockEarningsDistribution")),
            }
            for r in dividend_rows[-6:]
        ]
    return out


def build_chips(inst_rows, margin_rows, window=20):
    out = {}
    if inst_rows:
        inst_rows = sorted(inst_rows, key=lambda r: r.get("date", ""))
        dates = sorted({r.get("date") for r in inst_rows})[-window:]
        net_by_name = {}
        for r in inst_rows:
            if r.get("date") not in dates:
                continue
            name = r.get("name", "Unknown")
            net = (_f(r.get("buy")) or 0) - (_f(r.get("sell")) or 0)
            net_by_name[name] = net_by_name.get(name, 0) + net
        out["net_shares_sum"] = {k: _round(v, 0) for k, v in net_by_name.items()}
        out["window_days"] = len(dates)
        # Recent daily total net (all institutions) for trend reading.
        daily = {}
        for r in inst_rows:
            if r.get("date") not in dates:
                continue
            d = r.get("date")
            daily[d] = (
                daily.get(d, 0) + (_f(r.get("buy")) or 0) - (_f(r.get("sell")) or 0)
            )
        out["daily_total_net"] = [
            {"date": d, "net_shares": _round(daily[d], 0)} for d in sorted(daily)
        ]
    if margin_rows:
        margin_rows = sorted(margin_rows, key=lambda r: r.get("date", ""))
        out["margin_trend"] = [
            {
                "date": r.get("date"),
                "margin_balance": _f(r.get("MarginPurchaseTodayBalance")),
                "short_balance": _f(r.get("ShortSaleTodayBalance")),
            }
            for r in margin_rows[-window:]
        ]
    return out


def build_news(rows):
    if not rows:
        return {"items": []}
    rows = sorted(rows, key=lambda r: r.get("date", ""), reverse=True)
    items = [
        {
            "date": r.get("date"),
            "title": r.get("title"),
            "source": r.get("source"),
            "link": r.get("link"),
        }
        for r in rows[:25]
    ]
    return {"items": items}


# --------------------------------------------------------------------------- #
# Snapshot command
# --------------------------------------------------------------------------- #
def cmd_snapshot(args):
    token = resolve_token(args.token)
    stock_id = args.stock
    today = date.today()

    price_start = (today - timedelta(days=int(args.months * 31))).isoformat()
    # 3+ years so the trailing 18 months all have a prior-year comparison.
    revenue_start = (today - timedelta(days=365 * 3 + 60)).isoformat()
    fin_start = (today - timedelta(days=365 * 3)).isoformat()
    val_start = (today - timedelta(days=365)).isoformat()
    div_start = (today - timedelta(days=365 * 6)).isoformat()
    chips_start = (today - timedelta(days=90)).isoformat()
    news_start = (today - timedelta(days=30)).isoformat()

    # Company info (TaiwanStockInfo returns the full universe; filter locally).
    info_rows = fetch_data("TaiwanStockInfo", token)
    info = next((r for r in info_rows if r.get("stock_id") == stock_id), {})

    price = fetch_data("TaiwanStockPrice", token, stock_id, price_start)
    revenue = fetch_data("TaiwanStockMonthRevenue", token, stock_id, revenue_start)
    income = fetch_data("TaiwanStockFinancialStatements", token, stock_id, fin_start)
    balance = fetch_data("TaiwanStockBalanceSheet", token, stock_id, fin_start)
    cashflow = fetch_data("TaiwanStockCashFlowsStatement", token, stock_id, fin_start)
    per = fetch_data("TaiwanStockPER", token, stock_id, val_start)
    dividend = fetch_data("TaiwanStockDividend", token, stock_id, div_start)
    inst = fetch_data(
        "TaiwanStockInstitutionalInvestorsBuySell", token, stock_id, chips_start
    )
    margin = fetch_data(
        "TaiwanStockMarginPurchaseShortSale", token, stock_id, chips_start
    )
    news = fetch_data("TaiwanStockNews", token, stock_id, news_start)

    snapshot = {
        "stock_id": stock_id,
        "stock_name": info.get("stock_name"),
        "industry": info.get("industry_category"),
        "generated_at": today.isoformat(),
        "sections": {
            "info": {
                "stock_id": stock_id,
                "stock_name": info.get("stock_name"),
                "industry": info.get("industry_category"),
                "type": info.get("type"),
            },
            "technical": build_technical(price),
            "fundamental": {
                "revenue": build_revenue(revenue),
                "income": {"periods": _pivot_statement(income, INCOME_KEYS)[-8:]},
                "balance": {"periods": _pivot_statement(balance, BALANCE_KEYS)[-8:]},
                "cashflow": {"periods": _pivot_statement(cashflow, CASHFLOW_KEYS)[-8:]},
            },
            "valuation": build_valuation(per, dividend),
            "chips": build_chips(inst, margin),
            "news": build_news(news),
        },
    }

    outdir = args.outdir or os.path.join(
        os.getcwd(), "tw-trading-runs", f"{stock_id}_{today.strftime('%Y%m%d')}"
    )
    os.makedirs(outdir, exist_ok=True)
    out_path = os.path.join(outdir, "snapshot.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(snapshot, fh, ensure_ascii=False, indent=2)

    if not price:
        print(
            f"Warning: no price data for '{stock_id}'. Check the stock id.",
            file=sys.stderr,
        )

    name = snapshot["stock_name"] or "?"
    print(f"Snapshot written: {out_path}")
    print(f"Stock: {stock_id} {name} | industry: {snapshot['industry']}")
    print(f"Sections: {', '.join(snapshot['sections'].keys())}")


# --------------------------------------------------------------------------- #
# Slice command (render one section as markdown)
# --------------------------------------------------------------------------- #
def _kv_table(d):
    lines = ["| 指標 | 值 |", "| --- | --- |"]
    for k, v in d.items():
        lines.append(f"| {k} | {v} |")
    return "\n".join(lines)


def _rows_table(rows, columns):
    if not rows:
        return "_無資料_"
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for r in rows:
        lines.append("| " + " | ".join(str(r.get(c, "")) for c in columns) + " |")
    return "\n".join(lines)


def _render_technical(sec):
    if not sec:
        return "_無技術面資料_"
    ind = sec.get("indicators", {})
    flat = {}
    for k, v in ind.items():
        if isinstance(v, dict):
            flat[k] = ", ".join(f"{kk}={vv}" for kk, vv in v.items())
        else:
            flat[k] = v
    out = ["## 技術面指標\n", _kv_table(flat), "\n## 近 20 日價量\n"]
    out.append(
        _rows_table(
            sec.get("recent_prices", []),
            ["date", "open", "high", "low", "close", "volume"],
        )
    )
    return "\n".join(out)


def _render_fundamental(snapshot):
    sec = snapshot["sections"].get("fundamental", {})
    val = snapshot["sections"].get("valuation", {})
    info = snapshot["sections"].get("info", {})
    out = [
        f"## 公司：{info.get('stock_name')} ({info.get('stock_id')}) — {info.get('industry')}\n"
    ]
    out.append("## 月營收（近 18 月）\n")
    out.append(
        _rows_table(
            sec.get("revenue", {}).get("recent", []),
            ["year", "month", "revenue", "yoy_pct", "mom_pct"],
        )
    )
    out.append("\n## 綜合損益表（近 8 期）\n")
    out.append(
        _rows_table(
            sec.get("income", {}).get("periods", []),
            list(INCOME_KEYS.keys()) and ["date", *INCOME_KEYS.keys()],
        )
    )
    out.append("\n## 資產負債表（近 8 期）\n")
    out.append(
        _rows_table(
            sec.get("balance", {}).get("periods", []), ["date", *BALANCE_KEYS.keys()]
        )
    )
    out.append("\n## 現金流量表（近 8 期）\n")
    out.append(
        _rows_table(
            sec.get("cashflow", {}).get("periods", []), ["date", *CASHFLOW_KEYS.keys()]
        )
    )
    out.append("\n## 估值與股利\n")
    if val.get("latest"):
        out.append(_kv_table(val["latest"]))
    if val.get("per_min") is not None:
        out.append(
            f"\nPER 區間（近一年）：min {val.get('per_min')} / avg {val.get('per_avg')} / max {val.get('per_max')}"
        )
    if val.get("dividend"):
        out.append("\n股利（近 6 期）：\n")
        out.append(_rows_table(val["dividend"], ["date", "cash", "stock"]))
    return "\n".join(out)


def _render_chips(sec):
    if not sec:
        return "_無籌碼面資料_"
    out = [f"## 三大法人近 {sec.get('window_days', '?')} 日累計淨買賣（股數）\n"]
    out.append(_kv_table(sec.get("net_shares_sum", {})))
    out.append("\n## 每日法人合計淨額\n")
    out.append(_rows_table(sec.get("daily_total_net", []), ["date", "net_shares"]))
    out.append("\n## 融資融券餘額趨勢\n")
    out.append(
        _rows_table(
            sec.get("margin_trend", []), ["date", "margin_balance", "short_balance"]
        )
    )
    return "\n".join(out)


def _render_news(sec):
    items = sec.get("items", []) if sec else []
    if not items:
        return "_近期無新聞_"
    out = ["## 近期新聞\n"]
    for it in items:
        # Render the link so the news analyst can fetch the full article body.
        link = it.get("link")
        suffix = f" — {link}" if link else ""
        out.append(
            f"- [{it.get('date')}] {it.get('title')} ({it.get('source')}){suffix}"
        )
    return "\n".join(out)


def cmd_slice(args):
    try:
        with open(args.file, encoding="utf-8") as fh:
            snapshot = json.load(fh)
    except FileNotFoundError:
        print(f"Error: snapshot file not found: {args.file}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: snapshot file is not valid JSON: {args.file}", file=sys.stderr)
        sys.exit(1)

    sections = snapshot.get("sections", {})
    header = f"# {snapshot.get('stock_name')} ({snapshot.get('stock_id')}) — snapshot {snapshot.get('generated_at')}\n"

    if args.section == "technical":
        body = _render_technical(sections.get("technical", {}))
    elif args.section == "fundamental":
        body = _render_fundamental(snapshot)
    elif args.section == "chips":
        body = _render_chips(sections.get("chips", {}))
    elif args.section == "news":
        body = _render_news(sections.get("news", {}))
    elif args.section == "info":
        body = _kv_table(sections.get("info", {}))
    elif args.section == "all":
        body = json.dumps(snapshot, ensure_ascii=False, indent=2)
    else:
        print(f"Error: unknown section '{args.section}'.", file=sys.stderr)
        sys.exit(1)

    print(header)
    print(body)


# --------------------------------------------------------------------------- #
# Arg parsing
# --------------------------------------------------------------------------- #
def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--token",
        help="API token (highest priority; else .env then FINMIND_TOKEN env var)",
    )

    parser = argparse.ArgumentParser(
        description="Taiwan-stock data collector for the tw-trading-agents skill."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    snap = sub.add_parser(
        "snapshot", parents=[common], help="Build a consolidated snapshot"
    )
    snap.add_argument("--stock", "-s", required=True, help="Stock ID (e.g. 2330)")
    snap.add_argument(
        "--months", type=int, default=12, help="Price history months (default 12)"
    )
    snap.add_argument(
        "--outdir", help="Output directory (default ./tw-trading-runs/<id>_<date>)"
    )

    sl = sub.add_parser(
        "slice", parents=[common], help="Render one section of a snapshot"
    )
    sl.add_argument("--file", required=True, help="Path to snapshot.json")
    sl.add_argument(
        "--section",
        required=True,
        choices=["technical", "fundamental", "chips", "news", "info", "all"],
        help="Section to render",
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "snapshot":
        cmd_snapshot(args)
    elif args.command == "slice":
        cmd_slice(args)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _handle_sigterm)
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
