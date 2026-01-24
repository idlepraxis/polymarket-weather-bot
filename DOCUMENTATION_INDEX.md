# Documentation Index

**Purpose:** Master index of all documentation - Claude's "external brain"
**Last Updated:** January 23, 2026

---

## 📚 Documentation Categories

### 🏗️ Architecture & Design

| Document | Purpose | Use When |
|----------|---------|----------|
| `ARCHITECTURE.md` | System architecture, data flow | Understanding how components connect |
| `EXTREME_VALUE_STRATEGY.md` | Strategy explanation and theory | Understanding WHY the strategy works |

### 📖 User Guides & Tutorials

| Document | Purpose | Use When |
|----------|---------|----------|
| `README.md` | Main documentation, getting started | First time setup, quick reference |
| `CONFIGURATION.md` | All config options explained | Setting up .env, tuning parameters |
| `SIMULATION_GUIDE.md` | How to run 2-week validation | Before going live with real money |
| `TESTING_RESOLUTION_CHECKER.md` | Instant resolution testing (10s vs 24h) | Testing resolution logic without waiting overnight |
| `WALLET_ANALYSIS_GUIDE.md` | How to analyze trader strategies | Researching successful traders |

### 🔧 Implementation Specifications

| Document | Purpose | Use When |
|----------|---------|----------|
| `WEATHER_EDGE_IMPLEMENTATION.md` | **Phase 7: Weather-informed position sizing** | Ready to implement edge-based scaling |

**Template for Future Implementation Docs:**
- Current state analysis
- Exact code changes with line numbers
- Configuration parameters
- Testing strategy
- Success metrics
- Risk considerations

### 📊 Historical Record

| Document | Purpose | Use When |
|----------|---------|----------|
| `SESSION_SUMMARY.md` | Complete development history by phase | Understanding what was built when and why |
| `TRADER_ANALYSIS.md` | Research on successful traders | Validating strategy choices |

---

## 🎯 How to Use This Index

### For Implementation Tasks

**Pattern:**
1. Check if an implementation guide exists here
2. If yes: `Read` the guide → Follow step-by-step
3. If no: Create one first (like `WEATHER_EDGE_IMPLEMENTATION.md`)

**Example:**
```
User: "Implement weather edge sizing"
Claude: *Checks index* → Found: WEATHER_EDGE_IMPLEMENTATION.md
        *Reads guide* → Implements per specification
```

### For Troubleshooting

**Pattern:**
1. Check `SESSION_SUMMARY.md` for similar past issues
2. Check architecture docs for how system works
3. Check configuration docs for parameter meanings

### For New Features

**Pattern:**
1. Create implementation guide FIRST (before coding)
2. Get user approval on spec
3. Add to this index
4. Implement later using the guide

---

## 📝 Documentation Standards

### When to Create a New Document

**Create a new doc when:**
- ✅ Implementing a major feature (>100 lines of code)
- ✅ Complex decision with multiple options
- ✅ Procedure that will be repeated
- ✅ Information needed across multiple sessions

**Add to existing doc when:**
- Update to current feature
- Small bug fix or tweak
- Session notes (→ SESSION_SUMMARY.md)

### Naming Convention

```
Purpose: NOUN_DESCRIPTION.md
Examples:
- WEATHER_EDGE_IMPLEMENTATION.md (implementation guide)
- RESOLUTION_CHECKER_TROUBLESHOOTING.md (troubleshooting)
- POSITION_SIZING_DECISION_LOG.md (decision record)
```

### Required Sections

Every implementation guide should have:
1. **Status** - Not started / In progress / Completed
2. **Overview** - What and why
3. **Current State** - What exists now
4. **Changes Required** - Exact modifications with line numbers
5. **Testing Strategy** - How to verify it works
6. **Success Metrics** - How to measure success
7. **Risks** - What could go wrong

---

## 🔄 Maintenance

**Weekly Review:**
- Update STATUS fields in implementation docs
- Archive completed implementation guides
- Add new discoveries to SESSION_SUMMARY.md

**After Major Changes:**
- Update affected documentation
- Create new implementation guides for next phase
- Update this index

---

## 🚀 Quick Reference

**Most Important Docs:**
1. `README.md` - Start here
2. `SESSION_SUMMARY.md` - Complete development history
3. `CONFIGURATION.md` - How to configure the bot
4. This file - Find anything else

**For Future Me (Next Session):**
1. Read `SESSION_SUMMARY.md` Phase 9 (latest)
2. Check current bot status with: `python bot.py status`
3. Test simulation mode resolution with: `python test_simulation_resolution.py`
4. Look for new implementation guides here
5. Proceed with next task

---

**Document Count:** 12 markdown files
**Implementation Guides:** 1 ready (WEATHER_EDGE_IMPLEMENTATION.md), 0 in progress
**Testing Guides:** 1 (TESTING_RESOLUTION_CHECKER.md)
**Debug Scripts:** 2 (debug_resolution_checker.py, debug_settlements_api.py)
**Test Scripts:** 1 (test_simulation_resolution.py)
**Last Major Update:** Phase 9 - Dual-mode resolution checker for simulation vs live (Jan 24, 2026)
