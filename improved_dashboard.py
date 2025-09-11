# improved_dashboard.py - Fixed status detection and timezone handling
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

from src import betsapi

DB = "data/ebasketball.db"

def get_actual_game_status(event_id, db_status, start_time_str):
    """Get the real status of a game by checking API"""
    try:
        # Check multiple API endpoints for status
        fast = betsapi.get_event_score_fast(event_id) or {}
        result = betsapi.get_event_result(event_id) or {}
        
        # Get time_status from fast endpoint
        ts = str(fast.get("time_status") or "")
        
        # Get score info
        ss = fast.get("SS") or fast.get("ss")
        live_score = ss if isinstance(ss, str) and "-" in ss else None
        
        # Check if finished via result endpoint
        has_result_finals = (result.get("final_home") is not None and result.get("final_away") is not None)
        
        # Determine actual status
        if ts == "3" or has_result_finals:
            actual_status = "finished"
            final_score = None
            if has_result_finals:
                final_score = f"{result['final_home']}-{result['final_away']}"
            elif live_score:
                final_score = live_score
        elif ts == "1" or (live_score and ts != "0"):
            actual_status = "live"
            final_score = live_score
        elif ts == "0":
            actual_status = "not_started"
            final_score = None
        else:
            # Check if game should have started based on time
            try:
                start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                if start_time.tzinfo is None:
                    start_time = start_time.replace(tzinfo=timezone.utc)
                
                now = datetime.now(timezone.utc)
                minutes_since_start = (now - start_time).total_seconds() / 60
                
                if minutes_since_start > 30:  # Game should have finished (4x5min = 20min + buffer)
                    actual_status = "unknown_old"
                elif minutes_since_start > 0:  # Game should have started
                    actual_status = "unknown_started"
                else:
                    actual_status = "not_started"
            except:
                actual_status = "unknown"
            
            final_score = live_score
        
        return actual_status, final_score, ts
        
    except Exception as e:
        return "api_error", None, None

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

def get_recent_games_with_status():
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        games = con.execute("""
            SELECT event_id, start_time_utc, home_name, away_name, status, final_home, final_away
            FROM event 
            WHERE start_time_utc >= datetime('now', '-3 hours')
            ORDER BY start_time_utc DESC
            LIMIT 20
        """).fetchall()
    
    # Check actual status for each game
    enhanced_games = []
    for game in games:
        actual_status, live_score, api_ts = get_actual_game_status(
            int(game['event_id']), 
            game['status'], 
            game['start_time_utc']
        )
        
        enhanced_games.append({
            'event_id': game['event_id'],
            'start_time_utc': game['start_time_utc'],
            'home_name': game['home_name'],
            'away_name': game['away_name'],
            'db_status': game['status'],
            'actual_status': actual_status,
            'db_final': f"{game['final_home']}-{game['final_away']}" if game['final_home'] else None,
            'live_score': live_score,
            'api_ts': api_ts
        })
    
    return enhanced_games

def create_dashboard():
    console = Console()
    stats, opener_stats, accuracy = get_stats()
    recent_games = get_recent_games_with_status()
    
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
    
    # Recent games table with better status detection
    table = Table(title="Recent Games (3h) - Live Status Check", show_header=True, header_style="bold magenta")
    table.add_column("Start", style="dim", width=8)
    table.add_column("Status", width=12)
    table.add_column("Matchup", style="blue", no_wrap=True)
    table.add_column("Score", width=10)
    table.add_column("Issues", width=8)
    
    status_issues = 0
    for game in recent_games:
        # Parse start time and convert to local display
        try:
            start_utc = datetime.fromisoformat(game['start_time_utc'])
            if start_utc.tzinfo is None:
                start_utc = start_utc.replace(tzinfo=timezone.utc)
            
            # Convert to your local time (assuming EST/EDT)
            local_time = start_utc - timedelta(hours=4)  # Adjust this for your timezone
            start_display = local_time.strftime("%H:%M")
        except:
            start_display = "??:??"
        
        # Status with emoji and color
        actual = game['actual_status']
        if actual == "finished":
            status_display = "✅ Finished"
            status_style = "green"
        elif actual == "live":
            status_display = "🔴 LIVE"
            status_style = "red"
        elif actual == "not_started":
            status_display = "⏳ Not Started"
            status_style = "yellow"
        elif actual == "unknown_old":
            status_display = "❓ Old Game"
            status_style = "red"
            status_issues += 1
        elif actual == "unknown_started":
            status_display = "❓ Started?"
            status_style = "yellow"
            status_issues += 1
        else:
            status_display = f"❓ {actual}"
            status_style = "dim"
            status_issues += 1
        
        # Truncate team names
        matchup = f"{game['home_name']} vs {game['away_name']}"
        if len(matchup) > 35:
            matchup = matchup[:32] + "..."
        
        # Score display
        score = game['live_score'] or game['db_final'] or "—"
        
        # Issues column
        issues = ""
        if game['db_status'] != actual and actual not in ['unknown', 'api_error']:
            issues += "🔄"  # Status mismatch
        if game['api_ts']:
            issues += f"({game['api_ts']})"
        
        table.add_row(start_display, status_display, matchup, score, issues)
    
    layout["right"].update(table)
    
    # Footer with health status
    if status_issues == 0:
        health_status = "🟢 HEALTHY"
        footer_style = "bold green"
    elif status_issues <= 2:
        health_status = f"🟡 {status_issues} ISSUES"
        footer_style = "bold yellow"
    else:
        health_status = f"🔴 {status_issues} ISSUES"
        footer_style = "bold red"
    
    layout["footer"].update(Panel(f"System Status: {health_status} | Live API checks enabled | Press Ctrl+C to exit", style=footer_style))
    
    return layout

def run_live_dashboard():
    console = Console()
    
    with Live(create_dashboard(), refresh_per_second=0.5, console=console) as live:
        try:
            while True:
                time.sleep(5)  # Update every 5 seconds (slower due to API calls)
                live.update(create_dashboard())
        except KeyboardInterrupt:
            console.print("\n👋 Dashboard stopped")

if __name__ == "__main__":
    run_live_dashboard()