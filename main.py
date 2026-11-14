#!/usr/bin/env python3
"""BTC 4-hour-ahead forecaster for make.fun btc-cent-forecast-01.

Reads every *.in file in $MAKEFUN_INPUT_DIR (else /input/), writes one
*.out file per input in $MAKEFUN_OUTPUT_DIR (else /output/).

Each input is one case with 4320 one-minute BTC closes. The output is
exactly {"forecasts": [{"case": <id>, "price": <guess>}]}}.

Forecast: last close adjusted by a small, clipped blend of damped
short-horizon momentum and mild mean reversion toward a medium-term
average. Total adjustment is clipped to +/-1%. Deterministic, stdlib
only, no network, no clock, no randomness.

The program never crashes on a bad case: any error falls back to the
last valid close (or 1.0), and a valid output file is always written.
"""

import json
import math
import os
import sys


def _clean_prices(raw):
    """Return the list of finite positive prices, or []."""
    if not isinstance(raw, list):
        return []
    out = []
    for value in raw:
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)) and math.isfinite(value) and value > 0:
            out.append(float(value))
    return out


def _last_close(prices):
    """Last valid close, or 1.0 when no usable price exists."""
    if prices:
        return prices[-1]
    return 1.0


def _forecast(prices):
    """Honest median estimate: last close plus a small clipped adjustment."""
    last = _last_close(prices)
    if len(prices) < 2:
        return last
    # Flat series: persistence is exactly right, return the price as-is.
    if min(prices) == max(prices):
        return last

    # (a) Damped short-horizon momentum: EWMA of recent per-minute
    # returns over at most the last 120 minutes, shrunk hard so a
    # noisy burst cannot move the guess far. Each return is winsorized
    # to +/-2% so one bad tick or spike cannot dominate, and the term
    # is scaled down when little history is available so short series
    # lean on persistence instead of a handful of noisy returns.
    window = prices[-121:]
    ewma = 0.0
    alpha = 0.05
    started = False
    n_returns = 0
    for prev, cur in zip(window, window[1:]):
        ret = cur / prev - 1.0
        if ret > 0.02:
            ret = 0.02
        elif ret < -0.02:
            ret = -0.02
        n_returns += 1
        if not started:
            ewma = ret
            started = True
        else:
            ewma = alpha * ret + (1.0 - alpha) * ewma
    if started:
        reliability = min(1.0, n_returns / 60.0)
        momentum_term = ewma * 240.0 * 0.15 * reliability
    else:
        momentum_term = 0.0

    # (b) Mild mean reversion toward the medium-term average (at most
    # the last 1440 closes, i.e. 24 hours).
    lookback = prices[-1440:]
    sma = sum(lookback) / len(lookback)
    reversion_term = (sma - last) / last * 0.05

    adjustment = momentum_term + reversion_term
    if adjustment > 0.01:
        adjustment = 0.01
    elif adjustment < -0.01:
        adjustment = -0.01

    guess = last * (1.0 + adjustment)
    if not math.isfinite(guess) or guess <= 0:
        return last
    if guess >= 10000000.0:
        return 9999999.0
    return guess


def _case_id(payload, stem):
    """Extract the case id from the payload, falling back to the filename."""
    try:
        case = payload.get("case") if isinstance(payload, dict) else None
        if isinstance(case, str) and case:
            return case
        if isinstance(case, dict):
            cid = case.get("id")
            if isinstance(cid, str) and cid:
                return cid
            if isinstance(cid, (int, float)) and math.isfinite(cid):
                return str(cid)
        if isinstance(case, (int, float)) and math.isfinite(case):
            return str(case)
    except Exception:
        pass
    return stem


def _prices_from_payload(payload):
    """Extract the price series from a case payload, or []."""
    try:
        if not isinstance(payload, dict):
            return []
        markets = payload.get("markets")
        if isinstance(markets, list) and markets:
            series = markets[0]
            if isinstance(series, dict):
                return _clean_prices(series.get("prices"))
        # Tolerate a flat "prices" key if present.
        return _clean_prices(payload.get("prices"))
    except Exception:
        return []


def _process_file(in_path, out_path, stem):
    """Read one case, write one valid output file. Never raises."""
    case_id = stem
    guess = 1.0
    try:
        with open(in_path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        case_id = _case_id(payload, stem)
        prices = _prices_from_payload(payload)
        try:
            guess = _forecast(prices)
        except Exception:
            guess = _last_close(prices)
    except Exception:
        # Bad JSON, unreadable file, wrong shape: fall back to 1.0
        # with the filename stem as the case id, still a valid file.
        try:
            guess = 1.0
        except Exception:
            guess = 1.0
    if not isinstance(guess, float):
        try:
            guess = float(guess)
        except Exception:
            guess = 1.0
    if not math.isfinite(guess) or guess <= 0:
        guess = 1.0
    if guess >= 10000000.0:
        guess = 9999999.0
    payload_out = {"forecasts": [{"case": case_id, "price": guess}]}
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload_out, fh, separators=(",", ":"))
        fh.write("\n")


def main():
    input_dir = os.environ.get("MAKEFUN_INPUT_DIR") or "/input/"
    output_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output/"
    try:
        os.makedirs(output_dir, exist_ok=True)
    except Exception:
        return 0
    try:
        names = sorted(os.listdir(input_dir))
    except Exception:
        return 0
    for name in names:
        if not name.endswith(".in"):
            continue
        stem = name[:-3]
        in_path = os.path.join(input_dir, name)
        out_path = os.path.join(output_dir, stem + ".out")
        try:
            if not os.path.isfile(in_path):
                continue
        except Exception:
            continue
        try:
            _process_file(in_path, out_path, stem)
        except Exception:
            # Last-resort fallback: always leave a valid output file.
            try:
                with open(out_path, "w", encoding="utf-8") as fh:
                    json.dump(
                        {"forecasts": [{"case": stem, "price": 1.0}]},
                        fh,
                        separators=(",", ":"),
                    )
                    fh.write("\n")
            except Exception:
                pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
