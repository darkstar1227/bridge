# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Screen TWSE-listed stocks for sustained institutional (三大法人) net buying
without a large recent price runup.

Walks backward from --end-date over TWSE's public open-data endpoints
(no auth needed):
  - T86 (`/rwd/zh/fund/T86`): daily 三大法人買賣超股數 per stock
  - MI_INDEX (`/rwd/zh/afterTrading/MI_INDEX`): daily bulk closing prices

Collects `--days` trading days of T86 data ending at --end-date, plus one
more trading day immediately before that window as the price baseline.
A stock qualifies when its net-buy is positive on every one of those
`--days` days (or `--min-positive-days` of them) AND its close-to-close
change from the baseline day to the last window day is <= --max-change
percent.

TWSE (上市) only -- TPEX's (上櫃) open API has no historical-date query
(always returns the latest trading day), so 上櫃 stocks are not covered.

Prints a single JSON object to stdout:
{
  "dates": [...],            # the `--days` trading dates used, oldest first
  "baseline_date": "...",    # trading date used for the baseline close
  "market": "TWSE",
  "results": [
    {"code", "name", "net_buy_3d", "net_buy_by_day": [...],
     "baseline_close", "last_close", "change_pct"},
    ...
  ]  # sorted by net_buy_3d descending
}
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timedelta

T86_URL = "https://www.twse.com.tw/rwd/zh/fund/T86?date={date}&selectType=ALL&response=json"
MI_INDEX_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={date}&type=ALLBUT0999&response=json"


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def num(s) -> float:
    if s is None:
        return 0.0
    s = str(s).replace(",", "").strip()
    if s in ("", "--", "X"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def walk_back_trading_dates(end_date: datetime, count: int, max_lookback: int = 30) -> list[str]:
    """Return `count` TWSE trading dates (YYYYMMDD, oldest first) at or before end_date."""
    found: list[str] = []
    cur = end_date
    checked = 0
    while len(found) < count and checked < max_lookback:
        ds = cur.strftime("%Y%m%d")
        try:
            j = fetch_json(T86_URL.format(date=ds))
            if j.get("stat") == "OK" and j.get("data"):
                found.append(ds)
        except Exception:
            pass
        cur -= timedelta(days=1)
        checked += 1
    found.reverse()
    return found


def load_t86_net_buy(date: str) -> dict[str, dict]:
    j = fetch_json(T86_URL.format(date=date))
    fields = j["fields"]
    ic = fields.index("證券代號")
    iname = fields.index("證券名稱")
    inet = fields.index("三大法人買賣超股數")
    out = {}
    for row in j["data"]:
        code = row[ic].strip()
        out[code] = {"name": row[iname].strip(), "net_buy": num(row[inet])}
    return out


def load_close_prices(date: str) -> dict[str, float]:
    j = fetch_json(MI_INDEX_URL.format(date=date))
    out: dict[str, float] = {}
    for t in j.get("tables", []):
        fields = t.get("fields")
        if fields and "收盤價" in fields and "證券代號" in fields:
            ic = fields.index("證券代號")
            icl = fields.index("收盤價")
            for row in t["data"]:
                out[row[ic].strip()] = num(row[icl])
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--end-date", default=datetime.now().strftime("%Y%m%d"), help="YYYYMMDD, defaults to today")
    parser.add_argument("--days", type=int, default=3, help="trading-day window size")
    parser.add_argument("--max-change", type=float, default=5.0, help="max close-to-close %% change allowed over the window")
    parser.add_argument("--min-positive-days", type=int, default=None, help="days within the window that must show net buying (default: all days)")
    parser.add_argument("--include-etf", action="store_true", help="include 00-prefixed ETF/fund codes (excluded by default)")
    args = parser.parse_args()

    min_positive = args.min_positive_days if args.min_positive_days is not None else args.days

    end_dt = datetime.strptime(args.end_date, "%Y%m%d")
    window_dates = walk_back_trading_dates(end_dt, args.days)
    if len(window_dates) < args.days:
        print(json.dumps({"error": f"only found {len(window_dates)} trading dates at/before {args.end_date}"}))
        sys.exit(1)

    baseline_candidates = walk_back_trading_dates(
        datetime.strptime(window_dates[0], "%Y%m%d") - timedelta(days=1), 1
    )
    if not baseline_candidates:
        print(json.dumps({"error": "could not find a baseline trading date before the window"}))
        sys.exit(1)
    baseline_date = baseline_candidates[0]

    per_day = [load_t86_net_buy(d) for d in window_dates]
    baseline_close = load_close_prices(baseline_date)
    last_close = load_close_prices(window_dates[-1])

    codes = set(per_day[0])
    for d in per_day[1:]:
        codes &= set(d)

    results = []
    for code in codes:
        if not args.include_etf and code.startswith("00"):
            continue
        by_day = [per_day[i][code]["net_buy"] for i in range(args.days)]
        positive_days = sum(1 for v in by_day if v > 0)
        if positive_days < min_positive:
            continue
        p0 = baseline_close.get(code)
        p1 = last_close.get(code)
        if not p0 or not p1:
            continue
        change_pct = (p1 - p0) / p0 * 100
        if change_pct > args.max_change:
            continue
        results.append({
            "code": code,
            "name": per_day[0][code]["name"],
            "net_buy_3d": sum(by_day),
            "net_buy_by_day": by_day,
            "baseline_close": p0,
            "last_close": p1,
            "change_pct": change_pct,
        })

    results.sort(key=lambda r: -r["net_buy_3d"])

    print(json.dumps({
        "market": "TWSE",
        "dates": window_dates,
        "baseline_date": baseline_date,
        "results": results,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
