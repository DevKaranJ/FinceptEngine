# Adding Indicators to FinceptEngine

**Project:** FinceptEngine — Self-Improving Multi-Paradigm Quantitative Trading Engine  
**Scope:** How to add new technical indicators and signal wrappers without breaking the existing modular structure.

---

## 1. Core Principle — Keep Indicators Separate

Your project follows a **Lego-block** design. Each indicator family lives in its **own file**. Never mix all indicators into one chunk.

| Indicator Family | File | Responsibility |
|------------------|------|----------------|
| Family A — Classical Technical | `trading_engine/indicators/technical.py` | EMA, SMA, RSI, ATR, Bollinger Bands, MACD, Supertrend, Donchian, Pivots |
| Family B — Statistical / Quant | `trading_engine/indicators/statistical.py` | Rolling Z-Score, Hurst, Volatility Percentile, Linear Regression Slope, Relative Strength |
| Family C — Price Structure | `trading_engine/indicators/structure.py` | PDH/PDL/PDC, Opening Range, Dynamic Trendlines, FVG, Order Blocks, Liquidity Sweeps |
| Family D — Orderflow / Volume | `trading_engine/indicators/orderflow.py` | VWAP, RVOL, Volume Profile (POC/VAH/VAL), CVD, Footprint Imbalance, Iceberg |

Each signal family mirrors this in `trading_engine/signals/`:
- `technical_signals.py`
- `statistical_signals.py`
- `structure_signals.py`
- `orderflow_signals.py`

**Rule:** Add an indicator to the file matching its family. Add its signal wrapper to the matching `*_signals.py` file.

---

## 2. Install pandas-ta (Already Done)

`pandas-ta` (130+ indicators) is already installed in your `.venv` and listed in `trading_engine/requirements.txt`:

```ini
pandas-ta>=0.3.14b0
```

To verify it works:

```bash
source .venv/bin/activate
python3 -c "import pandas_ta as pta; print('pandas-ta OK')"
```

You can use `pandas-ta` as a **reference implementation** or drop-in for standard indicators, while keeping your own pure-pandas versions for deterministic, version-independent behavior.

---

## 3. Step-by-Step: How to Add a New Indicator

### Step 1: Pick the Right File

Decide which family the indicator belongs to:

- Trend/momentum/volatility → `indicators/technical.py`
- Statistical/quant/research → `indicators/statistical.py`
- Price action/structure → `indicators/structure.py`
- Volume/orderflow/microstructure → `indicators/orderflow.py`

### Step 2: Write the Indicator Function

Follow the existing pattern in that file. Key requirements:

1. **Input:** Accept pandas `Series` (or DataFrame columns) for OHLCV data.
2. **Output:** Return a pandas `Series` (single output) or a `dict` of Series (multi-output like Bollinger Bands / MACD).
3. **Zero look-ahead:** Only use rows up to the current bar (`t <= T`). Use `shift(1)` for previous-bar references, rolling windows that include only current/past bars. **Never use `shift(-1)` or future data.**
4. **Validation:** Raise `ValueError` if `length < 1` or invalid parameters.
5. **Type hints:** Use `pd.Series` and `dict[str, pd.Series]` annotations.

### Example: Adding a New Indicator to `technical.py`

```python
def hma(close: pd.Series, length: int = 20) -> pd.Series:
    """Hull Moving Average — pure pandas, zero look-ahead."""
    if length < 1:
        raise ValueError("hma length must be >= 1")
    # WMA = weighted moving average; HMA = WMA(2*WMA(n/2) - WMA(n)), sqrt(n)
    half = max(1, length // 2)
    sqrt_len = max(1, int(round(length ** 0.5)))
    wma_half = close.rolling(window=half, min_periods=half).mean()
    wma_full = close.rolling(window=length, min_periods=length).mean()
    raw = 2 * wma_half - wma_full
    return raw.rolling(window=sqrt_len, min_periods=sqrt_len).mean()
```

### Step 3: Add to `__all__`

If the file has an `__all__` list, add your function name to it so it's explicitly exported.

### Step 4: Write a Matching Signal Wrapper

In the corresponding `*_signals.py` file, add a `True`/`False` condition:

```python
def hma_bullish(row: Any, hma_col: str = "hma", close_col: str = "close") -> bool:
    """True when close is above HMA (bullish bias)."""
    return _f(row, close_col) > _f(row, hma_col)
```

Keep signals simple — they only read the current row's already-computed indicator values. No future data.

### Step 5: Write a Test

Add a test in `trading_engine/tests/test_phase2_indicators_signals.py` (or a new test file) covering:

- Basic math correctness
- Zero look-ahead (truncating input must not change earlier outputs)
- Output shape / value ranges
- Signal wrapper returns correct `True`/`False`

### Step 6: Run the Tests

```bash
source .venv/bin/activate
python3 -m pytest trading_engine/tests/test_phase2_indicators_signals.py -v
```

All tests must pass before considering the indicator done.

---

## 4. Step-by-Step: How to Add a New Signal

Signals live in `trading_engine/signals/`. Each family has its own file.

1. Open the matching `*_signals.py` file.
2. Add a function that takes a `row` (pandas Series or dict) and returns `bool`.
3. Use the existing `_f(row, name)` helper to read values safely.
4. Add the function name to the file's `__all__` list.
5. Write a test in `tests/test_phase2_indicators_signals.py`.
6. Run pytest.

Example signal pattern:

```python
def rsi_above_threshold(row: Any, rsi_col: str = "rsi", threshold: float = 50.0) -> bool:
    """True when RSI is above a threshold."""
    return _f(row, rsi_col) > threshold
```

---

## 5. Zero Look-Ahead Rule (Mandatory)

This is the most important rule in the project (AGENTS.md Hard Constraint #1):

> **Indicators/transforms/backtests must use only past data (`t <= T`). Prevent future leakage across train/validation splits.**

### What IS allowed:
- `shift(1)` — previous bar (past)
- `rolling(window=n).mean()` — current bar + past bars only
- `expanding().mean()` — current bar + past bars only
- `ewm(...).mean()` — exponential moving average over past bars

### What is NOT allowed:
- `shift(-1)` — next bar (future)
- Any computation that looks at rows after the current bar
- Using future data to compute the current bar's indicator value

### How to test for look-ahead:
```python
# Full calculation
full = ema(df["close"], length=14)
# Truncated calculation (only first 30 bars)
truncated = ema(df["close"].iloc[:30], length=14)
# First 30 outputs must be identical
pd.testing.assert_series_equal(full.iloc[:30], truncated, check_names=False)
```

---

## 6. Using pandas-ta Alongside Your Own Code

`pandas-ta` is available as `import pandas_ta as pta`. You can use it two ways:

### Option A: Use pandas-ta directly in your indicator file
```python
import pandas_ta as pta

def rsi_pta(close: pd.Series, length: int = 14) -> pd.Series:
    return pta.rsi(close=close, length=length)
```

### Option B: Use it as a reference / cross-check
Implement your own pure-pandas version (for determinism), then compare against `pandas-ta` in tests to ensure they match.

**Recommendation:** Keep your own pure-pandas implementations as the default (deterministic, version-independent), and use `pandas-ta` optionally for cross-checking or for indicators you don't want to implement from scratch.

---

## 7. File Organization Checklist

Before you consider a new indicator "done," confirm:

- [ ] Indicator function added to the correct `indicators/*.py` family file
- [ ] Function added to `__all__` (if present)
- [ ] Zero look-ahead verified (no `shift(-1)`, no future rows)
- [ ] Input validation (`length < 1` raises `ValueError`)
- [ ] Matching signal wrapper added to the correct `signals/*_signals.py` file
- [ ] Signal added to `__all__`
- [ ] Test written in `tests/test_phase2_indicators_signals.py`
- [ ] `pytest` passes (all tests green)
- [ ] Documentation updated (this file or `AGENTS.md` if rules change)

---

## 8. Running the Full Test Suite

From the repo root:

```bash
source .venv/bin/activate
python3 -m pytest trading_engine/tests/test_phase2_indicators_signals.py -v
```

To run a single test:

```bash
source .venv/bin/activate
python3 -m pytest trading_engine/tests/test_phase2_indicators_signals.py::test_rsi_range_and_bounds -v
```

---

## 9. What NOT to Do

- ❌ Don't put all indicators in one file — keep families separate
- ❌ Don't modify Phase 1 files (`config.py`, `data/clock.py`, `memory/db.py`, etc.)
- ❌ Don't use `shift(-1)` or any future data in indicators
- ❌ Don't skip the zero look-ahead test
- ❌ Don't let AI approve its own strategy — that's Phase 4's Validation Gate

---

## 10. Quick Reference — Indicator Function Signature

```python
def my_indicator(
    close: pd.Series,          # required price series
    high: pd.Series = None,    # optional
    low: pd.Series = None,     # optional
    length: int = 14,          # parameter with default
) -> pd.Series:                # or dict[str, pd.Series] for multi-output
```

---

**Maintainers:** When adding indicators, update `CHANGELOG.md` and `DEVELOPMENT_PLAN_AND_TODO.md` per AGENTS.md Rule 2 & 4.
