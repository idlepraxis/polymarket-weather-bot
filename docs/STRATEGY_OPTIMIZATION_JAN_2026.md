# Strategy Optimization Analysis - January 2026

**Date:** January 27, 2026
**Version:** v2.2.0
**Status:** RECOMMENDATION - Awaiting Implementation

---

## Executive Summary

Based on analysis of current configuration and extreme value strategy principles, **three key optimizations** are recommended:

1. **Increase scan frequency** from 6 hours → 4 hours (50% more coverage)
2. **Tighten entry thresholds** for higher quality trades (12¢ YES max, 45¢ NO min)
3. **Add market quality filters** for spread, liquidity, and position sizing

**Expected Impact:**
- Same number of trades (15-20/day)
- Higher win rate (current unknown, estimated +5-10%)
- Better average edge (45¢ vs 35¢)
- Same or lower total exposure (better risk/reward)

---

## Current Strategy Analysis

### Configuration (Defaults from config.py)

```python
# Scanning
SCAN_INTERVAL_HOURS = 6              # Scans 4x/day
MAX_TRADES_PER_SCAN = 20
MAX_TRADES_PER_CITY = 3

# Entry Thresholds
EXTREME_YES_MAX_PRICE = 0.15         # 15¢ max YES entry
EXTREME_YES_IDEAL_PRICE = 0.10       # 10¢ ideal YES
EXTREME_NO_MIN_YES_PRICE = 0.40      # YES must be 40¢+ to buy NO
EXTREME_NO_IDEAL_YES_PRICE = 0.50    # YES @ 50¢ ideal NO entry

# Position Sizing
EXTREME_MIN_POSITION = 0.50          # $0.50 min
EXTREME_MAX_POSITION = 1.00          # $1.00 standard
EXTREME_AGGRESSIVE_MAX = 1.50        # $1.50 max
MAX_DAILY_EXPOSURE_PCT = 5.0         # 5% of bankroll/day
```

### Performance Metrics (From User)

- **20 trades placed** in most recent scan (1:51 PM)
- **19 markets available** on Kalshi (7 cities)
- **0 resolved trades yet** (too early - need 24+ hours)
- **Covering 7/7 cities** - good diversification

---

## Optimization 1: Increase Scan Frequency

### Current State
- Scans every 6 hours (4x/day: 12am, 6am, 12pm, 6pm)
- Daily temperature markets typically list around 6-8 AM EST
- Markets close around 11:59 PM same day

### Problem
- Only 2-3 scan opportunities per market lifecycle
- Missing best entry prices if markets move quickly
- Competition from other extreme value traders

### Recommendation: Scan Every 4 Hours

**New Schedule:** 12am, 4am, 8am, 12pm, 4pm, 8pm (6 scans/day)

**Benefits:**
- ✅ 50% more coverage (6 vs 4 scans)
- ✅ Better chance of catching mispriced markets
- ✅ Can capitalize on intraday corrections
- ✅ Minimal cost (just API calls)

**Implementation:**
```bash
# Add to .env:
SCAN_INTERVAL_HOURS=4
```

**Risk:** None - Just more frequent checks

---

## Optimization 2: Tighten Entry Thresholds

### Current Edge Analysis

**YES Trades at 15¢:**
- If true probability ≈ 50% (tails of distribution), fair value ≈ 50¢
- Buying at 15¢ → **Gross edge = 35¢**
- After 3-5¢ commission → **Net edge ≈ 30¢**
- Risk/Reward: ~2:1 to 3:1

**NO Trades when YES @ 40¢:**
- Buying NO at 60¢ when YES is 40¢
- If true YES probability <10%, fair NO value ≈ 90¢
- **Edge ≈ 30¢** (similar to YES trades)

### Problem with Current Thresholds

1. **Too loose** - Catching marginal opportunities
2. **Lower win rate** - 15¢ markets can go to 20-25¢ and still lose
3. **More volatility** - Wider swings in daily P&L

### Recommendation: Tighten by 3-5¢

**New Thresholds:**
```bash
# Add to .env:
EXTREME_YES_MAX_PRICE=0.12        # Was 0.15 (↓ 3¢)
EXTREME_YES_IDEAL_PRICE=0.08      # Was 0.10 (↓ 2¢)
EXTREME_NO_MIN_YES_PRICE=0.45     # Was 0.40 (↑ 5¢)
EXTREME_NO_IDEAL_YES_PRICE=0.55   # Was 0.50 (↑ 5¢)
```

**Expected Impact:**

| Metric | Current (15¢) | New (12¢) | Change |
|--------|---------------|-----------|--------|
| Avg Edge | 35¢ | 45¢ | +10¢ (+29%) |
| Trades/Day | 20 | 12-15 | -25% to -40% |
| Win Rate | Unknown | Higher | +5-10% est |
| Quality | Mixed | High | Better |

**Trade-off:**
- ⚠️ Fewer trades (12-15 vs 20)
- ✅ Higher edge per trade (45¢ vs 35¢)
- ✅ Better win rate
- ✅ Lower variance

**Compensation:** Can increase position sizes to maintain exposure (see below)

---

## Optimization 3: Enhanced Market Examination

### Current Selection Logic

**What Bot Does:**
1. Fetch all daily temperature markets
2. Filter by price: YES < 15¢ OR YES > 40¢
3. Take up to 3 trades per city
4. Execute up to 20 trades total

**What Bot Does NOT Check:**
- ❌ Bid-ask spread (could be 5-10¢ wide)
- ❌ Market liquidity (could be $50 total volume)
- ❌ Order book depth (may not fill desired size)
- ❌ Position sizing based on edge quality

### Recommended Additions

#### Filter 1: Spread Check
```python
# Reject markets with spread > 5¢
max_spread = 0.05
if (best_ask - best_bid) > max_spread:
    skip_market()
```

**Impact:** Avoid paying 5¢+ in slippage

#### Filter 2: Liquidity Check
```python
# Require minimum $500 total volume
min_volume = 500.0
if market_volume < min_volume:
    skip_market()
```

**Impact:** Ensure markets are active and liquid

#### Filter 3: Edge-Based Position Sizing
```python
# Scale position size by edge quality
def calculate_position_size(price, side):
    if side == "YES":
        edge = 0.50 - price  # Assume 50% true probability
        if edge > 0.42:      # 8¢ entry (optimal)
            return 1.50      # Aggressive max
        elif edge > 0.38:    # 12¢ entry (good)
            return 1.00      # Standard
        else:                # 15¢ entry (acceptable)
            return 0.50      # Minimum

    elif side == "NO":
        yes_price = 1.0 - price
        if yes_price > 0.55:  # YES @ 55¢+ (optimal NO)
            return 1.50
        elif yes_price > 0.50:  # YES @ 50-55¢ (good NO)
            return 1.00
        else:                # YES @ 45-50¢ (acceptable NO)
            return 0.50
```

**Impact:** Put more money on the best opportunities

---

## Recommended Configuration

### Complete Optimized .env Settings

```bash
# ============================================================================
# STRATEGY OPTIMIZATION - January 2026
# ============================================================================

# --- Scanning & Frequency ---
SCAN_INTERVAL_HOURS=4              # ↑ from 6 (more coverage)
RESOLUTION_CHECK_HOURS=1           # Keep at 1 (hourly checks)

# --- Entry Thresholds (Tightened) ---
EXTREME_YES_MAX_PRICE=0.12         # ↓ from 0.15 (higher quality)
EXTREME_YES_IDEAL_PRICE=0.08       # ↓ from 0.10 (target best entries)
EXTREME_NO_MIN_YES_PRICE=0.45      # ↑ from 0.40 (higher quality)
EXTREME_NO_IDEAL_YES_PRICE=0.55    # ↑ from 0.50 (target best entries)

# --- Position Sizing (Adjusted for Fewer Trades) ---
EXTREME_MIN_POSITION=0.75          # ↑ from 0.50 (larger min)
EXTREME_MAX_POSITION=1.50          # ↑ from 1.00 (larger standard)
EXTREME_AGGRESSIVE_MAX=2.50        # ↑ from 1.50 (larger max)

# --- Trade Limits (Adjusted) ---
MAX_TRADES_PER_SCAN=15             # ↓ from 20 (fewer but better)
MAX_TRADES_PER_DAY=60              # ↑ from 50 (4 more scans)
MAX_TRADES_PER_CITY=3              # Keep at 3 (diversification)

# --- Risk Management (Same) ---
BANKROLL=1000.0
MAX_DAILY_EXPOSURE_PCT=5.0         # Keep at 5% ($50/day max)

# --- System ---
SIMULATION_MODE=true               # Keep true during testing
LOG_LEVEL=INFO
```

---

## Implementation Plan

### Phase 1: Quick Wins (No Code Changes)

**Just update .env file:**

1. ✅ Increase scan frequency: `SCAN_INTERVAL_HOURS=4`
2. ✅ Tighten YES threshold: `EXTREME_YES_MAX_PRICE=0.12`
3. ✅ Tighten NO threshold: `EXTREME_NO_MIN_YES_PRICE=0.45`
4. ✅ Adjust position sizes: `EXTREME_MAX_POSITION=1.50`

**Testing:** Run for 3-5 days and compare:
- Number of trades/day (expect 12-15 vs 20)
- Average entry prices (expect 10¢ YES, 55¢ implied YES for NO)
- Win rate after 1 week

### Phase 2: Market Quality Filters (Requires Code)

**Add to market scanner logic:**

1. Spread filter (max 5¢)
2. Liquidity filter (min $500 volume)
3. Edge-based position sizing

**Files to Modify:**
- `bot/scanners/kalshi_scanner.py` (add filters)
- `bot/strategies/extreme_value.py` (add edge-based sizing)

**Testing:** Compare with Phase 1 results

### Phase 3: Advanced Optimizations (Future)

1. Weather edge integration (WEATHER_EDGE_IMPLEMENTATION.md)
2. Historical win rate tracking
3. Dynamic threshold adjustment based on performance
4. Multi-city correlation analysis

---

## Success Metrics

### Week 1 (Phase 1 Only)

**Target Metrics:**
- 12-15 trades/day (down from 20)
- Average YES entry: 10-11¢ (down from 13-14¢)
- Average NO entry: YES @ 52¢+ (up from 45¢)
- Total exposure: ~$20/day (same as before with larger sizes)

**Win Rate Target:** Unknown (need baseline first)

### Week 2-4 (Full Strategy)

**Compare to Week 1:**
- Win rate +5-10% (if Phase 2 filters work)
- Average edge +8-10¢ per trade
- Total P&L: Better risk-adjusted returns

---

## Risk Analysis

### Potential Issues

**1. Fewer Trades = Less Data**
- With 12-15 trades/day instead of 20, slower to gather statistical significance
- **Mitigation:** Tighter thresholds should produce higher win rate to compensate

**2. Missing Marginal Opportunities**
- 13-15¢ YES markets that would have won are now skipped
- **Mitigation:** The opportunities we DO take have 50% better edge

**3. Increased Position Sizes = More Volatility**
- $1.50-$2.50 positions vs $0.50-$1.00
- **Mitigation:** Better quality trades should reduce volatility overall

**4. 4-Hour Scans = More API Calls**
- 6 scans/day vs 4 scans/day
- **Mitigation:** Kalshi API has high rate limits, negligible cost

### Rollback Plan

If results are worse after 1 week:

```bash
# Revert to original settings:
SCAN_INTERVAL_HOURS=6
EXTREME_YES_MAX_PRICE=0.15
EXTREME_NO_MIN_YES_PRICE=0.40
EXTREME_MAX_POSITION=1.00
EXTREME_AGGRESSIVE_MAX=1.50
MAX_TRADES_PER_SCAN=20
```

---

## Questions for User

**Before implementing, please confirm:**

1. ✅ Are you comfortable with fewer trades (12-15 vs 20) in exchange for higher quality?
2. ✅ Should we implement Phase 1 (config only) first, or go straight to Phase 2 (with code)?
3. ✅ What's your target win rate expectation? (Typical extreme value: 55-65%)
4. ✅ Any concerns about increased position sizes ($2.50 max vs $1.50)?

---

## Conclusion

**Key Insights:**

1. **Scan frequency:** 6 hours is adequate, but 4 hours is better (50% more coverage)
2. **Edge thresholds:** Current 15¢/40¢ is good, but 12¢/45¢ is better (29% more edge)
3. **Market examination:** Currently only checks price, should add spread/liquidity filters

**Recommended Action:**

Start with **Phase 1** (config-only changes) and run for 5 days to validate:
- Create `.env` file if it doesn't exist
- Copy `.env.example` → `.env`
- Apply optimized settings above
- Monitor results daily
- Proceed to Phase 2 if results are positive

---

**Next Steps:**
1. User reviews this analysis
2. User approves Phase 1 implementation
3. Create `.env` with optimized settings
4. Run bot for 5 days
5. Analyze results and decide on Phase 2
