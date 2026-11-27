# ATLAS Quant Engine

**Multi-Asset Quantitative Market Analysis Platform**

ATLAS Quant Engine is being developed as a multi-asset market-data and quantitative-analysis platform. The current BTC/SOL pipeline is the initial validation scope; the long-term roadmap covers crypto, FX, commodities, equities, indices and supported derivatives.

## Project roadmap

The durable architecture decisions, phased delivery plan, acceptance gates and new-session handoff instructions are maintained in the [ATLAS Quant Engine Master Roadmap](docs/ATLAS_QUANT_ENGINE_MASTER_ROADMAP.md).

> Start new project sessions by reading the Master Roadmap and checking the current repository/worktree state before making changes.

## Development principles

- One logical canonical data universe with independent instrument/timeframe data lanes.
- Explicit freshness, provenance and validation for every published record.
- A failure in one instrument must not block unrelated healthy instruments.
- Last-known-good data may be retained only when clearly marked stale.
- Controlled, race-safe publication; no partial or unverified updates.
- Existing paper-only research safeguards remain protected.
