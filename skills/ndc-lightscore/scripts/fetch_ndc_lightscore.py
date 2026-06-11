#!/usr/bin/env python3
# /// script
# dependencies = ["patchright>=1.55.0"]
# ///
"""Fetch Taiwan NDC monthly business cycle light score.

Usage:
  uv run fetch_ndc_lightscore.py --json
  uv run fetch_ndc_lightscore.py --text
  uv run fetch_ndc_lightscore.py --history --json --series-limit -1
  uv run fetch_ndc_lightscore.py --red-runs --min-red-length 5 --text
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any

from patchright.sync_api import TimeoutError as PlaywrightTimeoutError
from patchright.sync_api import sync_playwright

SOURCE_URL = "https://index.ndc.gov.tw/m/zh_tw/lightscore"
API_PATH = "/n/json/lightscore"
API_URL = "https://index.ndc.gov.tw/n/json/lightscore"
HISTORY_SOURCE_URL = "https://index.ndc.gov.tw/n/zh_tw/data/eco/indicators_table1"
HISTORY_API_PATH = "/n/json/data/eco/indicators"
HISTORY_API_URL = "https://index.ndc.gov.tw/n/json/data/eco/indicators"
SCORE_CODE = "SR0005"


def score_to_signal(score: int | float) -> str:
    """Map NDC score to the corresponding monitoring indicator light."""
    if score <= 16:
        return "藍燈"
    if score <= 22:
        return "黃藍燈"
    if score <= 31:
        return "綠燈"
    if score <= 37:
        return "黃紅燈"
    return "紅燈"


def yyyymm_to_iso_month(value: str) -> str:
    value = str(value).strip()
    if len(value) != 6 or not value.isdigit():
        raise ValueError(f"Unexpected YYYYMM value: {value!r}")
    return f"{value[:4]}-{value[4:6]}"


def yyyymm_to_roc_label(value: str) -> str:
    value = str(value).strip()
    year = int(value[:4]) - 1911
    month = int(value[4:6])
    return f"{year}年{month}月"


def _limit_series(series: list[dict[str, Any]], series_limit: int | None) -> list[dict[str, Any]]:
    if series_limit is None or series_limit < 0:
        return series
    return series[-series_limit:] if series_limit else []


def _normalize_score_series(raw_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    series = []
    for item in raw_items:
        score_value = item.get("y")
        if score_value is None:
            continue
        month_raw = str(item["x"])
        score = int(score_value)
        series.append(
            {
                "month": yyyymm_to_iso_month(month_raw),
                "roc_month_label": yyyymm_to_roc_label(month_raw),
                "score": score,
                "signal": score_to_signal(score),
            }
        )
    if not series:
        raise ValueError("NDC payload contains no non-null score rows")
    return series


def normalize_payload(payload: dict[str, Any], series_limit: int | None = None) -> dict[str, Any]:
    line = payload.get("line")
    if not isinstance(line, list) or not line:
        raise ValueError("NDC JSON payload missing non-empty 'line' list")

    full_series = _normalize_score_series(line)
    latest = full_series[-1]
    series = _limit_series(full_series, series_limit)

    return {
        "source_url": SOURCE_URL,
        "api_url": API_URL,
        "latest": latest,
        "next_publish_at": payload.get("next"),
        "series": series,
        "series_count": len(full_series),
        "fetched_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }


def _post_json_via_page(*, source_url: str, api_path: str, headless: bool, timeout_ms: int) -> dict[str, Any]:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=headless)
        page = browser.new_page(locale="zh-TW")
        try:
            page.goto(source_url, wait_until="domcontentloaded", timeout=timeout_ms)
            try:
                page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 15_000))
            except PlaywrightTimeoutError:
                # The API can still be queried after DOMContentLoaded; networkidle is only a nicety.
                pass

            title = page.title()
            body_text = ""
            try:
                body_text = page.locator("body").inner_text(timeout=5_000)
            except Exception:
                pass
            if "Cloudflare" in title or "被封鎖" in body_text or "been blocked" in body_text:
                raise RuntimeError(
                    "NDC page is blocked by Cloudflare. Retry with the default non-headless Chrome, "
                    "or open the page once manually in Chrome from this machine."
                )

            result = page.evaluate(
                """async (apiPath) => {
                    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
                    const res = await fetch(apiPath, {
                        method: 'POST',
                        headers: {
                            'Accept': 'application/json',
                            'X-CSRF-TOKEN': csrf
                        }
                    });
                    const text = await res.text();
                    return {status: res.status, text};
                }""",
                api_path,
            )
        finally:
            browser.close()

    status = int(result.get("status", 0))
    text = result.get("text") or ""
    if status != 200:
        raise RuntimeError(f"NDC API returned HTTP {status}: {text[:300]}")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"NDC API did not return valid JSON: {text[:300]}") from exc


def fetch_payload(*, headless: bool, timeout_ms: int) -> dict[str, Any]:
    return _post_json_via_page(
        source_url=SOURCE_URL,
        api_path=API_PATH,
        headless=headless,
        timeout_ms=timeout_ms,
    )


def fetch_history_payload(*, headless: bool, timeout_ms: int) -> dict[str, Any]:
    return _post_json_via_page(
        source_url=HISTORY_SOURCE_URL,
        api_path=HISTORY_API_PATH,
        headless=headless,
        timeout_ms=timeout_ms,
    )


def _extract_history_score_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    line = payload.get("line")
    if isinstance(line, dict):
        candidates = line.values()
    elif isinstance(line, list):
        candidates = line
    else:
        raise ValueError("NDC history payload missing 'line' collection")

    for item in candidates:
        if item.get("code") == SCORE_CODE:
            data = item.get("data")
            if not isinstance(data, list):
                raise ValueError(f"NDC history item {SCORE_CODE} missing data list")
            return data
    raise ValueError(f"NDC history payload missing score code {SCORE_CODE}")


def normalize_history_payload(payload: dict[str, Any], series_limit: int | None = None) -> dict[str, Any]:
    full_series = _normalize_score_series(_extract_history_score_items(payload))
    latest = full_series[-1]
    return {
        "source_url": HISTORY_SOURCE_URL,
        "api_url": HISTORY_API_URL,
        "latest": latest,
        "latest_date": payload.get("latest_date"),
        "series": _limit_series(full_series, series_limit),
        "series_count": len(full_series),
        "fetched_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }


def find_signal_runs(
    series: list[dict[str, Any]], *, signal: str = "紅燈", min_length: int = 5
) -> list[dict[str, Any]]:
    """Return consecutive runs of `signal` with length >= min_length."""
    runs: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []

    def flush() -> None:
        if len(current) >= min_length:
            start = current[0]
            end = current[-1]
            years = sorted({int(row["month"][:4]) for row in current})
            runs.append(
                {
                    "signal": signal,
                    "start_month": start["month"],
                    "start_roc_month_label": start["roc_month_label"],
                    "end_month": end["month"],
                    "end_roc_month_label": end["roc_month_label"],
                    "months": len(current),
                    "years": years,
                    "scores": [row["score"] for row in current],
                    "min_score": min(row["score"] for row in current),
                    "max_score": max(row["score"] for row in current),
                }
            )

    for row in series:
        if row["signal"] == signal:
            current.append(row)
        else:
            flush()
            current = []
    flush()
    return runs


def format_text(data: dict[str, Any]) -> str:
    latest = data["latest"]
    lines = [
        f"國發會景氣對策信號：{latest['roc_month_label']}（{latest['month']}）",
        f"分數：{latest['score']} 分",
        f"燈號：{latest['signal']}",
    ]
    if data.get("next_publish_at"):
        lines.append(f"下次發布日期：{data['next_publish_at']}")
    if data.get("latest_date"):
        lines.append(f"資料更新日期：{data['latest_date']}")
    lines.extend(
        [
            f"序列筆數：{data.get('series_count', len(data.get('series', [])))}",
            f"來源：{data['source_url']}",
        ]
    )
    return "\n".join(lines)


def format_red_runs_text(data: dict[str, Any]) -> str:
    runs = data.get("red_runs", [])
    min_len = data.get("red_run_min_length")
    lines = [
        f"歷史景氣燈號連續紅燈（至少 {min_len} 個月）：{len(runs)} 段",
        f"資料範圍：{data['history_range']['start_month']} ～ {data['history_range']['end_month']}，共 {data['series_count']} 筆",
    ]
    for idx, run in enumerate(runs, 1):
        years = ", ".join(str(y) for y in run["years"])
        lines.append(
            f"{idx}. {run['start_month']} ～ {run['end_month']}：連續 {run['months']} 個月，"
            f"涵蓋年份 {years}，分數 {run['min_score']}～{run['max_score']}"
        )
    lines.append(f"來源：{data['source_url']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch NDC 景氣對策信號 scores, history, and red-light runs.")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="Output normalized JSON (default).")
    output.add_argument("--text", action="store_true", help="Output human-readable text.")
    parser.add_argument("--history", action="store_true", help="Fetch full historical score series from the NDC indicators endpoint.")
    parser.add_argument("--red-runs", action="store_true", help="Analyze consecutive historical red-light runs; implies --history.")
    parser.add_argument("--min-red-length", type=int, default=5, help="Minimum consecutive red-light months for --red-runs (default: 5).")
    parser.add_argument("--series-limit", type=int, default=12, help="Number of recent series rows to include; use 0 to omit, -1 for all.")
    parser.add_argument("--headless", action="store_true", help="Try headless Chrome. If Cloudflare blocks it, omit this flag.")
    parser.add_argument("--timeout-ms", type=int, default=60_000, help="Browser navigation/API timeout in milliseconds.")
    args = parser.parse_args(argv)

    try:
        if args.min_red_length < 1:
            raise ValueError("--min-red-length must be >= 1")

        if args.history or args.red_runs:
            payload = fetch_history_payload(headless=args.headless, timeout_ms=args.timeout_ms)
            data = normalize_history_payload(payload, series_limit=args.series_limit)
            if args.red_runs:
                full_history = normalize_history_payload(payload, series_limit=-1)
                full_series = full_history["series"]
                data.update(
                    {
                        "history_range": {
                            "start_month": full_series[0]["month"],
                            "end_month": full_series[-1]["month"],
                        },
                        "red_run_min_length": args.min_red_length,
                        "red_runs": find_signal_runs(full_series, min_length=args.min_red_length),
                    }
                )
                if args.text:
                    print(format_red_runs_text(data))
                else:
                    print(json.dumps(data, ensure_ascii=False, indent=2))
            elif args.text:
                print(format_text(data))
            else:
                print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            payload = fetch_payload(headless=args.headless, timeout_ms=args.timeout_ms)
            data = normalize_payload(payload, series_limit=args.series_limit)
            if args.text:
                print(format_text(data))
            else:
                print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
