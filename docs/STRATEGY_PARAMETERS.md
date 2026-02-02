# Strategy Parameters Reference

This document is the **single source of truth** for understanding how the bot makes trading decisions. Every parameter that affects trade selection, sizing, and filtering is documented here.

## Quick Reference

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `EXTREME_YES_MIN_PRICE` | 0.03 | Skip YES trades under 3¢ |
| `EXTREME_YES_MAX_PRICE` | 0.12 | Only buy YES if price < 12¢ |
| `EXTREME_NO_MIN_PRICE` | 0.03 | Skip NO trades under 3¢ |
| `EXTREME_NO_MIN_YES_PRICE` | 0.50 | Only buy NO if YES > 50¢ |
| `MIN_EDGE_THRESHOLD` | 0.10 | Require 10% edge minimum |
| `PREFER_NO_ON_RANGE` | true | Prioritize NO bets on range markets |
| `SKIP_YES_ON_THRESHOLD` | false | Skip YES bets on threshold markets |
| `PREFER_NWS_ONLY` | true | Use NWS data exclusively |

---

## Trade Entry Thresholds

### `EXTREME_YES_MIN_PRICE`
**Default:** `0.03` (3¢)

**What it does:** Skips any YES trade priced below this threshold.

**Why it exists:** Backtesting showed that sub-3¢ trades had a **0% win rate** with 28 trades and -$70 loss. These "cheap" opportunities are traps - they're cheap because they almost never happen.

**Trade-off:**
- Higher value = Fewer trades, but higher quality
- Lower value = More trades, but includes low-probability traps

**Backtest impact:** Setting this to 0.03 improved P&L from -$38 to +$32.

---

### `EXTREME_NO_MIN_PRICE`
**Default:** `0.03` (3¢)

**What it does:** Skips any NO trade priced below this threshold.

**Why it exists:** Same logic as YES minimum - if YES is at 97%+, NO costs only 3¢. These extreme prices are traps just like cheap YES trades. The market is correctly pricing rare events as unlikely.

**Trade-off:**
- Higher value = Fewer NO trades, but avoids trap trades
- Lower value = More NO trades, but includes low-probability traps

---

### `EXTREME_YES_MAX_PRICE`
**Default:** `0.12` (12¢)

**What it does:** Only considers YES trades if the price is below this threshold.

**Why it exists:** The extreme value strategy relies on asymmetric payoffs. At 12¢:
- Risk: $0.12 per share
- Reward: $0.88 per share (if YES wins)
- Payoff ratio: 7.3:1

At higher prices, the payoff ratio decreases and the strategy loses its edge.

**Trade-off:**
- Higher value (e.g., 0.15) = More opportunities, but lower payoff ratios
- Lower value (e.g., 0.08) = Fewer opportunities, but better risk/reward

---

### `EXTREME_YES_IDEAL_PRICE`
**Default:** `0.08` (8¢)

**What it does:** Prices at or below this get larger position sizes.

**Why it exists:** Better prices deserve more capital. At 8¢, the payoff ratio is 11.5:1.

---

### `EXTREME_NO_MIN_YES_PRICE`
**Default:** `0.50` (50¢)

**What it does:** Only considers NO trades if the YES price is above this threshold.

**Why it exists:** When YES is overpriced at 50¢+, NO becomes cheap at 50¢ or less:
- NO cost: $0.50 or less
- NO reward: $0.50 or more
- Payoff ratio: 1:1 or better

**Trade-off:**
- Higher value (e.g., 0.60) = Fewer NO trades, but cheaper NO prices
- Lower value (e.g., 0.40) = More NO trades, but worse payoff ratios

---

### `EXTREME_NO_IDEAL_YES_PRICE`
**Default:** `0.60` (60¢)

**What it does:** YES prices at or above this trigger larger NO position sizes.

**Why it exists:** When YES is at 60¢, NO costs only 40¢ with a 1.5:1 payoff ratio.

---

## Edge & Probability

### `MIN_EDGE_THRESHOLD`
**Default:** `0.10` (10%)

**What it does:** Requires at least 10% edge before taking a trade.

**Edge calculation:**
```
edge = fair_probability - market_price
```

For example:
- Market price: 8¢ (0.08)
- Fair probability (from forecast): 25% (0.25)
- Edge: 0.25 - 0.08 = 0.17 (17%) ✓ Exceeds 10%

**Why it exists:** Ensures we only trade when we have a meaningful information advantage. Lower thresholds lead to more trades but with less conviction.

**Trade-off:**
- Higher value (e.g., 0.15) = Fewer trades, higher conviction
- Lower value (e.g., 0.05) = More trades, but some may be noise

---

### Forecast Standard Deviation (hardcoded: 7.0°F)

**Location:** `bot/connectors/weather.py`

**What it does:** Controls how confident the probability calculation is about forecasts.

**How it works:** Uses a normal distribution to calculate P(temp > threshold):
```python
probability = normal_cdf((forecast - threshold) / std_dev)
```

With std_dev = 7.0°F:
- Forecast 7°F above threshold → ~84% probability
- Forecast equals threshold → ~50% probability
- Forecast 7°F below threshold → ~16% probability

**Why 7.0°F:** Backtesting showed actual forecast errors of 6-10°F. The original 4.0°F was too optimistic, leading to 97% fair probability estimates that had near-0% actual win rates.

**Trade-off:**
- Higher std_dev = More conservative probabilities, fewer trades
- Lower std_dev = More confident probabilities, but may be overconfident

---

## Trade Type Preferences

### `PREFER_NO_ON_RANGE`
**Default:** `true`

**What it does:** Prioritizes NO bets on range markets when sorting opportunities.

**Market types:**
- **Range markets** (`-B` in market ID): "Will temp be 48-49°?"
- **Threshold markets** (`-T` in market ID): "Will temp be >58°?"

**Why it exists:** Backtesting showed NO on range markets had:
- 22.2% win rate
- +144% ROI

This is the highest-performing trade category.

**How it works:** Signals are sorted by:
1. Trade type priority (NO+RANGE first, then NO+THRESHOLD, then YES)
2. Expected value within each priority tier

---

### `SKIP_YES_ON_THRESHOLD`
**Default:** `false`

**What it does:** Completely skips YES bets on threshold markets.

**Why it exists:** YES threshold bets had the worst performance:
- 8.3% win rate
- -53.3% ROI

The probability calculations for threshold markets have been systematically inaccurate.

**Trade-off:**
- `true` = Eliminates worst category, improves ROI from +37% to +71%
- `false` = More diversification, occasional YES threshold wins

**Recommendation:** Enable (`true`) based on backtesting results.

---

## Weather Data Source

### `PREFER_NWS_ONLY`
**Default:** `true`

**What it does:** Uses National Weather Service data exclusively when available.

**Why it exists:** Kalshi uses NWS station data for market resolution. Using the same data source ensures our probability estimates align with actual outcomes.

**Data source comparison (observed):**
| Source | LA Min Temp (Jan 31) |
|--------|---------------------|
| WeatherAPI | 58.1°F |
| NWS (KLAX) | 57.2°F |
| Kalshi Resolution | Used NWS |

The 1-2°F difference caused systematic losses on close threshold markets.

---

### `ENABLE_ENSEMBLE_MODELS`
**Default:** `false`

**What it does:** When true, averages forecasts from multiple APIs (NWS, WeatherAPI, OpenWeather).

**Why disabled:** Ensemble averaging introduced upward bias since non-NWS sources reported temps 1-2°F higher than NWS stations.

**When to enable:** If you want broader data coverage and are willing to accept some data source mismatch.

---

## Position Sizing

### `EXTREME_MIN_POSITION`
**Default:** `1.50` ($1.50)

**What it does:** Minimum dollar amount per trade.

---

### `EXTREME_MAX_POSITION`
**Default:** `2.50` ($2.50)

**What it does:** Standard position size for good opportunities.

---

### `EXTREME_AGGRESSIVE_MAX`
**Default:** `5.00` ($5.00)

**What it does:** Maximum position size for excellent opportunities (very cheap prices with high edge).

---

### Position Sizing Logic

**v2.5.2: INVERTED logic** - bet MORE on proven winners, LESS on traps.

```
For YES trades (based on win rate data):
  price < 5¢  → $1.50 (min) - TRAP (0% historical win rate)
  price ≤ 8¢  → $2.50 (max) - good win rate + great payoff
  price ≤ 10¢ → $2.50 (max) - decent
  price ≤ 12¢ → $5.00 (aggressive) - BEST win rate (20%)
  else        → $1.50 (min) - lower payoff ratio

For NO trades (based on NO price = 1 - YES price):
  NO < 10¢  → $1.50 (min) - TRAP (YES >90%)
  NO < 30¢  → $1.50 (min) - risky
  NO < 40¢  → $2.50 (max) - good sweet spot
  NO < 45¢  → $5.00 (aggressive) - best balance
  else      → $2.50 (max) - moderate payoff
```

**Why inverted?** Analysis showed the old logic was backwards:
- Cheap trades (<5¢) had 0% win rate but got $5 positions
- 10-12¢ trades had 20% win rate but got only $1.88 positions

---

## Risk Management

### `MAX_TRADES_PER_DAY`
**Default:** `25`

**What it does:** Hard cap on daily trade count.

**Why it exists:** Prevents overtrading and excessive exposure.

---

### `MAX_TRADES_PER_SCAN`
**Default:** `10`

**What it does:** Maximum trades to execute in a single scan cycle.

---

### `MAX_TRADES_PER_CITY`
**Default:** `2`

**What it does:** Limits exposure to any single city's weather.

**Why it exists:** Diversification. If our Denver forecast is wrong, we don't want 10 Denver trades all losing.

---

### `MAX_DAILY_EXPOSURE_PCT`
**Default:** `5.0` (5%)

**What it does:** Maximum percentage of bankroll at risk per day.

**Example:** With $1000 bankroll, max daily exposure = $50.

---

### `BANKROLL`
**Default:** `1000.0`

**What it does:** Total trading capital. Used for exposure calculations.

---

## Timing

### `SCAN_INTERVAL_HOURS`
**Default:** `4`

**What it does:** How often the bot scans for new opportunities.

---

### `RESOLUTION_CHECK_HOURS`
**Default:** `1`

**What it does:** How often the bot checks for resolved markets to update P&L.

---

## Decision Flow Summary

When the bot scans for trades, it follows this logic:

```
1. Fetch all weather markets from Kalshi

2. For each market, check YES opportunity:
   ├── Is price < EXTREME_YES_MAX_PRICE (12¢)?
   │   └── No → Skip
   ├── Is price ≥ EXTREME_YES_MIN_PRICE (3¢)?
   │   └── No → Skip (sub-3¢ trap)
   ├── Is this a threshold market AND SKIP_YES_ON_THRESHOLD=true?
   │   └── Yes → Skip
   ├── Get weather forecast (NWS preferred)
   │   └── No forecast → Skip
   ├── Calculate fair probability
   ├── Is edge ≥ MIN_EDGE_THRESHOLD (10%)?
   │   └── No → Skip
   └── Create trade signal

3. For each market, check NO opportunity:
   ├── Is YES price > EXTREME_NO_MIN_YES_PRICE (50¢)?
   │   └── No → Skip
   ├── Is NO price ≥ EXTREME_NO_MIN_PRICE (3¢)?
   │   └── No → Skip (sub-3¢ trap)
   ├── Get weather forecast
   ├── Calculate fair probability for NO
   ├── Is edge ≥ MIN_EDGE_THRESHOLD (10%)?
   │   └── No → Skip
   └── Create trade signal

4. Sort signals:
   ├── If PREFER_NO_ON_RANGE: NO+RANGE first, then NO+THRESHOLD, then YES
   └── Within each tier, sort by expected value

5. Apply risk limits:
   ├── Filter out markets with existing positions
   ├── Apply city limits (MAX_TRADES_PER_CITY)
   └── Cap at MAX_TRADES_PER_SCAN

6. Execute top trades
```

---

## Tuning Guide

### If win rate is too low:
- Increase `MIN_EDGE_THRESHOLD` (require more edge)
- Enable `SKIP_YES_ON_THRESHOLD` (eliminate worst category)
- Increase `EXTREME_YES_MIN_PRICE` (avoid cheap traps)

### If not enough trades:
- Decrease `MIN_EDGE_THRESHOLD` (accept less edge)
- Increase `EXTREME_YES_MAX_PRICE` (allow higher prices)
- Decrease `EXTREME_NO_MIN_YES_PRICE` (allow cheaper YES for NO bets)

### If position sizes feel wrong:
- Adjust `EXTREME_MIN_POSITION`, `EXTREME_MAX_POSITION`, `EXTREME_AGGRESSIVE_MAX`
- Lower values = Less risk per trade, more trades needed for same exposure

### If losing on specific trade types:
- Check backtest breakdown by trade type
- Consider enabling `SKIP_YES_ON_THRESHOLD`
- Ensure `PREFER_NO_ON_RANGE=true`

---

## Configuration File Locations

| Setting | Location |
|---------|----------|
| Runtime config | `.env` |
| Default values | `bot/utils/config.py` |
| Strategy logic | `bot/application/extreme_value_strategy.py` |
| Probability calc | `bot/connectors/weather.py` |

---

## Version History

| Version | Key Changes |
|---------|-------------|
| v2.5.2 | Inverted position sizing - bet more on proven winners (10-12¢), less on traps (<5¢) |
| v2.5.1 | Added NO min price floor (same 3¢ filter as YES) |
| v2.5.0 | Added min price floor, NWS-only mode, trade type preferences, increased std_dev |
| v2.4.0 | Added NWS integration, fixed threshold direction bug |
| v2.3.0 | Added range probability calculation, weather API integration |
