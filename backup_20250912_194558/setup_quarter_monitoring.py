# setup_quarter_monitoring.py - Initialize quarter line monitoring
import sqlite3
import os
from src.db import engine
from sqlalchemy import text

def setup_quarter_tables():
    """Create/update database tables for quarter line tracking"""
    print("🔧 Setting up quarter line monitoring tables...")
    
    # Read the schema update SQL
    schema_sql = """
    -- Ensure the quarter_line table exists with proper structure
    CREATE TABLE IF NOT EXISTS quarter_line(
      event_id INTEGER NOT NULL,
      bookmaker_id TEXT NOT NULL,
      market TEXT NOT NULL CHECK (market IN ('spread','total')),
      quarter INTEGER NOT NULL CHECK (quarter IN (1,2,3)),
      line REAL NOT NULL,
      captured_at_utc TEXT NOT NULL,
      PRIMARY KEY(event_id, bookmaker_id, market, quarter),
      FOREIGN KEY(event_id) REFERENCES event(event_id)
    );

    -- Create index for efficient querying
    CREATE INDEX IF NOT EXISTS idx_quarter_line_event ON quarter_line(event_id);
    CREATE INDEX IF NOT EXISTS idx_quarter_line_captured ON quarter_line(captured_at_utc);

    -- Drop existing view if it exists (in case we're updating it)
    DROP VIEW IF EXISTS quarter_analysis;

    -- Add a view for easier quarter analysis
    CREATE VIEW quarter_analysis AS
    SELECT 
        e.event_id,
        e.home_name,
        e.away_name,
        e.final_home,
        e.final_away,
        e.start_time_utc,
        
        -- Pregame opener lines
        MAX(CASE WHEN o.market='spread' THEN o.line END) as opener_spread,
        MAX(CASE WHEN o.market='total' THEN o.line END) as opener_total,
        
        -- Q1 lines
        MAX(CASE WHEN ql.quarter=1 AND ql.market='spread' THEN ql.line END) as q1_spread,
        MAX(CASE WHEN ql.quarter=1 AND ql.market='total' THEN ql.line END) as q1_total,
        
        -- Q2 lines
        MAX(CASE WHEN ql.quarter=2 AND ql.market='spread' THEN ql.line END) as q2_spread,
        MAX(CASE WHEN ql.quarter=2 AND ql.market='total' THEN ql.line END) as q2_total,
        
        -- Q3 lines
        MAX(CASE WHEN ql.quarter=3 AND ql.market='spread' THEN ql.line END) as q3_spread,
        MAX(CASE WHEN ql.quarter=3 AND ql.market='total' THEN ql.line END) as q3_total,
        
        -- Calculate deltas (handle NULL cases)
        CASE WHEN MAX(CASE WHEN o.market='spread' THEN o.line END) IS NOT NULL 
             THEN ABS(ABS(e.final_home - e.final_away) - ABS(MAX(CASE WHEN o.market='spread' THEN o.line END))) 
             ELSE NULL END as opener_spread_delta,
        CASE WHEN MAX(CASE WHEN o.market='total' THEN o.line END) IS NOT NULL 
             THEN ABS((e.final_home + e.final_away) - MAX(CASE WHEN o.market='total' THEN o.line END)) 
             ELSE NULL END as opener_total_delta,
        
        CASE WHEN MAX(CASE WHEN ql.quarter=1 AND ql.market='spread' THEN ql.line END) IS NOT NULL 
             THEN ABS(ABS(e.final_home - e.final_away) - ABS(MAX(CASE WHEN ql.quarter=1 AND ql.market='spread' THEN ql.line END))) 
             ELSE NULL END as q1_spread_delta,
        CASE WHEN MAX(CASE WHEN ql.quarter=1 AND ql.market='total' THEN ql.line END) IS NOT NULL 
             THEN ABS((e.final_home + e.final_away) - MAX(CASE WHEN ql.quarter=1 AND ql.market='total' THEN ql.line END)) 
             ELSE NULL END as q1_total_delta,
        
        CASE WHEN MAX(CASE WHEN ql.quarter=2 AND ql.market='spread' THEN ql.line END) IS NOT NULL 
             THEN ABS(ABS(e.final_home - e.final_away) - ABS(MAX(CASE WHEN ql.quarter=2 AND ql.market='spread' THEN ql.line END))) 
             ELSE NULL END as q2_spread_delta,
        CASE WHEN MAX(CASE WHEN ql.quarter=2 AND ql.market='total' THEN ql.line END) IS NOT NULL 
             THEN ABS((e.final_home + e.final_away) - MAX(CASE WHEN ql.quarter=2 AND ql.market='total' THEN ql.line END)) 
             ELSE NULL END as q2_total_delta,
        
        CASE WHEN MAX(CASE WHEN ql.quarter=3 AND ql.market='spread' THEN ql.line END) IS NOT NULL 
             THEN ABS(ABS(e.final_home - e.final_away) - ABS(MAX(CASE WHEN ql.quarter=3 AND ql.market='spread' THEN ql.line END))) 
             ELSE NULL END as q3_spread_delta,
        CASE WHEN MAX(CASE WHEN ql.quarter=3 AND ql.market='total' THEN ql.line END) IS NOT NULL 
             THEN ABS((e.final_home + e.final_away) - MAX(CASE WHEN ql.quarter=3 AND ql.market='total' THEN ql.line END)) 
             ELSE NULL END as q3_total_delta

    FROM event e
    LEFT JOIN opener o ON o.event_id = e.event_id
    LEFT JOIN quarter_line ql ON ql.event_id = e.event_id
    WHERE e.final_home IS NOT NULL AND e.final_away IS NOT NULL
    GROUP BY e.event_id, e.home_name, e.away_name, e.final_home, e.final_away, e.start_time_utc;
    """
    
    # Execute the schema updates
    if engine.url.get_backend_name() == "sqlite":
        # Use raw sqlite connection for executescript
        raw = engine.raw_connection()
        try:
            cur = raw.cursor()
            cur.executescript(schema_sql)
            raw.commit()
            print("✅ Quarter line tables created successfully")
        finally:
            raw.close()
    else:
        # For other databases, split and execute individually
        statements = [s.strip() for s in schema_sql.split(';') if s.strip()]
        with engine.begin() as conn:
            for stmt in statements:
                conn.execute(text(stmt))
        print("✅ Quarter line tables created successfully")

def test_quarter_tables():
    """Test that the tables were created properly"""
    print("\n🧪 Testing quarter line tables...")
    
    with sqlite3.connect("data/ebasketball.db") as con:
        con.row_factory = sqlite3.Row
        
        # Test quarter_line table
        try:
            count = con.execute("SELECT COUNT(*) as count FROM quarter_line").fetchone()['count']
            print(f"✅ quarter_line table: {count} records")
        except Exception as e:
            print(f"❌ quarter_line table error: {e}")
            return False
        
        # Test quarter_analysis view
        try:
            count = con.execute("SELECT COUNT(*) as count FROM quarter_analysis").fetchone()['count']
            print(f"✅ quarter_analysis view: {count} records")
        except Exception as e:
            print(f"❌ quarter_analysis view error: {e}")
            return False
        
        # Test a sample query
        try:
            sample = con.execute("""
                SELECT event_id, home_name, away_name, opener_spread, q1_spread, q2_spread, q3_spread
                FROM quarter_analysis 
                LIMIT 3
            """).fetchall()
            
            if sample:
                print(f"✅ Sample data available ({len(sample)} games with finished results)")
                for row in sample:
                    quarters_available = sum(1 for q in [row['q1_spread'], row['q2_spread'], row['q3_spread']] if q is not None)
                    print(f"   FI {row['event_id']}: {row['home_name']} vs {row['away_name']} - {quarters_available}/3 quarter lines")
            else:
                print("ℹ️  No finished games with quarter data yet (expected for new setup)")
                
        except Exception as e:
            print(f"❌ Sample query error: {e}")
            return False
    
    return True

def create_run_scripts():
    """Create convenience scripts for running the quarter monitor"""
    
    # Create a standalone quarter monitor script
    quarter_runner = """# run_quarter_monitor.py - Standalone quarter monitor runner
from live_quarter_monitor import LiveQuarterMonitor
import sys

def main():
    print("🏀 EBasketball Quarter Line Monitor")
    print("This will monitor live games and capture lines at quarter endings")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    
    cycles = None
    if len(sys.argv) > 1:
        try:
            cycles = int(sys.argv[1])
            print(f"Running for {cycles} cycles only")
        except:
            print("Invalid cycle count, running indefinitely")
    
    monitor = LiveQuarterMonitor()
    monitor.run(cycles=cycles)

if __name__ == "__main__":
    main()
"""
    
    with open("run_quarter_monitor.py", "w") as f:
        f.write(quarter_runner)
    
    print("✅ Created run_quarter_monitor.py")
    
    # Create an integrated tracker that includes quarter monitoring
    integrated_tracker = """# run_integrated_tracker.py - Full tracker with quarter monitoring
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import time
import subprocess
import threading
from live_quarter_monitor import LiveQuarterMonitor

class IntegratedTracker:
    def __init__(self):
        self.quarter_monitor = None
        self.monitor_thread = None
        self.running = True
    
    def start_quarter_monitor(self):
        \"\"\"Start quarter monitoring in a separate thread\"\"\"
        def monitor_worker():
            self.quarter_monitor = LiveQuarterMonitor()
            # Run indefinitely until stopped
            while self.running:
                try:
                    self.quarter_monitor.monitor_cycle()
                    time.sleep(10)  # 10 second polling
                except Exception as e:
                    print(f"Quarter monitor error: {e}")
                    time.sleep(30)  # Wait longer on error
        
        self.monitor_thread = threading.Thread(target=monitor_worker, daemon=True)
        self.monitor_thread.start()
        print("🔴 Quarter monitoring started in background")
    
    def run_etl_cycle(self):
        \"\"\"Run the standard ETL cycle\"\"\"
        print("\\n=== ETL ===")
        subprocess.run([r".\\.venv\\Scripts\\python.exe", "-m", "src.etl"])
        print("=== Openers ===")
        subprocess.run([r".\\.venv\\Scripts\\python.exe", "backfill_openers.py"])
        print("=== Retry Missing Openers ===")
        subprocess.run([r".\\.venv\\Scripts\\python.exe", "-m", "src.backfill_openers_retry_missing"])
        print("=== Results ===")
        subprocess.run([r".\\.venv\\Scripts\\python.exe", "backfill_results.py"])
    
    def run(self):
        POLL_SECONDS = 60  # Main ETL cycle every 60 seconds
        
        print("🏀 INTEGRATED EBASKETBALL TRACKER")
        print("- Standard ETL every 60 seconds")
        print("- Live quarter monitoring every 10 seconds")
        print("- Press Ctrl+C to stop")
        print("=" * 60)
        
        # Start quarter monitoring
        self.start_quarter_monitor()
        
        try:
            while True:
                self.run_etl_cycle()
                print(f"Sleeping {POLL_SECONDS}s... (quarter monitor running in background)")
                time.sleep(POLL_SECONDS)
        except KeyboardInterrupt:
            print("\\n👋 Stopping integrated tracker...")
            self.running = False
            if self.monitor_thread:
                self.monitor_thread.join(timeout=2)

def main():
    tracker = IntegratedTracker()
    tracker.run()

if __name__ == "__main__":
    main()
"""
    
    with open("run_integrated_tracker.py", "w") as f:
        f.write(integrated_tracker)
    
    print("✅ Created run_integrated_tracker.py")

def main():
    print("🏀 QUARTER LINE MONITORING SETUP")
    print("=" * 50)
    
    # Setup database tables
    setup_quarter_tables()
    
    # Test the setup
    if not test_quarter_tables():
        print("\n❌ Setup failed - please check the errors above")
        return
    
    # Create runner scripts
    create_run_scripts()
    
    print("\n✅ SETUP COMPLETE!")
    print("\nNext Steps:")
    print("1. To test quarter monitoring:")
    print("   python run_quarter_monitor.py")
    print()
    print("2. To run full integrated tracking (ETL + quarter monitoring):")
    print("   python run_integrated_tracker.py")
    print()
    print("3. To analyze quarter data (after collecting some):")
    print("   python quarter_analysis.py")
    print()
    print("The quarter monitor will:")
    print("- Monitor live games every 10 seconds")
    print("- Detect when quarters end (≤5 seconds remaining)")
    print("- Capture spread/total lines at Q1, Q2, Q3 endings")
    print("- Store lines in quarter_line table")
    print("- Allow analysis vs final game results")
    print()
    print("Best times to run:")
    print("- Typically 9 AM - 11 PM EST when eBasketball games are active")
    print("- Games are ~20 minutes long (4x5min quarters)")

if __name__ == "__main__":
    main()