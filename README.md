# EBasketball Lines Tracker

A system for tracking opening lines vs closing results for eBasketball games using BetsAPI.

## Quick Start

1. Setup environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Configure:
   ```bash
   cp .env.example .env
   # Edit .env with your BETSAPI_KEY and LEAGUE_IDS
   ```

3. Run:
   ```bash
   python run_tracker.py
   ```

## Core Files

- `src/etl.py` - Main ETL process
- `src/betsapi.py` - BetsAPI client
- `run_tracker.py` - Main runner script
- `backfill_*.py` - Data backfill scripts

## Monitoring Tools

- `enhanced_dashboard.py` - Real-time dashboard
- `data_quality.py` - Data quality analysis  
- `verify_fix.py` - System health checks
- `live_monitor.py` - Live monitoring

## Analysis

The system tracks how opening spreads/totals compare to final game margins/totals, looking for games that finish within 2-5 points of the opening lines.

## Database Schema

See `schema.sql` for complete database structure.
