# Weather-Informed Dynamic Position Sizing Implementation Guide

**Status:** 📋 SPECIFICATION READY - Not Yet Implemented
**Created:** January 21, 2026
**Target Phase:** Phase 7 (After Phase 6 resolution checker validation)
**Priority:** MEDIUM - Implement after confirming current bot is profitable

---

## 🎯 Feature Overview

**Current Strategy:**
- Fixed position sizing: $0.50 - $1.50 per trade
- Based only on market price (cheaper = slightly bigger bet)
- "Spray and pray" approach - diversify across many markets

**Enhanced Strategy:**
- **Keep spray-and-pray base** ($1 default on everything)
- **Scale UP opportunistically** when weather data shows massive edge
- Weather-informed conviction sizing
- Maintain diversification, add selective aggression

**Core Principle:**
> "Bet small on everything to maintain coverage, but bet BIG when weather data confirms a slam dunk opportunity."

---

## 📐 Edge Calculation Overview

### Mathematical Definition

```python
Edge = Fair_Probability - Market_Price

Where:
- Fair_Probability = Calculated from weather forecast data (0.0 to 1.0)
- Market_Price = Current market price in decimal (0.0 to 1.0)
- Edge = Percentage points of mispricing
```

### Example Calculations

**Example 1: Small Edge (Normal)**
```
Market: "Will NYC exceed 70°F on Jan 25?"
Market Price: 12¢ (0.12)
Weather Forecast: 45°F high predicted
Fair Probability: 0.02 (2% chance of hitting 70°F)
Edge (buying NO): 0.9998 - 0.88 = 11.98% edge
→ Position Size: $1 (default)
```

**Example 2: Massive Edge (Scale Up)**
```
Market: "Will Phoenix exceed 100°F on July 15?"
Market Price: 25¢ (0.25)
Weather Forecast: 108°F high predicted
Fair Probability: 0.87 (87% chance of exceeding 100°F)
Edge (buying YES): 0.87 - 0.25 = 62% MASSIVE EDGE
→ Position Size: $20 (scaled up 20x)
```

---

## 🔧 Current Implementation State

### What Already Exists

The infrastructure is **90% complete**. These components are already built:

#### 1. Weather API Integration (`bot/connectors/weather.py`)

**Available Methods:**
```python
class WeatherConnector:
    def get_forecast(location: str, date: datetime) -> WeatherForecast
    def parse_market_question(question: str) -> Dict
    def calculate_probability(forecast, threshold, threshold_type) -> float
    def _ensemble_average(forecasts: List) -> WeatherForecast
```

**Supported APIs:**
- OpenWeather API
- WeatherAPI.com
- Ensemble averaging (combines multiple sources)

**Configuration Required:**
```bash
# .env file
OPENWEATHER_API_KEY=your_key_here
WEATHER_API_KEY=your_key_here
```

#### 2. Strategy Integration (`bot/application/extreme_value_strategy.py`)

**Existing Method (Line 230):**
```python
def _estimate_fair_probability(self, market: WeatherMarket, outcome: str) -> float:
    """Already implemented!

    - Parses market question
    - Gets weather forecast
    - Calculates fair probability
    - Returns 0.0-1.0 probability
    """
```

**Current Usage:**
- Fair probability IS calculated
- Edge IS computed internally
- But NOT used for position sizing (yet!)

#### 3. Position Sizing Methods (Line 180, 204)

**Current Implementation:**
```python
def _calculate_yes_position_size(self, yes_price: float) -> float:
    """Position size based ONLY on price"""
    if yes_price <= 0.05:
        return self.aggressive_max  # $1.50
    elif yes_price <= 0.10:
        return self.max_position    # $1.00
    else:
        return self.min_position    # $0.50

def _calculate_no_position_size(self, yes_price: float) -> float:
    """Similar logic for NO positions"""
```

**Missing:** Edge-based scaling logic

---

## 📝 Implementation Specification

### New Position Sizing Logic

**Function Signature:**
```python
def _calculate_edge_informed_position_size(
    self,
    market: WeatherMarket,
    outcome: str,  # "YES" or "NO"
    market_price: float,
    fair_probability: float
) -> float:
    """Calculate position size based on edge from weather data.

    Args:
        market: The weather market
        outcome: "YES" or "NO" - which side we're betting
        market_price: Current market price (0.0 - 1.0)
        fair_probability: Probability from weather forecast (0.0 - 1.0)

    Returns:
        Position size in USD
    """
```

### Position Sizing Tiers

**Conservative Scaling (Recommended for Initial Implementation):**

```python
# Calculate edge
edge = abs(fair_probability - market_price)

# Conservative scaling - only scale up on MASSIVE edge
if edge >= 0.70:  # 70%+ edge - Nearly impossible to be wrong
    position_size = 50.00  # Max conviction
elif edge >= 0.50:  # 50-70% edge - Slam dunk
    position_size = 20.00
elif edge >= 0.35:  # 35-50% edge - Very strong
    position_size = 10.00
elif edge >= 0.20:  # 20-35% edge - Strong
    position_size = 5.00
else:  # < 20% edge - Normal spray and pray
    position_size = 1.00  # DEFAULT - maintains diversification

return position_size
```

**Aggressive Scaling (Alternative - Test Carefully):**

```python
# More aggressive scaling
if edge >= 0.60:
    position_size = 100.00  # Go all-in on sure things
elif edge >= 0.45:
    position_size = 50.00
elif edge >= 0.30:
    position_size = 20.00
elif edge >= 0.15:
    position_size = 10.00
elif edge >= 0.08:
    position_size = 5.00
else:
    position_size = 1.00

return position_size
```

**Recommendation:** Start with conservative, measure results for 1-2 weeks, then decide if aggressive is warranted.

---

## 💻 Code Changes Required

### File 1: `bot/application/extreme_value_strategy.py`

#### Change 1: Add Edge-Informed Position Sizing Method

**Location:** After line 227 (after `_conservative_estimate` method)

```python
def _calculate_edge_informed_position_size(
    self,
    market: WeatherMarket,
    outcome: str,
    market_price: float,
    fair_probability: float
) -> float:
    """Calculate position size based on edge from weather data.

    Args:
        market: The weather market
        outcome: "YES" or "NO" - which side we're betting
        market_price: Current market price (0.0 - 1.0)
        fair_probability: Probability from weather forecast (0.0 - 1.0)

    Returns:
        Position size in USD
    """
    # Calculate edge (absolute difference)
    edge = abs(fair_probability - market_price)

    # Conservative scaling - only scale up on MASSIVE edge
    if edge >= 0.70:  # 70%+ edge - Nearly impossible to be wrong
        position_size = 50.00
        self.logger.info(f"🚀 MASSIVE EDGE ({edge:.1%}): Betting ${position_size} on {market.question[:50]}...")
    elif edge >= 0.50:  # 50-70% edge - Slam dunk
        position_size = 20.00
        self.logger.info(f"🎯 HUGE EDGE ({edge:.1%}): Betting ${position_size} on {market.question[:50]}...")
    elif edge >= 0.35:  # 35-50% edge - Very strong
        position_size = 10.00
        self.logger.info(f"💪 STRONG EDGE ({edge:.1%}): Betting ${position_size} on {market.question[:50]}...")
    elif edge >= 0.20:  # 20-35% edge - Strong
        position_size = 5.00
        self.logger.debug(f"✓ Good edge ({edge:.1%}): Betting ${position_size}")
    else:  # < 20% edge - Normal spray and pray
        position_size = 1.00  # DEFAULT
        self.logger.debug(f"Spray & pray: ${position_size} (edge: {edge:.1%})")

    return position_size
```

#### Change 2: Modify `_calculate_yes_position_size`

**Current Code (Line 180-202):**
```python
def _calculate_yes_position_size(self, yes_price: float) -> float:
    """Calculate position size for YES purchases."""
    # ... existing price-based logic ...
```

**New Code:**
```python
def _calculate_yes_position_size(self, market: WeatherMarket, yes_price: float) -> float:
    """Calculate position size for YES purchases.

    Args:
        market: Full market object (added parameter)
        yes_price: Current YES price

    Returns:
        Position size in USD
    """
    # Try weather-informed sizing first
    if self.weather:
        try:
            fair_prob = self._estimate_fair_probability(market, "YES")
            if fair_prob is not None and fair_prob != 0.5:  # 0.5 = no data fallback
                return self._calculate_edge_informed_position_size(
                    market=market,
                    outcome="YES",
                    market_price=yes_price,
                    fair_probability=fair_prob
                )
        except Exception as e:
            self.logger.debug(f"Edge sizing failed, using price-based: {e}")

    # Fallback to original price-based sizing
    # (Keep existing code as backup)
    if yes_price <= 0.05:
        return self.aggressive_max
    elif yes_price <= 0.08:
        return min(self.max_position * 2, self.aggressive_max)
    elif yes_price <= 0.10:
        return self.max_position
    elif yes_price <= 0.12:
        return self.max_position * 0.75
    else:
        return self.min_position
```

#### Change 3: Modify `_calculate_no_position_size`

**Similar changes as YES sizing:**
```python
def _calculate_no_position_size(self, market: WeatherMarket, yes_price: float) -> float:
    """Calculate position size for NO purchases."""
    # Try weather-informed sizing first
    if self.weather:
        try:
            fair_prob = self._estimate_fair_probability(market, "NO")
            if fair_prob is not None and fair_prob != 0.5:
                no_price = 1 - yes_price
                return self._calculate_edge_informed_position_size(
                    market=market,
                    outcome="NO",
                    market_price=no_price,
                    fair_probability=fair_prob
                )
        except Exception as e:
            self.logger.debug(f"Edge sizing failed, using price-based: {e}")

    # Fallback to original price-based sizing
    # (Keep existing code as backup)
    no_price = 1 - yes_price
    if no_price <= 0.05:
        return self.aggressive_max
    # ... rest of existing logic ...
```

#### Change 4: Update Method Calls

**Location:** Line 71-120 (in `scan_for_opportunities` method)

**Find these lines:**
```python
position_size = self._calculate_yes_position_size(market.yes_price)
# and
position_size = self._calculate_no_position_size(market.yes_price)
```

**Change to:**
```python
position_size = self._calculate_yes_position_size(market, market.yes_price)
# and
position_size = self._calculate_no_position_size(market, market.yes_price)
```

---

## 🧪 Testing Strategy

### Phase 1: Unit Testing (Recommended First Step)

Create test file: `tests/test_edge_position_sizing.py`

```python
"""Test edge-based position sizing logic."""

from bot.application.extreme_value_strategy import ExtremeValueStrategy
from bot.utils.models import WeatherMarket, MarketStatus
from datetime import datetime

def test_massive_edge_scaling():
    """Test that massive edge (>70%) triggers $50 bet."""
    strategy = ExtremeValueStrategy(config, client, weather)

    market = WeatherMarket(
        market_id="test",
        question="Will Phoenix exceed 100°F on July 15?",
        yes_price=0.25,
        # ... other fields ...
    )

    # Mock weather API to return 87% probability
    fair_prob = 0.87
    market_price = 0.25

    size = strategy._calculate_edge_informed_position_size(
        market, "YES", market_price, fair_prob
    )

    assert size == 50.00, f"Expected $50 for 62% edge, got ${size}"

def test_normal_edge_default_sizing():
    """Test that small edge (<20%) uses $1 default."""
    # Edge = 15%
    fair_prob = 0.25
    market_price = 0.10

    size = strategy._calculate_edge_informed_position_size(
        market, "YES", market_price, fair_prob
    )

    assert size == 1.00, f"Expected $1 for 15% edge, got ${size}"

# Run tests:
# pytest tests/test_edge_position_sizing.py -v
```

### Phase 2: Simulation Testing

**Test Plan:**
1. Run bot with edge-based sizing for 3-5 days in simulation
2. Compare against control period (previous 3-5 days with fixed sizing)
3. Track metrics:
   - Average position size
   - Number of scaled-up bets (>$5)
   - Win rate on scaled-up bets vs normal bets
   - Total P&L comparison
   - ROI comparison

**Success Criteria:**
- Win rate on scaled bets ≥ 60% (should be higher than normal)
- Overall ROI improves by ≥ 20%
- No catastrophic losses from oversized bets

### Phase 3: Logging and Monitoring

**Add enhanced logging:**
```python
# When scaling up, log details
if position_size > 5.00:
    self.logger.info(
        f"💰 SCALED BET: ${position_size:.2f}\n"
        f"   Market: {market.question}\n"
        f"   Fair Prob: {fair_probability:.1%}\n"
        f"   Market Price: {market_price:.1%}\n"
        f"   Edge: {edge:.1%}\n"
        f"   Weather: {forecast_summary}"
    )
```

**Monitor for:**
- Frequency of scaled bets (expect 2-10% of trades)
- Accuracy of weather forecasts
- Edge persistence (are big edges real or API errors?)

---

## ⚙️ Configuration Changes

### Add Config Parameters

**File:** `bot/utils/config.py`

```python
class Config:
    # ... existing config ...

    # Edge-based position sizing
    edge_sizing_enabled: bool = True  # Feature flag
    edge_tier_1_threshold: float = 0.70  # 70%+ edge
    edge_tier_1_size: float = 50.00
    edge_tier_2_threshold: float = 0.50  # 50-70% edge
    edge_tier_2_size: float = 20.00
    edge_tier_3_threshold: float = 0.35  # 35-50% edge
    edge_tier_3_size: float = 10.00
    edge_tier_4_threshold: float = 0.20  # 20-35% edge
    edge_tier_4_size: float = 5.00
    edge_default_size: float = 1.00  # < 20% edge
```

**Environment Variables (.env):**
```bash
# Edge-Based Position Sizing
EDGE_SIZING_ENABLED=true
EDGE_TIER_1_THRESHOLD=0.70
EDGE_TIER_1_SIZE=50.00
EDGE_TIER_2_THRESHOLD=0.50
EDGE_TIER_2_SIZE=20.00
EDGE_TIER_3_THRESHOLD=0.35
EDGE_TIER_3_SIZE=10.00
EDGE_TIER_4_THRESHOLD=0.20
EDGE_TIER_4_SIZE=5.00
EDGE_DEFAULT_SIZE=1.00

# Weather API Keys (required for edge sizing)
OPENWEATHER_API_KEY=your_key_here
WEATHER_API_KEY=your_key_here
```

---

## 📊 Expected Impact

### Baseline (Current Strategy)

```
Daily Trades: 100
Average Position: $1.00
Total Exposure: $100/day
Win Rate: 30%
Expected Daily P&L: ~$20-30
```

### With Edge-Based Sizing (Projected)

```
Daily Trades: 100
Breakdown:
  - 85 trades @ $1 = $85 (normal edge)
  - 10 trades @ $5 = $50 (20-35% edge)
  - 3 trades @ $10 = $30 (35-50% edge)
  - 2 trades @ $20 = $40 (50%+ edge)
Total Exposure: $205/day (+105% capital)

Expected Win Rates:
  - $1 trades: 30% (same as before)
  - $5+ trades: 50-70% (weather-confirmed edge)

Expected Daily P&L: $40-70 (+100-130% profit)
```

**Key Improvement:** Similar number of trades, 2x capital, 2-3x profit potential

---

## 🚨 Risk Considerations

### Potential Issues

1. **Weather API Reliability**
   - APIs can be down or rate-limited
   - Forecasts can be wrong (especially >3 days out)
   - **Mitigation:** Fallback to price-based sizing if weather unavailable

2. **Over-Concentration Risk**
   - Multiple big bets on same day/location could correlate
   - **Mitigation:** Track daily exposure by location, cap at $100/location

3. **False Edges**
   - Model might calculate "massive edge" incorrectly
   - Market might know something weather API doesn't
   - **Mitigation:** Start conservative (only bet big on 70%+ edge)

4. **Bankroll Requirements**
   - 2x daily exposure means 2x bankroll needed
   - **Mitigation:** Keep simulation until confirmed profitable

### Safety Features to Implement

```python
# Max position size cap (prevent catastrophic loss)
MAX_POSITION_SIZE = 50.00

# Max daily exposure per location
MAX_LOCATION_EXPOSURE = 100.00

# Max total daily exposure
MAX_DAILY_EXPOSURE = 500.00

# Minimum edge for scaling (don't trust marginal edges)
MIN_EDGE_FOR_SCALING = 0.20  # 20%
```

---

## 📅 Implementation Timeline

### Week 1: Preparation
- [ ] Verify current bot is profitable (wait for resolution check results)
- [ ] Obtain weather API keys if not already configured
- [ ] Review and understand current codebase

### Week 2: Development
- [ ] Day 1-2: Implement `_calculate_edge_informed_position_size` method
- [ ] Day 3-4: Modify `_calculate_yes_position_size` and `_calculate_no_position_size`
- [ ] Day 5: Add configuration parameters
- [ ] Day 6: Write unit tests
- [ ] Day 7: Code review and testing

### Week 3: Testing
- [ ] Run simulation with edge sizing for 5-7 days
- [ ] Monitor logs for scaled bets
- [ ] Track win rate on scaled vs normal bets
- [ ] Compare P&L to previous week

### Week 4: Evaluation & Tuning
- [ ] Analyze results
- [ ] Adjust thresholds if needed (more/less aggressive)
- [ ] Decide: deploy to live or iterate further
- [ ] Document results

---

## ✅ Pre-Implementation Checklist

Before starting implementation, verify:

- [ ] Current bot is running successfully (no crashes)
- [ ] Resolution checker is working (trades updating to WON/LOST)
- [ ] Current strategy is profitable (win rate ≥ 25%)
- [ ] Weather API keys are configured in `.env`
- [ ] Sufficient simulation bankroll ($500+ recommended for testing)
- [ ] 1-2 weeks of baseline performance data collected

**Do NOT implement if:**
- ❌ Current bot is losing money
- ❌ Resolution checker still broken
- ❌ No weather API access
- ❌ Insufficient baseline data

---

## 📖 Reference Code Locations

**Key Files:**
- Strategy: `bot/application/extreme_value_strategy.py` (lines 180-227)
- Weather: `bot/connectors/weather.py` (lines 250-303)
- Config: `bot/utils/config.py`
- Models: `bot/utils/models.py`

**Key Methods:**
- `_estimate_fair_probability()` - Line 230 (already calculates edge!)
- `_calculate_yes_position_size()` - Line 180 (needs modification)
- `_calculate_no_position_size()` - Line 204 (needs modification)
- `calculate_probability()` - weather.py line 250 (statistical model)

---

## 🎯 Success Metrics

**After 2-Week Test Period:**

| Metric | Target | Measurement |
|--------|--------|-------------|
| Scaled Bet Win Rate | ≥ 60% | Compare $5+ bets vs $1 bets |
| Overall ROI Improvement | +20-50% | Compare to baseline period |
| Scaled Bet Frequency | 5-15% | Count of bets >$5 |
| Max Drawdown | < 20% | Worst daily loss |
| Average Daily P&L | +50-100% | Compare to baseline |

**Decision Matrix:**

| ROI Improvement | Action |
|-----------------|--------|
| > +50% | Deploy immediately, consider more aggressive scaling |
| +20% to +50% | Deploy with conservative settings |
| 0% to +20% | Iterate and test more, don't deploy yet |
| Negative | Abandon feature, revert to fixed sizing |

---

## 📝 Notes for Implementation

1. **Start Conservative:** Use 70%/50%/35%/20% thresholds initially
2. **Feature Flag:** Make it easy to toggle on/off via config
3. **Extensive Logging:** Log every scaled bet with reasoning
4. **Fallback Always:** If weather fails, use price-based sizing
5. **Test Thoroughly:** Don't rush - 2 weeks of testing minimum
6. **Monitor Closely:** Check logs daily during test period

---

**Document Version:** 1.0
**Last Updated:** January 21, 2026
**Status:** Ready for Implementation
**Estimated Development Time:** 1-2 weeks
**Estimated Testing Time:** 2-3 weeks
