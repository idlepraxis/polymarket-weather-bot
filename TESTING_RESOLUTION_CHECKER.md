# Testing Resolution Checker

This guide explains how to test the resolution checker without waiting for real markets to finalize.

## Problem

During development, waiting overnight for markets to finalize makes debugging extremely slow. The resolution checker runs hourly and only updates when Kalshi markets reach `status: 'finalized'`.

## Solution

We've added a `test-resolution` command that simulates a finalized market, allowing you to verify the resolution logic works correctly immediately.

## How to Use

### 1. Test with Any Open Trade

The simplest way - test with your first open trade:

```bash
python bot.py test-resolution
```

This will:
- Show you the trade details (ticker, question, position)
- Simulate the market finalizing with outcome "yes" (default)
- Calculate the P&L
- Ask if you want to update the database

### 2. Test with Specific Outcome

Test what happens if a market resolves "no":

```bash
python bot.py test-resolution --outcome no
```

### 3. Test Specific Ticker

Test a particular market:

```bash
python bot.py test-resolution --ticker HIGHSF-26JAN21-T32 --outcome yes
```

## What It Tests

This command verifies:
- ✅ The resolution checker can read open trades from database
- ✅ The logic for determining win/loss works correctly
- ✅ P&L calculations are accurate
- ✅ Database updates work properly
- ✅ Status command shows updated P&L after resolution

## Example Output

```
🧪 Testing Resolution Checker

Testing with trade:
  Trade ID: abc123
  Market: HIGHSF-26JAN21-T32
  Question: Will San Francisco hit 32°F on Jan 21?
  Token: Yes
  Size: $1.00

Simulating market finalization with outcome: yes

Resolution Result:
  Market Outcome: YES
  Your Position: Yes
  Result: 🎉 WON
  P&L: +$0.35

Update this trade in the database? [y/N]:
```

## Testing Workflow

1. **Run the bot** to place some trades:
   ```bash
   python bot.py bot-start --simulation
   ```

2. **Test resolution logic** without waiting:
   ```bash
   python bot.py test-resolution --outcome yes
   ```

3. **Check P&L updates**:
   ```bash
   python bot.py status
   ```

4. **Test both outcomes** to verify win/loss calculations:
   ```bash
   # Test a winning trade
   python bot.py test-resolution --outcome yes

   # Test a losing trade
   python bot.py test-resolution --outcome no
   ```

## What This Doesn't Test

This command simulates the resolution logic but does NOT test:
- ❌ The Kalshi API integration (making real API calls)
- ❌ The automatic hourly resolution checker loop
- ❌ Network issues or API rate limits

For those, you still need to let the bot run overnight with real markets.

## Why This Matters

**Before:** Debug cycle = 24 hours (wait for markets to finalize)
**After:** Debug cycle = 10 seconds (test immediately)

This dramatically speeds up development and lets you verify:
- Resolution logic is correct
- P&L calculations are accurate
- Database updates work
- Win/loss determination is correct

Without having to wait for real markets every time.

## Important: Dual-Mode Resolution (January 2026 Update)

The resolution checker now works differently for simulation vs live modes:

**Simulation Mode:**
- Uses Kalshi markets API with `status=settled` parameter
- Queries finalized markets by series ticker
- No real positions exist, so can't use settlements API

**Live Mode:**
- Uses Kalshi settlements API for real settled positions
- Calculates actual P&L from executed trades

The `test-resolution` command tests the core logic that's shared between both modes (win/loss determination, P&L calculation, database updates). The only difference in production is which API endpoint is called.

## Next Steps

After verifying the logic works with test data:

1. Let the bot run overnight with real markets
2. Check tomorrow morning if actual trades resolved
3. If they didn't, we know it's an API integration issue (not logic issue)
4. Check `logs/bot.log` for "Checking for market resolutions" to verify checker is running

This narrows down where bugs might be hiding.
