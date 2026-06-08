#!/usr/bin/env python3
# /// script
# dependencies = ["patchright>=1.55.0"]
# ///
"""Fetch Taiwan NDC monthly business cycle light score.

Usage:
  uv run fetch_ndc_lightscore.py --json
  uv run fetch_ndc_lightscore.py --text
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


def normalize_payload(payload: dict[str, Any], series_limit: int | None = None) -> dict[str, Any]:
    line = payload.get("line")
    if not isinstance(line, list) or not line:
        raise ValueError("NDC JSON payload missing non-empty 'line' list")

    series = []
    for item in line:
        month_raw = str(item["x"])
        score = int(item["y"])
        series.append(
            {
                "month": yyyymm_to_iso_month(month_raw),
                "roc_month_label": yyyymm_to_roc_label(month_raw),
                "score": score,
                "signal": score_to_signal(score),
            }
        )

    latest = series[-1]
    if series_limit is not None and series_limit >= 0:
        series = series[-series_limit:] if series_limit else []

    return {
        "source_url": SOURCE_URL,
        "api_url": API_URL,
        "latest": latest,
        "next_publish_at": payload.get("next"),
        "series": series,
        "fetched_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }


def fetch_payload(*, headless: bool, timeout_ms: int) -> dict[str, Any]:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=headless)
        page = browser.new_page(locale="zh-TW")
        try:
            page.goto(SOURCE_URL, wait_until="domcontentloaded", timeout=timeout_ms)
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
                API_PATH,
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


def format_text(data: dict[str, Any]) -> str:
    latest = data["latest"]
    return (
        f"國發會景氣對策信號：{latest['roc_month_label']}（{latest['month']}）\n"
        f"分數：{latest['score']} 分\n"
        f"燈號：{latest['signal']}\n"
        f"下次發布日期：{data.get('next_publish_at') or '未取得'}\n"
        f"來源：{data['source_url']}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch NDC 景氣對策信號 latest score and next publish date.")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="Output normalized JSON (default).")
    output.add_argument("--text", action="store_true", help="Output human-readable text.")
    parser.add_argument("--series-limit", type=int, default=12, help="Number of recent series rows to include; use 0 to omit.")
    parser.add_argument("--headless", action="store_true", help="Try headless Chrome. If Cloudflare blocks it, omit this flag.")
    parser.add_argument("--timeout-ms", type=int, default=60_000, help="Browser navigation/API timeout in milliseconds.")
    args = parser.parse_args(argv)

    try:
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
