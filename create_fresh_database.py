# create_fresh_database.py
import os
import sqlite3
from datetime import datetime

def create_fresh_database():
    """Create a fresh, clean database with all required tables"""
    
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    
    db_path = "data/ebasketball.db"
    
    # Rename existing database if it exists
    if os.path.exists(db_path):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        old_path = f"data/ebasketball_old_{timestamp}.db"
        os.rename(db_path, old_path)
        print(f"✅ Renamed old database to: {old_path}")
    
    print("\n🔨 Creating fresh database...")
    
    # Create new database with all tables
    with sqlite3.connect(db_path) as con:
        # Enable foreign keys
        con.execute("PRAGMA foreign_keys = ON")
        
        # Create all tables
        con.executescript("""
        -- Main event table
        CREATE TABLE IF NOT EXISTS event(
            event_id INTEGER PRIMARY KEY,
            league_id INTEGER,
            start_time_utc TEXT NOT NULL,
            status TEXT NOT NULL,
            home_name TEXT NOT NULL,
            away_name TEXT NOT NULL,
            final_home INTEGER,
            final_away INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_event_league_time ON event(league_id, start_time_utc);
        CREATE INDEX IF NOT EXISTS idx_event_status ON event(status);

        -- Opening lines table
        CREATE TABLE IF NOT EXISTS opener(
            event_id INTEGER,
            bookmaker_id TEXT,
            market TEXT CHECK (market IN ('spread','total')),
            line REAL NOT NULL,
            price_home REAL,
            price_away REAL,
            opened_at_utc TEXT NOT NULL,
            PRIMARY KEY(event_id, bookmaker_id, market),
            FOREIGN KEY(event_id) REFERENCES event(event_id)
        );

        -- Results analysis table
        CREATE TABLE IF NOT EXISTS result(
            event_id INTEGER PRIMARY KEY,
            spread_delta REAL,
            total_delta REAL,
            within2_spread BOOLEAN, within3_spread BOOLEAN,
            within4_spread BOOLEAN, within5_spread BOOLEAN,
            within2_total BOOLEAN, within3_total BOOLEAN,
            within4_total BOOLEAN, within5_total BOOLEAN,
            FOREIGN KEY(event_id) REFERENCES event(event_id)
        );

        -- Quarter lines table (NEW)
        CREATE TABLE IF NOT EXISTS quarter_line(
            event_id INTEGER NOT NULL,
            bookmaker_id TEXT NOT NULL,
            quarter INTEGER NOT NULL CHECK (quarter IN (1,2,3)),
            market TEXT NOT NULL CHECK (market IN ('spread','total')),
            line REAL NOT NULL,
            captured_at_utc TEXT NOT NULL,
            game_time_remaining INTEGER,
            home_score INTEGER,
            away_score INTEGER,
            PRIMARY KEY(event_id, bookmaker_id, quarter, market),
            FOREIGN KEY(event_id) REFERENCES event(event_id)
        );
        CREATE INDEX IF NOT EXISTS idx_quarter_line_event ON quarter_line(event_id);
        CREATE INDEX IF NOT EXISTS idx_quarter_line_captured ON quarter_line(captured_at_utc);

        -- Optional: odds snapshots for historical tracking
        CREATE TABLE IF NOT EXISTS odds_snapshot(
            event_id INTEGER, 
            bookmaker_id TEXT, 
            market TEXT,
            line REAL, 
            price_home REAL, 
            price_away REAL,
            update_time_utc TEXT,
            PRIMARY KEY(event_id, bookmaker_id, market, update_time_utc)
        );
        """)
        
        con.commit()
        
        # Verify all tables were created
        tables = con.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            ORDER BY name
        """).fetchall()
        
        print("\n✅ Fresh database created with tables:")
        for table in tables:
            print(f"  - {table[0]}")
    
    print(f"\n✅ Fresh database ready at: {db_path}")
    print("\nYou can now run your tracker to start collecting clean data!")

if __name__ == "__main__":
    create_fresh_database()