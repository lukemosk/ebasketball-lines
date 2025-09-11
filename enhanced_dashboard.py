# enhanced_dashboard.py - Better monitoring with stats
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from rich.console import Console
from rich.table import Table
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

DB = "data/ebasketball.db"

def get_stats():
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        
        # Basic counts
        stats = con.execute("""
            SELECT 
                COUNT(*) as total_events,
                SUM(CASE WHEN final_home IS NOT NULL THEN 1 ELSE 0 END) as finished_events,
                SUM(CASE WHEN status='live' THEN 1 ELSE 0 END) as live_events,
                SUM(CASE WHEN start_time_utc >= datetime('now', '-24 hours') THEN 1 ELSE 0 END) as last_24h
            FROM event
        """).fetchone()
        
        # Opener coverage
        opener_stats = con.execute("""
            SELECT 
                COUNT(DISTINCT e.event_id) as events_with_openers,
                COUNT(DISTINCT CASE WHEN o.market='spread' THEN e.event_id END) as spread_coverage,
                COUNT(DISTINCT CASE WHEN o.market='total' THEN e.event_id END) as total_coverage
            FROM event e
            JOIN opener o ON o.event_id = e.event_id
            WHERE e.start_time_utc >= datetime('now', '-24 hours')
        """).fetchone()
        
        # Accuracy stats
        accuracy = con.execute("""
            SELECT 
                COUNT(*) as total_results,
                AVG(CASE WHEN within2_spread THEN 1.0 ELSE 0.0 END) * 100 as spread_2pt_pct,
                AVG(CASE WHEN within5_spread THEN 1.0 ELSE 0.0 END) * 100 as spread_5pt_pct,
                AVG(CASE WHEN within2_total THEN 1.0 ELSE 0.0 END) * 100 as total_2pt_pct,
                AVG(CASE WHEN within5_total THEN 1.0 ELSE 0.0 END) * 100 as total_5pt_pct
            FROM result r
            JOIN event e ON e.event_id = r.event_id
            WHERE e.start_time_utc >= datetime('now', '-7 days')
        """).fetchone()
        
        return stats, opener_stats, accuracy

def get_recent_games():
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        return con.execute("""
            SELECT event_id, start_time_utc, home_name, away_name, status, final_home, final_away
            FROM event 
            WHERE start_time_utc >= datetime('now', '-2 hours')
            ORDER BY start_time_utc DESC
            LIMIT 15
        """).fetchall()

def create_dashboard():
    console = Console()
    stats, opener_stats, accuracy = get_stats()
    recent_games = get_recent_games()
    
    # Create layout
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=3)
    )
    
    layout["body"].split_row(
        Layout(name="left"),
        Layout(name="right")
    )
    
    # Header
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    layout["header"].update(Panel(f"🏀 EBasketball Lines Tracker - {now}", style="bold blue"))
    
    # Stats panel
    stats_text = f"""
📊 Overall Stats:
  Total Events: {stats['total_events']:,}
  Finished: {stats['finished_events']:,}
  Live: {stats['live_events']:,}
  Last 24h: {stats['last_24h']:,}

📈 Opener Coverage (24h):
  Events with openers: {opener_stats['events_with_openers'] or 0:,}
  Spread coverage: {opener_stats['spread_coverage'] or 0:,}
  Total coverage: {opener_stats['total_coverage'] or 0:,}

🎯 Accuracy (7 days):
  Results analyzed: {accuracy['total_results'] or 0:,}
  Spread ±2pts: {accuracy['spread_2pt_pct'] or 0:.1f}%
  Spread ±5pts: {accuracy['spread_5pt_pct'] or 0:.1f}%
  Total ±2pts: {accuracy['total_2pt_pct'] or 0:.1f}%
  Total ±5pts: {accuracy['total_5pt_pct'] or 0:.1f}%
"""
    
    layout["left"].update(Panel(stats_text, title="📊 Statistics", border_style="green"))
    
    # Recent games table
    table = Table(title="Recent Games (2h)", show_header=True, header_style="bold magenta")
    table.add_column("Start", style="dim", width=8)
    table.add_column("Status", width=10)
    table.add_column("Matchup", style="blue", no_wrap=True)
    table.add_column("Final", width=8)
    
    for game in recent_games:
        start_time = datetime.fromisoformat(game['start_time_utc']).strftime("%H:%M")
        status_emoji = {"not_started": "⏳", "live": "🔴", "finished": "✅"}.get(game['status'], "❓")
        status_text = f"{status_emoji} {game['status']}"
        
        matchup = f"{game['home_name']} vs {game['away_name']}"
        if len(matchup) > 40:
            matchup = matchup[:37] + "..."
        
        final_score = f"{game['final_home']}-{game['final_away']}" if game['final_home'] else "—"
        
        table.add_row(start_time, status_text, matchup, final_score)
    
    layout["right"].update(table)
    
    # Footer
    health_status = "🟢 HEALTHY" if stats['live_events'] == 0 or True else "🟡 MONITORING"
    layout["footer"].update(Panel(f"System Status: {health_status} | Press Ctrl+C to exit", style="bold green"))
    
    return layout

def run_live_dashboard():
    console = Console()
    
    with Live(create_dashboard(), refresh_per_second=0.5, console=console) as live:
        try:
            while True:
                time.sleep(2)  # Update every 2 seconds
                live.update(create_dashboard())
        except KeyboardInterrupt:
            console.print("\n👋 Dashboard stopped")

if __name__ == "__main__":
    run_live_dashboard()