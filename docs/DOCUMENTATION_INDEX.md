# Documentation Index

**Purpose:** Master index of all documentation - Quick navigation to all docs
**Last Updated:** January 27, 2026

---

## 📂 Repository Structure

```
polymarket-weather-bot/
├── docs/           # All documentation (you are here)
├── bot/            # Source code
├── scripts/        # Utility and diagnostic scripts
├── tests/          # Unit tests
└── README.md       # Main entry point
```

---

## 📚 Documentation Categories

### 🏗️ Architecture & Design

| Document | Purpose | Use When |
|----------|---------|----------|
| `ARCHITECTURE.md` | System architecture, data flow, common issues | Understanding how components connect, troubleshooting |
| `EXTREME_VALUE_STRATEGY.md` | Strategy explanation and theory | Understanding WHY the strategy works |
| `STRATEGY_PARAMETERS.md` | **All strategy parameters explained** | Understanding why trades are made, tuning the bot |
| `CHANGELOG.md` | Version history and recent improvements | Understanding what changed and why |

### 📖 User Guides & Tutorials

| Document | Purpose | Use When |
|----------|---------|----------|
| `../README.md` | Main documentation, getting started | First time setup, quick reference |
| `CONFIGURATION.md` | All config options explained | Setting up .env, tuning parameters |
| `SIMULATION_GUIDE.md` | How to run 2-week validation | Before going live with real money |
| `TESTING_RESOLUTION_CHECKER.md` | Instant resolution testing (10s vs 24h) | Testing resolution logic without waiting overnight |
| `WALLET_ANALYSIS_GUIDE.md` | How to analyze trader strategies | Researching successful traders |

### 🔧 Implementation Specifications

| Document | Purpose | Use When |
|----------|---------|----------|
| `WEATHER_EDGE_IMPLEMENTATION.md` | Weather-informed position sizing specification | Ready to implement edge-based scaling |

**Template for Future Implementation Docs:**
- Current state analysis
- Exact code changes with line numbers
- Configuration parameters
- Testing strategy
- Success metrics
- Risk considerations

### 📊 Analysis & Research

| Document | Purpose | Use When |
|----------|---------|----------|
| `TRADER_ANALYSIS.md` | Research on successful traders | Validating strategy choices |
| `STRATEGY_OPTIMIZATION_JAN_2026.md` | Strategy parameter optimization analysis | Tuning scan frequency, edge thresholds, position sizing |

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
1. Check `CHANGELOG.md` and `ARCHITECTURE.md` for recent changes and known issues
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
- Version updates (→ CHANGELOG.md)

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
1. `../README.md` - Start here (root directory)
2. `ARCHITECTURE.md` - Technical details and troubleshooting
3. `CHANGELOG.md` - Recent changes and improvements
4. `CONFIGURATION.md` - How to configure the bot
5. This file - Navigation hub

**For AI Context:**
1. Check `CHANGELOG.md` for recent changes (currently v2.2.0)
2. Check `ARCHITECTURE.md` for system design and common issues
3. Check current bot status with: `python bot.py bot-status --simulation --platform kalshi`
4. **Current Status (v2.2.0):**
   - ✅ Dual-mode resolution checking (simulation uses markets API, live uses settlements API)
   - ✅ Duplicate trade prevention (filters existing positions)
   - ✅ Location injection (city names in market questions)
   - ✅ File logging enabled (logs/bot.log)

---

**Document Count:** 11 markdown files
**Scripts:** 11 utility/diagnostic scripts in `../scripts/`
**Tests:** 5 test files in `../tests/`
**Last Major Update:** v2.2.0 - Dual-mode resolution, duplicate prevention, location injection (Jan 26, 2026)
