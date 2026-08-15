# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Rule-based long/flat backtest over OHLCV candles.

Reads a JSON payload (stdin or --input file) shaped like:
{
  "candles": [{"t": 1700000000, "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}, ...],
  "strategy": {"type": "sma_crossover", "fast": 10, "slow": 30}
           or {"type": "rsi", "period": 14, "oversold": 30, "overbought": 70},
  "initial_capital": 10000,
  "fee_rate": 0.0,
  "bars_per_year": 365
}

Simulation-only: long-only, no leverage/shorting, flat position earns 0. This
is the derived-metrics boundary called out in CLAUDE.md's context-mode
convention -- callers pass raw candle JSON in and get back only the reduced
metrics JSON below, never a bar-by-bar trace.

Prints a single JSON object of metrics to stdout:
{cagr, sharpe, max_drawdown, win_rate, trade_count, final_equity,
 total_return_pct}
"""
from __future__ import annotations

import argparse
import json
import math
import sys


def sma(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = []
    for i in range(len(values)):
        if i + 1 < period:
            out.append(None)
        else:
            out.append(sum(values[i + 1 - period : i + 1]) / period)
    return out


def rsi(closes: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(closes)
    if len(closes) <= period:
        return out
    gains = [max(closes[i] - closes[i - 1], 0.0) for i in range(1, len(closes))]
    losses = [max(closes[i - 1] - closes[i], 0.0) for i in range(1, len(closes))]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rs = avg_gain / avg_loss if avg_loss != 0 else math.inf
        out[i + 1] = 100 - (100 / (1 + rs))
    return out


def signals_sma_crossover(closes: list[float], fast: int, slow: int) -> list[int]:
    fast_sma = sma(closes, fast)
    slow_sma = sma(closes, slow)
    return [
        1 if (f is not None and s is not None and f > s) else 0
        for f, s in zip(fast_sma, slow_sma)
    ]


def signals_rsi(closes: list[float], period: int, oversold: float, overbought: float) -> list[int]:
    values = rsi(closes, period)
    signals: list[int] = []
    state = 0
    for v in values:
        if v is not None:
            if v < oversold:
                state = 1
            elif v > overbought:
                state = 0
        signals.append(state)
    return signals


def build_signals(closes: list[float], strategy: dict) -> list[int]:
    kind = strategy.get("type")
    if kind == "sma_crossover":
        return signals_sma_crossover(closes, int(strategy["fast"]), int(strategy["slow"]))
    if kind == "rsi":
        return signals_rsi(
            closes,
            int(strategy.get("period", 14)),
            float(strategy.get("oversold", 30)),
            float(strategy.get("overbought", 70)),
        )
    raise ValueError(f"unknown strategy type: {kind!r}")


def run_backtest(payload: dict) -> dict:
    candles = payload["candles"]
    if len(candles) < 2:
        raise ValueError("need at least 2 candles")
    closes = [float(c["c"]) for c in candles]
    strategy = payload["strategy"]
    initial_capital = float(payload.get("initial_capital", 10000))
    fee_rate = float(payload.get("fee_rate", 0.0))
    bars_per_year = float(payload.get("bars_per_year", 365))

    signals = build_signals(closes, strategy)

    equity = initial_capital
    equity_curve = [equity]
    position = 0
    trade_returns: list[float] = []
    entry_price = 0.0
    trade_count = 0

    for i in range(1, len(closes)):
        sig = signals[i - 1] if signals[i - 1] is not None else 0
        prev_close, cur_close = closes[i - 1], closes[i]

        if sig == 1 and position == 0:
            position = 1
            entry_price = prev_close
            equity *= 1 - fee_rate
            trade_count += 1
        elif sig == 0 and position == 1:
            trade_returns.append(cur_close / entry_price - 1)
            position = 0
            equity *= 1 - fee_rate

        if position == 1:
            equity *= cur_close / prev_close

        equity_curve.append(equity)

    if position == 1:
        trade_returns.append(closes[-1] / entry_price - 1)

    bar_returns = [
        equity_curve[i] / equity_curve[i - 1] - 1
        for i in range(1, len(equity_curve))
        if equity_curve[i - 1] != 0
    ]
    mean_ret = sum(bar_returns) / len(bar_returns) if bar_returns else 0.0
    variance = (
        sum((r - mean_ret) ** 2 for r in bar_returns) / len(bar_returns)
        if bar_returns
        else 0.0
    )
    std_ret = math.sqrt(variance)
    sharpe = (mean_ret / std_ret * math.sqrt(bars_per_year)) if std_ret > 0 else 0.0

    peak = equity_curve[0]
    max_drawdown = 0.0
    for v in equity_curve:
        peak = max(peak, v)
        if peak > 0:
            max_drawdown = min(max_drawdown, v / peak - 1)

    total_periods = len(closes) - 1
    total_return = equity_curve[-1] / equity_curve[0] - 1
    years = total_periods / bars_per_year if bars_per_year > 0 else 0
    cagr = (
        (equity_curve[-1] / equity_curve[0]) ** (1 / years) - 1
        if years > 0 and equity_curve[-1] > 0
        else 0.0
    )

    wins = sum(1 for r in trade_returns if r > 0)
    win_rate = wins / len(trade_returns) if trade_returns else 0.0

    return {
        "cagr": cagr,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "win_rate": win_rate,
        "trade_count": trade_count,
        "final_equity": equity_curve[-1],
        "total_return_pct": total_return * 100,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="Path to JSON payload; reads stdin if omitted")
    args = parser.parse_args()

    raw = open(args.input).read() if args.input else sys.stdin.read()
    payload = json.loads(raw)
    print(json.dumps(run_backtest(payload), indent=2))


if __name__ == "__main__":
    main()
