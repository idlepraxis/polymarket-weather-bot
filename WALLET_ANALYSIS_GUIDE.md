# 🔍 Wallet Analysis Guide

**Last Updated:** January 17, 2026
**Status:** ✅ FULLY FUNCTIONAL

This guide shows you how to use the `analyze-wallet` command to reverse engineer successful traders' strategies and apply them to your own trading.

---

## Quick Start

```bash
# Basic analysis (analyzes up to 10,000 trades by default)
python bot.py analyze-wallet 0x0f37cb80dee49d55b5f6d9e595d52591d6371410

# Show individual trades
python bot.py analyze-wallet 0x0f37cb80dee49d55b5f6d9e595d52591d6371410 --show-trades

# Custom limit (if you want more or fewer trades)
python bot.py analyze-wallet 0x0f37cb80dee49d55b5f6d9e595d52591d6371410 --limit 5000
```

**Note:** The analyzer uses Polymarket's public Data API and requires no authentication. It will paginate automatically to fetch all trades up to the specified limit.

---

## Analyzing Known Successful Traders

### Trader A: The Consistent Grinder (0xaa7a...)

```bash
bot analyze-wallet 0xaa7a74b8c754e8aacc1ac2dedb699af0a3224d23
```

**What to look for:**
- High trade count (3,000+ trades)
- Small position sizes ($0.50-$1.00 average)
- Tight entry thresholds (YES < 12¢)
- Daily trading frequency (4-5 trades/day)

**Expected Strategy:**
```
YES Entry: ~11-12% median
NO Entry: ~45% (when YES > 55%)
Position Size: $0.50-$1.00
Frequency: 4-5 trades/day
```

### Trader B: The High-ROI Specialist (0x8278...)

```bash
bot analyze-wallet 0x8278252ebbf354eca8ce316e680a0eaf02859464
```

**What to look for:**
- Lower trade count (1,420 trades)
- Larger position sizes ($1-$5 average)
- More extreme entry thresholds (YES < 8¢)
- Selective trading (fewer but better opportunities)

**Expected Strategy:**
```
YES Entry: ~8-10% median
NO Entry: ~35-40% (when YES > 60-65%)
Position Size: $1-$5
Frequency: 3-4 trades/day
```

### Trader D (Hans323): High-Frequency Weather Specialist ✅ VALIDATED (0x0f37...)

```bash
python bot.py analyze-wallet 0x0f37cb80dee49d55b5f6d9e595d52591d6371410
```

**Actual Results (10,000 trades analyzed):**
- **Total Trades:** 10,000 over 49 days
- **Trade Frequency:** 204 trades/day
- **Weather Focus:** 80.9% (8,090 weather trades)
- **Position Sizing:** $1.00 median, $266.29 average
- **Max Position:** $34,965.00
- **Strategy:** High-volume small bets with selective aggressive positions

**Why This Matters:**
This trader's strategy **directly validates our bot's approach**:
- ✅ High frequency weather trading
- ✅ Small base position sizes ($1 median)
- ✅ Heavy focus on climate markets (80.9%)
- ✅ Occasional large bets on strong opportunities

**Expected Strategy:**
```
Market Focus: 80.9% Weather markets
Position Size: $1.00 median (tiny bets on lots of opportunities)
Frequency: 200+ trades/day (very active)
Approach: Spray and pray with selective aggression
```

---

## Step-by-Step: Replicating a Strategy

### Step 1: Analyze the Wallet

```bash
bot analyze-wallet 0x8278252ebbf354eca8ce316e680a0eaf02859464 > trader_b_analysis.txt
```

### Step 2: Review the Output

Look at the key sections:

**Entry Thresholds:**
```
📊 Entry Thresholds (Extreme Value Strategy)
┌──────────────────┬────────────┬────────────┐
│ Metric           │ YES Buys   │ NO Buys    │
├──────────────────┼────────────┼────────────┤
│ Median Entry     │ 10.5%      │ 37.0%      │
│ 10th Percentile  │ 5.2%       │ -          │
│ 90th Percentile  │ 14.8%      │ -          │
└──────────────────┴────────────┴────────────┘
```

**Position Sizing:**
```
💰 Position Sizing
┌───────────────────────┬──────────┐
│ Median Size           │ $1.50    │
│ Average Size          │ $1.85    │
│ Max Size              │ $5.00    │
└───────────────────────┴──────────┘
```

### Step 3: Copy Suggested Configuration

The analyzer generates a ready-to-use .env configuration:

```bash
⚙️ Suggested .env Configuration:

EXTREME_YES_MAX_PRICE=0.15
EXTREME_YES_IDEAL_PRICE=0.11
EXTREME_NO_MIN_YES_PRICE=0.63
EXTREME_MIN_POSITION=0.50
EXTREME_MAX_POSITION=1.50
EXTREME_AGGRESSIVE_MAX=5.00
```

### Step 4: Update Your .env File

```bash
# Open your .env file
nano .env

# Update the extreme value parameters
EXTREME_YES_MAX_PRICE=0.15
EXTREME_YES_IDEAL_PRICE=0.11
EXTREME_NO_MIN_YES_PRICE=0.63
EXTREME_MIN_POSITION=0.50
EXTREME_MAX_POSITION=1.50
EXTREME_AGGRESSIVE_MAX=5.00
```

### Step 5: Run Simulation

```bash
# Start 2-week simulation with the new parameters
bot-start --simulation --platform kalshi

# Check performance after 3-7 days
bot-status --simulation
```

### Step 6: Compare Results

After 1 week, compare your simulation to the trader's actual performance:

| Metric | Trader B | Your Sim | Status |
|--------|----------|----------|--------|
| Win Rate | 60-65% | ? | Compare |
| $/Trade | $18.10 | ? | Compare |
| Trades/Day | 3.1 | ? | Compare |

If your simulation matches within 20%, the strategy replication is successful.

---

## Advanced Analysis: Comparing Multiple Traders

### Batch Analysis Script

```bash
#!/bin/bash
# analyze_all_traders.sh

TRADERS=(
  "0xaa7a74b8c754e8aacc1ac2dedb699af0a3224d23"  # Trader A
  "0x8278252ebbf354eca8ce316e680a0eaf02859464"  # Trader B
  "0x6297b93ea37ff92a57fd636410f3b71ebf74517e"  # Trader C
  "0x0f37cb80dee49d55b5f6d9e595d52591d6371410"  # Trader D
)

for wallet in "${TRADERS[@]}"; do
  echo "Analyzing $wallet..."
  bot analyze-wallet "$wallet" > "analysis_${wallet:0:10}.txt"
  sleep 2  # Avoid rate limits
done

echo "Analysis complete! Check analysis_*.txt files"
```

### Comparison Spreadsheet

Create a comparison table:

| Metric | Trader A | Trader B | Trader C | Trader D |
|--------|----------|----------|----------|----------|
| **YES Median** | ~11% | ~10.5% | ? | ? |
| **NO Median** | ~45% | ~37% | ? | ? |
| **Avg Position** | $0.75 | $1.85 | ? | ? |
| **Max Position** | $2.00 | $5.00 | ? | ? |
| **Trades/Day** | 4.5 | 3.1 | ? | ? |
| **Weather %** | 95% | 94% | ? | ? |

---

## Understanding the Output

### Strategy Overview

```
🎯 Strategy Overview
┌──────────────────────┬──────────────┐
│ Total Trades         │ 1,420        │  ← How many trades total
│ Total Volume         │ $25,700.00   │  ← Total $ traded
│ Profit per Trade     │ $18.10       │  ← Average profit (if available)
│ Trading Period       │ 456 days     │  ← How long they've been active
│ Trades per Day       │ 3.1          │  ← Daily frequency
└──────────────────────┴──────────────┘
```

### Entry Thresholds

- **Median Entry**: Most common entry price (use this for your config)
- **10th Percentile**: Lowest 10% of entries (most extreme values)
- **90th Percentile**: Highest 10% of entries (upper limit)

**How to interpret:**
- If median YES entry is 10.5%, set `EXTREME_YES_IDEAL_PRICE=0.10`
- If 90th percentile is 14.8%, set `EXTREME_YES_MAX_PRICE=0.15`

### Position Sizing

- **Median**: Most common bet size (use this for `EXTREME_MAX_POSITION`)
- **Average**: Mean bet size (for comparison)
- **Max**: Largest bet ever placed (use for `EXTREME_AGGRESSIVE_MAX`)

**How to interpret:**
- If median is $1.50, they typically bet $1.50 per trade
- If max is $5.00, they occasionally go up to $5 on great opportunities

### Market Selection

```
🎲 Market Selection
┌──────────┬────────┬────────────┐
│ Category │ Trades │ Percentage │
├──────────┼────────┼────────────┤
│ Weather  │ 1,335  │ 94.0%      │  ← Focused on weather!
│ Sports   │ 52     │ 3.7%       │
│ Politics │ 33     │ 2.3%       │
└──────────┴────────┴────────────┘
```

**How to interpret:**
- 94% weather = they're a weather specialist (like our bot)
- <50% weather = they trade multiple categories (not pure weather trader)

### Performance by Price Range

Shows how they perform at different entry prices:

```
📈 Performance by Entry Range
┌────────────────────┬────────┬───────────┬──────────┐
│ Range              │ Trades │ Avg Entry │ Avg Size │
├────────────────────┼────────┼───────────┼──────────┤
│ YES < 15¢ (Extreme)│ 892    │ 9.2%      │ $1.50    │  ← Main strategy
│ YES 15-40¢ (Mid)   │ 105    │ 22.1%     │ $0.75    │  ← Rare
│ NO (YES > 40¢)     │ 528    │ 38.5%     │ $1.20    │  ← Secondary
└────────────────────┴────────┴───────────┴──────────┘
```

**How to interpret:**
- Most trades (892) are YES < 15¢ at ~$1.50 average
- This confirms extreme value strategy
- They also buy NO when YES > 60% (inverted from 38.5%)

---

## Common Patterns to Look For

### 1. Conservative Grinder Profile

**Characteristics:**
- ✅ High trade count (3,000+ trades)
- ✅ Small position sizes ($0.50-$1.00)
- ✅ Tight entry thresholds (YES < 12¢)
- ✅ High frequency (4-5+ trades/day)
- ✅ 90%+ weather focus

**Best for:** Consistent, low-risk returns with high volume

### 2. Aggressive Specialist Profile

**Characteristics:**
- ✅ Moderate trade count (1,000-2,000 trades)
- ✅ Larger positions ($1-$5)
- ✅ More extreme thresholds (YES < 8¢)
- ✅ Selective frequency (2-3 trades/day)
- ✅ 90%+ weather focus

**Best for:** Higher returns per trade, requires patience

### 3. Diversified Trader Profile

**Characteristics:**
- ✅ Variable trade count
- ✅ Mixed position sizes
- ✅ Multiple entry ranges
- ✅ <70% weather focus
- ✅ Trades across categories

**Best for:** Not pure weather strategy, harder to replicate

---

## Troubleshooting

### No trades found

**Causes:**
- Wallet has no Polymarket activity
- Wallet address is incorrect (check for typos)
- API rate limits or connectivity issues

**Solutions:**
```bash
# Verify wallet on polymarketanalytics.com first
# Check that address starts with 0x
# Try again in a few minutes (rate limits)
```

### Only a few trades returned

**Cause:** Default limit is 1000 trades

**Solution:**
```bash
# Fetch more trades
bot analyze-wallet <address> --limit 5000
```

### Analysis shows 0% weather markets

**Cause:** This trader doesn't trade weather markets

**Solution:**
- Find different trader on polymarketanalytics.com
- Filter for "Weather" category
- Look for high-volume traders

---

## Tips for Finding Good Traders to Analyze

### 1. Use Polymarket Analytics

Visit: https://polymarketanalytics.com/traders

**Filter by:**
- Total Volume: > $10,000
- Win Rate: > 55%
- Predictions: > 500

### 2. Look for Weather Specialists

**How to identify:**
- Check their recent activity
- Look for repeated weather market trades
- Temperature predictions are a good sign

### 3. Check Trading Frequency

**Good indicators:**
- Regular daily activity (not sporadic)
- Consistent trade sizes
- Long trading history (6+ months)

### 4. Avoid These Profiles

❌ **Whales:** Traders with $100k+ volume (different strategy, can't replicate)
❌ **Bots with weird patterns:** All trades at exact same size/time
❌ **Inactive:** Haven't traded in 3+ months
❌ **One-hit wonders:** Made profit from single lucky event

---

## Example Workflow: Finding and Analyzing a New Trader

### Step 1: Discover Trader

```bash
# Visit polymarketanalytics.com/traders
# Find trader with:
# - 1,000+ predictions
# - $10k+ volume
# - Recent activity in weather markets

# Example: 0x1234...abcd
```

### Step 2: Quick Analysis

```bash
bot analyze-wallet 0x1234...abcd
```

### Step 3: Evaluate Strategy

**Ask yourself:**
- Is their weather focus > 70%? (Good)
- Are they trading daily? (Good)
- Do they use extreme value thresholds? (Good)
- Is their avg position size reasonable ($0.50-$5)? (Good)

### Step 4: Extract Configuration

Copy the suggested .env settings from the output.

### Step 5: Test in Simulation

```bash
# Update .env with their parameters
nano .env

# Run 1-week simulation
bot-start --simulation --platform kalshi

# Compare results after 1 week
bot-status --simulation
```

### Step 6: Refine

If simulation results are close to the trader's performance (within 20-30%), you've successfully replicated their strategy!

---

## Next Steps

1. **Start with Trader B** - Highest ROI, well-documented
   ```bash
   bot analyze-wallet 0x8278252ebbf354eca8ce316e680a0eaf02859464
   ```

2. **Compare to your current results**
   ```bash
   bot-status --simulation
   ```

3. **Adjust your .env file** to match successful patterns

4. **Run 2-week validation** before going live

5. **Iterate** - Analyze new traders monthly to stay current

---

## FAQ

**Q: Can I analyze Kalshi wallets?**
A: No, currently only Polymarket. Kalshi doesn't have public trading history.

**Q: How often should I re-analyze traders?**
A: Monthly - strategies evolve over time.

**Q: What if two traders have very different strategies?**
A: Test both in simulation and see which performs better for you.

**Q: Can I combine insights from multiple traders?**
A: Yes! Use median values across multiple successful traders.

**Q: Is there a risk of over-fitting to one trader?**
A: Yes. Always validate with 2-week simulation before going live.

**Q: What if the trader's strategy stops working?**
A: Markets change. Re-analyze quarterly and adjust parameters.

---

## Troubleshooting

### "No trades found for this wallet"

**Fixed in v2.2 (January 17, 2026)**

This error occurred due to multiple issues, all now resolved:
- ✅ Switched from authenticated CLOB API to public Data API
- ✅ Fixed API parameter from `maker_address` to `user`
- ✅ Fixed timestamp parsing (Unix timestamps vs ISO strings)
- ✅ Fixed field name mapping (conditionId, title, usdcSize)

The wallet analyzer now successfully fetches trades for any Polymarket wallet.

### "MarkupError: closing tag doesn't match"

**Fixed in v2.2 (January 17, 2026)**

This error was caused by Rich trying to parse exception messages and tracebacks as markup. Fixed by:
- ✅ Added `markup=False` to exception printing
- ✅ Added `markup=False` to traceback printing
- ✅ Removed orphaned `[/dim]` closing tag

### Only showing 1,000 trades

**Fixed in v2.2 (January 17, 2026)**

The analyzer now:
- ✅ Paginates through all results automatically
- ✅ Default limit increased from 1,000 to 10,000
- ✅ Filters to TRADE events only (excludes SPLIT, MERGE, REDEEM, etc.)

### Showing 10,000+ trades but Polymarket says 2,703 predictions

**This is expected behavior.**

The API returns all TRADE events, including:
- BUY trades (opening positions)
- SELL trades (closing positions)

So if someone opens and closes a position, that's 2 trades but 1 prediction on Polymarket's UI.

The analyzer correctly filters to TRADE events only and excludes:
- ❌ SPLIT, MERGE (position management)
- ❌ REDEEM (claiming winnings)
- ❌ REWARD, CONVERSION, MAKER_REBATE (incentives)

Analyzing all trades gives a more accurate picture of trading frequency and strategy.

---

## Summary

The wallet analyzer lets you:
- ✅ Study successful traders without guessing
- ✅ Extract exact entry thresholds and position sizing
- ✅ Generate ready-to-use configuration
- ✅ Validate strategy hypotheses with real data
- ✅ Continuously improve by analyzing new traders

**The formula for success:**
1. Analyze proven traders
2. Replicate their parameters
3. Validate in simulation
4. Iterate and improve

Happy analyzing! 🔍📈💰
