# live_db_monitor.py - Fixed version
import sqlite3
import time
import os
from datetime import datetime

DB_PATH = "data/ebasketball.db"

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_recent_entries(table_name, limit=10):
    """Get most recent entries from any table with team info"""
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        
        if table_name == 'quarter_line':
            query = """
                SELECT q.*, e.home_name, e.away_name
                FROM quarter_line q
                LEFT JOIN event e ON e.event_id = q.event_id
                ORDER BY q.captured_at_utc DESC
                LIMIT ?
            """
            return con.execute(query, (limit,)).fetchall()
            
        elif table_name == 'opener':
            query = """
                SELECT o.*, e.home_name, e.away_name
                FROM opener o
                LEFT JOIN event e ON e.event_id = o.event_id
                ORDER BY o.opened_at_utc DESC
                LIMIT ?
            """
            return con.execute(query, (limit,)).fetchall()
        
        else:
            # Original logic for other tables
            time_column = {
                'event': 'start_time_utc',
                'result': 'event_id'
            }.get(table_name, 'event_id')
            
            query = f"""
                SELECT * FROM {table_name} 
                ORDER BY {time_column} DESC 
                LIMIT {limit}
            """
            return con.execute(query).fetchall()

def get_table_counts():
    """Get record counts for all tables"""
    with sqlite3.connect(DB_PATH) as con:
        counts = {}
        tables = ['event', 'opener', 'quarter_line', 'result']
        
        for table in tables:
            count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            counts[table] = count
        
        return counts

def format_event_row(row):
    """Format event table row"""
    status_emoji = {
        'not_started': '⏳',
        'live': '🔴',
        'finished': '✅'
    }.get(row['status'], '❓')
    
    finals = f"{row['final_home']}-{row['final_away']}" if row['final_home'] else "---"
    
    return (f"{status_emoji} FI {row['event_id']} | "
            f"{row['home_name'][:20]:>20} vs {row['away_name'][:20]:<20} | "
            f"{finals:>7} | {row['start_time_utc']}")

def format_opener_row(row):
    """Format opener table row with teams"""
    line_str = f"{row['market']}={row['line']:.1f}"
    
    # Handle team names safely
    home = away = None
    try:
        if row['home_name']:
            home = row['home_name'][:15]
        if row['away_name']:
            away = row['away_name'][:15]
    except (KeyError, TypeError, IndexError):
        pass
    
    if home and away:
        teams = f"{home} vs {away}"
    elif home:
        teams = f"{home} vs ???"
    else:
        teams = f"FI {row['event_id']}"
    
    return (f"FI {row['event_id']} | "
            f"{teams:^35} | "
            f"{line_str:>12} | "
            f"{row['opened_at_utc']}")

def format_quarter_line_row(row):
    """Format quarter_line table row with teams"""
    score = f"{row['home_score']}-{row['away_score']}"
    
    # Handle team names safely - show at least home team
    home = None
    try:
        if row['home_name']:
            home = row['home_name'][:20]
    except (KeyError, TypeError, IndexError):
        pass
    
    if home:
        team_info = home
    else:
        team_info = f"FI {row['event_id']}"
    
    return (f"FI {row['event_id']} | "
            f"Q{row['quarter']} | "
            f"{team_info:^25} | "
            f"{row['market']}={row['line']:.1f} | "
            f"{score:>7} | "
            f"{row['game_time_remaining']:>2}s | "
            f"{row['captured_at_utc'][11:19]}")

def monitor_live(refresh_seconds=5):
    """Live monitoring display"""
    
    print("📊 LIVE DATABASE MONITOR")
    print("Press Ctrl+C to stop")
    print("=" * 100)
    
    last_counts = get_table_counts()
    
    try:
        while True:
            clear_screen()
            
            # Header
            print("📊 EBASKETBALL DATABASE MONITOR")
            print(f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("=" * 100)
            
            # Get current counts
            counts = get_table_counts()
            
            # Table summary with change indicators
            print("\n📈 TABLE SUMMARY:")
            for table, count in counts.items():
                change = count - last_counts.get(table, 0)
                change_str = f" (+{change})" if change > 0 else ""
                print(f"  {table:12} : {count:5} records{change_str}")
            
            # Recent Quarter Lines (most important)
            print("\n🎯 RECENT QUARTER CAPTURES:")
            print("-" * 100)
            quarter_lines = get_recent_entries('quarter_line', 5)
            if quarter_lines:
                for row in quarter_lines:
                    print(f"  {format_quarter_line_row(row)}")
            else:
                print("  No quarter lines captured yet")
            
            # Recent Openers
            print("\n📍 RECENT OPENING LINES:")
            print("-" * 100)
            openers = get_recent_entries('opener', 5)
            if openers:
                for row in openers:
                    print(f"  {format_opener_row(row)}")
            else:
                print("  No opening lines captured yet")
            
            # Active/Recent Games
            print("\n🏀 RECENT GAMES:")
            print("-" * 100)
            events = get_recent_entries('event', 5)
            if events:
                for row in events:
                    print(f"  {format_event_row(row)}")
            else:
                print("  No games tracked yet")
            
            # Update last counts
            last_counts = counts.copy()
            
            # Show what changed
            if any(counts[t] > last_counts.get(t, 0) for t in counts):
                print("\n✨ NEW DATA ADDED! ✨")
            
            print(f"\n🔄 Refreshing every {refresh_seconds} seconds...")
            time.sleep(refresh_seconds)
            
    except KeyboardInterrupt:
        print("\n\n👋 Monitor stopped")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Live database monitor")
    parser.add_argument("--refresh", type=int, default=5, 
                       help="Refresh interval in seconds (default: 5)")
    parser.add_argument("--once", action="store_true", 
                       help="Show once and exit")
    
    args = parser.parse_args()
    
    if args.once:
        # Just show current state
        counts = get_table_counts()
        print("\n📊 DATABASE SNAPSHOT")
        print("=" * 100)
        for table, count in counts.items():
            print(f"{table:12} : {count:5} records")
        
        print("\nRecent quarter captures:")
        for row in get_recent_entries('quarter_line', 3):
            print(f"  {format_quarter_line_row(row)}")
    else:
        monitor_live(args.refresh)

if __name__ == "__main__":
    main()