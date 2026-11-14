# BTC Cent Forecast

Forecast Bitcoin's price 4 hours ahead, 12 times over 48 hours
(make.fun competition `btc-cent-forecast-01`).

## What the program does

`main.py` reads every `*.in` case file (one JSON object with 4320
one-minute BTC closes, the last equal to the checkpoint close) and
writes one `*.out` file per case with a single forecast price.

The forecast is the last close adjusted by a small, clipped blend of
damped short-horizon momentum (an EWMA of recent per-minute returns,
heavily shrunk) and mild mean reversion toward the medium-term
average (up to the last 1440 closes). The total adjustment is clipped
to ±1%, so the guess stays close to persistence while tilting toward
the honest median estimate. The program is deterministic, uses only
the Python standard library, and never crashes: any invalid case
falls back to the last close (or 1.0) and still gets a valid output
file.

## How to run locally

```sh
MAKEFUN_INPUT_DIR=/path/to/cases MAKEFUN_OUTPUT_DIR=/path/to/out python3 main.py
```

Without those variables it reads `/input/` and writes `/output/`,
matching the judging sandbox. Each `<id>.in` produces `<id>.out`
containing exactly `{"forecasts":[{"case":"<id>","price":<guess>}]}`.
