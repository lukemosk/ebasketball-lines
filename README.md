# eBasketball Lines Tracker

An automated system for tracking and analyzing betting lines in eBasketball (simulated basketball) games. Captures opening lines, quarter-end lines, and final results to identify potential middling opportunities.

## Overview

This system monitors live eBasketball H2H GG League games (4x5 minute quarters) and captures:
- Opening lines: Captured when games start (Q1 ~5:00 remaining)
- Quarter-end lines: Captured at the end of Q1, Q2, and Q3 (≤10 seconds remaining)
- Final results: Captured when games end (Q4 0:00)

The data enables analysis of line movements and identification of potential middle betting opportunities.

## Key Features

- Automated tracking: Monitors live games continuously with adaptive polling
- Smart capture timing: Speeds up polling near quarter ends to ensure accurate captures
- Integrated system: Combines ETL, line capturing, and results tracking
- Real-time monitoring: Live database viewer shows captures as they happen
- Middling analysis: Built-in tools to analyze opening vs final and quarter vs final spreads

## Installation

1. Clone the repository
2. Create virtual environment:
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   source .venv/bin/activate  # Linux/Mac

3. Install dependencies:
   pip install -r requirements.txt

4. Configure environment:
   cp .env.example .env
   # Edit .env with your BetsAPI key

5. Initialize database:
   python create_fresh_database.py

## Usage

### Primary Tracking System

Run the integrated tracker (recommended):
python run_integrated_tracker.py

This runs:
- ETL process every 60 seconds (tracks games, updates statuses)
- Quarter monitoring every 10 seconds (captures lines at key moments)
- Adaptive polling that speeds up near quarter ends

### Real-time Monitoring

In a separate terminal, monitor captures in real-time:
python live_db_monitor.py

Shows:
- Table record counts with change indicators
- Recent captures with team names and scores
- Live updates as new data is captured

### Analysis Tools

Analyze opening line middles:
python middling_analysis.py

Analyze quarter-based middles:
python quarter_middling_analysis.py

# Analyze specific quarters:
python quarter_middling_analysis.py --quarters 2  # Q2 (halftime) only
python quarter_middling_analysis.py --quarters 1,3  # Q1 and Q3

## Database Schema

### Core Tables

- event: Game information (teams, times, final scores)
- opener: Opening lines captured at game start
- quarter_line: Lines captured at quarter ends
- result: Calculated deltas between openers and finals

### Example Data Flow

Game Start (Q1 5:00) → Opening line captured
Q1 End (0:10 remaining) → Q1 line captured  
Q2 End (0:10 remaining) → Q2 line captured
Q3 End (0:10 remaining) → Q3 line captured
Game End (Q4 0:00) → Final score captured → Results calculated

## Timing Details

- eBasketball games: ~20 minutes (4 quarters × 5 minutes)
- Peak hours: 9 AM - 11 PM EST (most games)
- Capture threshold: ≤10 seconds remaining in quarter
- Adaptive polling: 15s normal → 5s at 30s → 3s at 20s → 2s at 10s → 1s at 5s

## Configuration

Edit .env file:
BETSAPI_KEY=your_api_key_here
BOOKMAKER_ID=bet365
LEAGUE_IDS=25067
POLL_SECONDS=60

## Best Practices

1. Run during peak hours for maximum data collection
2. Let it run continuously - the longer it runs, the more data you collect
3. Monitor the database periodically to ensure captures are working
4. Check for orphaned records - games without event records won't display properly

## Troubleshooting

No games showing:
- Check if it's peak hours (9 AM - 11 PM EST)
- Verify API key is working: python probe_api.py
- Check for "ebasketball h2h gg league" games specifically

Missing team names:
- Event records might be missing
- The integrated tracker creates these automatically

No opening lines:
- Games must be caught early (Q1 with 4:55-5:00 remaining)
- Window is small (~10 seconds at game start)

No results:
- Games must complete (reach Q4 0:00)
- Results are calculated automatically at game end

## Analysis Outputs

The analysis scripts show:
- Hit rates for various middle sizes (1-5 points for spreads, 2-6 for totals)
- Expected value calculations based on -120 odds
- Distribution analysis of how results cluster around openers
- Sample games that would have hit specific middle sizes

## Files Overview

- run_integrated_tracker.py - Main entry point
- integrated_quarter_tracker.py - Core tracking logic
- live_db_monitor.py - Real-time database viewer
- middling_analysis.py - Opening line analysis
- quarter_middling_analysis.py - Quarter-based analysis
- src/ - Core modules (API client, ETL, database)
- data/ebasketball.db - SQLite database

## Data Privacy & Usage

This tool is for educational and analytical purposes. Please ensure you comply with:
- Your jurisdiction's laws regarding sports betting
- BetsAPI's terms of service
- Responsible data usage practices

## License

This project is for personal/educational use. See LICENSE file for details.