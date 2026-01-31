# 🎯 Extreme Value Betting Strategy

## The Strategy That Actually Works

> **Note:** This strategy was originally analyzed on Polymarket but works identically on **Kalshi** (the bot's current primary platform). The same principles, entry thresholds, and risk management apply. All examples use Polymarket data as historical proof, but the automated bot now runs this strategy on Kalshi via `bot-start`.

This document explains the **Extreme Value Betting** strategy that has generated **$25,700+ in profits** for successful Polymarket weather traders.

### Real Performance Data

**Successful Trader:** `0x8278252ebbf354eca8ce316e680a0eaf02859464`

```
Total Predictions: 1,420
Total Winnings: $25,700
Average Profit per Bet: $18.10
Typical Position Size: <$1
Win Rate: ~60%

Notable Wins:
- $48  → $1,020  (21.3x return)
- $127 → $1,221  (9.6x return)
- $107 → $1,327  (12.4x return)
```

**ROI Calculation:**
- Assuming $1 average position × 1,420 trades = $1,420 deployed
- $25,700 profit ÷ $1,420 = **1,809% ROI**
- Even with $5k total capital deployed: **514% ROI**

This is NOT a typo. This strategy actually works.

---

## How It Works

### Core Principle: Exploit Market Inefficiency

Weather prediction markets on Polymarket are:
1. **Low liquidity** ($1k-$50k per market)
2. **Few sophisticated traders** watching
3. **High emotional volatility** (panic selling on forecasts)
4. **Slow price discovery** (mispricings persist for hours/days)

This creates **systematic mispricings** that can be exploited.

### The Rules (Dead Simple)

```
✅ BUY YES shares when price < 10-12¢
✅ BUY NO shares when YES price > 50¢ (NO costs < 50¢)
✅ Position size: $1.50 - $5.00 (v2.4.0)
✅ Quality over quantity: 10-15 trades per day
✅ Verify with weather forecast (don't bet blind!)
✅ Require 10% minimum edge before trading
❌ Never buy YES above 12¢
❌ Never buy NO when YES below 50¢ (insufficient payoff ratio)
```

That's it. Weather forecasts provide the edge. Strict price discipline provides the payoff.

> ⚠️ **CRITICAL**: The strategy requires weather data to calculate real probabilities. The bot uses **NWS (National Weather Service)** as the primary source (no API key required), with OpenWeatherMap and WeatherAPI.com as backups. Without weather data, the bot will skip trades.

---

## Why This Works: The Math

### Asymmetric Payoffs

**Buying YES at 10¢:**
- **Cost:** $0.10 per share
- **Payoff if YES:** $1.00 per share
- **Profit if right:** $0.90 (9x return)
- **Loss if wrong:** -$0.10

**Risk/Reward:** 9:1 payoff ratio

Even with a **30% win rate**, the expected value is positive:
```
EV = (0.30 × $0.90) - (0.70 × $0.10) = $0.27 - $0.07 = +$0.20 per share
+200% expected return per share!
```

### Market Overreaction Example

**Scenario:** Market asks "Will NYC exceed 70°F tomorrow?"

1. **Morning:** One forecast shows 68°F → Market panics, YES dumps to 8¢
2. **Reality:** Weather forecasts have ±5°F uncertainty
3. **True Probability:** ~25-35% chance (not 8%)
4. **Your Action:** Buy YES at 8¢
5. **Next Day:** Actual temp is 72°F → You win $0.92 per share

**Why the market was wrong:**
- Single data point bias
- Overconfidence in forecasts
- Emotional selling
- Lack of statistical thinking

You're not smarter. You're just **more patient and systematic**.

---

## Why Extreme Prices Are Often Wrong

### Statistical Reality of Weather Forecasts

Weather forecasts have inherent uncertainty:
- **±5°F** standard deviation for next-day temperature forecasts
- **±8-10°F** for 3-5 day forecasts
- **Lake effects, cold fronts, heat domes** can swing temps 10-20°F

When a market prices YES at 8¢ (8% probability), it's saying:
> "There's only an 8% chance the temperature will be above threshold."

But if the forecast says 68°F with a 70°F threshold:
- **1 std dev above forecast:** 20-30% chance
- **Forecast could be wrong:** Another 10-15% probability
- **True probability:** 25-40% (not 8%)

**You're getting 3-5x value.**

### The Oracle Problem (Why NO Is Profitable Too)

When YES is priced at 60¢ (market thinks 60% chance), you buy NO at 40¢.

Why? Because:
1. **Oracle uncertainty:** Which weather station does Polymarket use?
   - Airport vs downtown can differ 5-10°F
   - Your forecast might be for the "wrong" location

2. **Resolution criteria ambiguity:**
   - "High temperature" could mean max reading, average, or specific time
   - This adds 5-10% uncertainty to any prediction

3. **Market overconfidence:**
   - When YES is 60¢, market is very confident
   - Reality: Weather is chaotic, 60% is probably 45-50%

**You're exploiting overconfidence.**

---

## Implementation Details

### Position Sizing Strategy

The bot automatically sizes positions based on price:

**YES Purchases:**
```
YES ≤ 5¢:   $5.00 (super attractive)
YES ≤ 8¢:   $2.00 (very attractive)
YES ≤ 10¢:  $1.00 (ideal range)
YES ≤ 12¢:  $0.75 (good)
YES ≤ 15¢:  $0.50 (acceptable)
```

**NO Purchases (when YES is expensive) - v2.4.0:**
```
YES ≥ 75¢:  $5.00 (NO costs 25¢, 3x payoff)
YES ≥ 70¢:  $3.50 (NO costs 30¢, 2.3x payoff)
YES ≥ 60¢:  $2.50 (NO costs 40¢, 1.5x payoff)
YES ≥ 50¢:  $1.50 (NO costs 50¢, 1x payoff - edge required!)
```

> **Important**: v2.4.0 lowered the NO threshold from 60% to 50% but requires a **10% minimum edge** from weather data. At YES=50%, NO costs 50¢ with 1x payoff - only trade if weather forecasts show the market is wrong..

**Rationale:**
- At 5¢, $1 buys 20 shares (great upside, but limit position to manage risk)
- At 60¢ YES (40¢ NO), NO shares are undervalued

### Risk Management

**Daily Limits:**
- Max 20-30 positions per day
- Max total exposure: $50-100 (assuming $0.50-$1 per bet)
- If capital is $1k, you're risking 5-10% max per day

**Position Limits:**
- Never more than $5 on a single market
- Diversify across different cities/dates
- Avoid clustering (e.g., all NYC, all same day)

**Time Filters:**
- Minimum 2 hours until resolution (avoid last-minute chaos)
- Maximum 7 days out (too much uncertainty)
- Sweet spot: 1-3 days (best forecast accuracy)

---

## Expected Performance

### Conservative Projections

Assumptions:
- 3 trades per day × 30 days = 90 trades/month
- Average position: $1.00
- Win rate: 55% (conservative)
- Average price: 12¢ for YES, 45¢ for NO

**Monthly Math:**
```
Wins: 90 × 0.55 = 49.5 trades
Losses: 90 × 0.45 = 40.5 trades

Average win: $1.00 × (1 - 0.12) = $0.88
Average loss: $1.00 × 0.12 = -$0.12

Monthly profit: (49.5 × $0.88) - (40.5 × $0.12)
              = $43.56 - $4.86
              = $38.70/month

Annual profit: $38.70 × 12 = $464/year
```

**With $90 capital deployed per month (90 trades × $1):**
- ROI: $464 / $90 = **516% annual ROI**

### Aggressive Projections (Matching Real Trader)

If you can achieve similar performance to `0x8278...`:
- 4 trades/day × 365 days = 1,460 trades/year
- Average profit: $18/trade (their actual performance)
- **Annual profit: $26,280**

**Capital requirement:**
- If average position is $1: $1,460 deployed
- **ROI: 1,799%**

Even if you need $5k total capital for safety:
- **ROI: 526% annually**

---

## Why This Beats Forecast Arbitrage

### Forecast Arbitrage (My Original Strategy)
- ❌ Relies on having better forecasts than the market
- ❌ Edges are small (2-5%)
- ❌ Win rate: 55-60%
- ❌ Requires weather API costs, computation
- ❌ Markets often incorporate public forecasts already
- ✅ Scientific and feels smart

**Reality:** $500-1,000/year profit (7-10% ROI)

### Extreme Value Betting (This Strategy)
- ✅ Exploits market microstructure, not forecast accuracy
- ✅ Edges are HUGE (50-200% on individual trades)
- ✅ Win rate: 55-65% (good enough with asymmetric payoffs)
- ✅ No expensive data needed (just Polymarket prices)
- ✅ Simple rules, easy to automate
- ❌ Feels too simple (but it works!)

**Reality:** $5,000-26,000/year profit (500-1,800% ROI)

---

## Usage Instructions

### 1. Scan for Opportunities

```bash
python bot.py extreme-scan --limit 20
```

This shows you the top 20 extreme value opportunities with:
- Market question
- Side (YES or NO)
- Price
- Position size
- Expected value
- Payoff ratio

**Example Output:**
```
🎯 EXTREME VALUE Opportunities

Market                                      Side    Price   Size    EV      Payoff
Will NYC exceed 70°F on Jan 15?            📈 YES   8%     $2.00   +$1.64  11.5x
Will London see rain on Jan 16?            📉 NO    38%    $1.50   +$0.93   1.6x
Will Denver hit 45°F on Jan 17?            📈 YES   12%    $1.00   +$0.76   7.3x

Total EV: $3.33
Total Risk: $4.50
EV/Risk: 74%
```

### 2. Execute Trades (Simulation)

```bash
python bot.py extreme-trade --dry-run --max-trades 10
```

This will:
- Scan all weather markets
- Find extreme value opportunities
- Simulate executing the top 10 trades
- Show you what it would have done

**Safe to run - no real money!**

### 3. Go Live (When Ready)

```bash
python bot.py extreme-trade --live --max-trades 5
```

⚠️ **This executes REAL trades with REAL money!**

Start with:
- `--max-trades 1` for your first trade
- Watch it closely
- Gradually increase as you build confidence

### 4. Adjust Parameters

```bash
# More conservative (fewer opportunities)
python bot.py extreme-scan --yes-max 0.10 --no-min-yes 0.50

# More aggressive (more opportunities)
python bot.py extreme-scan --yes-max 0.20 --no-min-yes 0.35
```

---

## Configuration

Add these to your `.env` file:

```bash
# Weather APIs (NWS is used automatically as primary source)
OPENWEATHER_API_KEY=your_key      # Backup: openweathermap.org
WEATHERAPI_KEY=your_key           # Backup: weatherapi.com

# Edge Requirement (v2.4.0: increased from 5% to 10%)
MIN_EDGE_THRESHOLD=0.10           # Only trade with 10%+ edge

# Extreme Value Strategy Settings (v2.4.0: tighter thresholds)
EXTREME_YES_MAX_PRICE=0.12        # Max price to buy YES (12¢)
EXTREME_YES_IDEAL_PRICE=0.08      # Ideal YES price (8¢)
EXTREME_NO_MIN_YES_PRICE=0.50     # Min YES price to buy NO (50¢)
EXTREME_NO_IDEAL_YES_PRICE=0.60   # Ideal YES price for NO (60¢)

# Position Sizing (v2.4.0: larger positions, fewer trades)
EXTREME_MIN_POSITION=1.50         # Min position size (was 0.50)
EXTREME_MAX_POSITION=2.50         # Standard max position (was 1.00)
EXTREME_AGGRESSIVE_MAX=5.00       # Max for great opportunities (was 1.50)

# Trading Limits (v2.4.0: quality over quantity)
MAX_TRADES_PER_DAY=25             # Daily limit (was 50)
MAX_TRADES_PER_SCAN=10            # Per scan limit (was 20)
```

> **Weather Data**: The bot uses **NWS (National Weather Service)** as the primary weather source with 2x weight in the ensemble. This is the official US source and likely matches Kalshi's resolution data. OpenWeatherMap and WeatherAPI.com serve as backups.

---

## Common Questions

### Q: Why don't more people do this?

**A:** They do! But:
1. Most traders focus on news/politics (higher volume)
2. Weather markets are "boring" and overlooked
3. Requires patience and discipline (not exciting)
4. Small position sizes = seems not worth it
5. People don't believe simple strategies work

The successful trader has been doing this for **years** consistently. It works because it's **unsexy but systematic**.

### Q: Won't this stop working if everyone does it?

**A:** Eventually, but:
1. Weather markets are low-visibility
2. Requires daily discipline (most people quit)
3. New markets created constantly
4. Even with competition, mispricings will exist (emotional traders)

You have a **multi-year runway** before this gets competitive.

### Q: What's the catch?

**A:** Honest catches:
1. **Small absolute profits:** $50-100/month unless you scale
2. **Requires daily attention:** Check markets 2-3x per day
3. **Oracle risk:** Polymarket might use unexpected weather station
4. **Liquidity risk:** Can't deploy huge capital ($1k-5k max)
5. **Boring:** Buying 10¢ shares all day isn't thrilling

If you're okay with **slow, steady, boring profits**, this is perfect.

### Q: Can I use this full-time?

**A:** Not really:
- Max realistic annual profit: $10k-25k (even with perfect execution)
- Requires capital at risk ($1k-5k)
- Better as side income or learning experience

**But:** It's a GREAT way to:
- Learn prediction markets
- Build trading discipline
- Generate 500-1,800% ROI on small capital
- Have fun with quantitative trading

---

## Risk Warnings

### What Could Go Wrong

1. **Oracle disputes:** Polymarket uses unexpected data source
   - Mitigation: Diversify across many markets

2. **Market manipulation:** Whale moves prices artificially
   - Mitigation: Avoid low-liquidity markets (<$500)

3. **API costs:** If scaling, weather API costs could add up
   - Mitigation: This strategy doesn't require APIs!

4. **Polymarket terms:** Bot trading could violate ToS
   - Mitigation: Check with Polymarket, use responsibly

5. **Black swan:** Extreme weather event breaks models
   - Mitigation: Small position sizes limit damage

### Position Size Guidelines

**If your bankroll is $500:**
- Max per trade: $1
- Max daily exposure: $20 (20 trades)
- Comfortable losing 4% per day

**If your bankroll is $1,000:**
- Max per trade: $2
- Max daily exposure: $40
- Comfortable losing 4% per day

**If your bankroll is $5,000:**
- Max per trade: $5
- Max daily exposure: $100
- Comfortable losing 2% per day

**Never risk more than 5% of bankroll on a single day.**

---

## Comparison: Both Strategies

| Factor | Forecast Arbitrage | Extreme Value |
|--------|-------------------|---------------|
| **Edge Source** | Better forecasts | Market mispricing |
| **Typical Edge** | 2-5% | 50-200% |
| **Win Rate** | 55-60% | 55-65% |
| **Data Needed** | Weather APIs | Just Polymarket |
| **Complexity** | Medium | Low |
| **Annual ROI** | 50-100% | 500-1,800% |
| **Capital Needed** | $1k-10k | $500-5k |
| **Time Investment** | 5-10 hrs/week | 2-5 hrs/week |
| **Risk** | Low | Low-Medium |

**Recommendation:** **Use Extreme Value as your primary strategy.** Use forecast arbitrage as a supplementary filter (check if forecast supports the price being wrong).

---

## Getting Started Checklist

- [ ] Read this entire document
- [ ] Run `python bot.py extreme-scan` to see opportunities
- [ ] Run in simulation for 3-7 days
- [ ] Track simulated performance
- [ ] When comfortable, start with 1 live trade
- [ ] Gradually scale to 3-5 trades/day
- [ ] Monitor P&L weekly
- [ ] Adjust thresholds based on results

**Goal:** Achieve 4 trades/day average with 55%+ win rate.

If you hit this, you're on track for **$10k-25k annual profit** with minimal capital.

---

## Final Thoughts

This strategy is **unsexy but profitable**. You won't get rich quick. But you will make consistent, high-ROI returns on small capital by being:

1. **Patient** - Waiting for extreme prices
2. **Disciplined** - Never breaking the rules
3. **Systematic** - Trading every day
4. **Boring** - Letting math do the work

The successful trader didn't discover a secret. They just **followed simple rules consistently for years**.

You can too.

Happy trading! 🌤️📈💰
