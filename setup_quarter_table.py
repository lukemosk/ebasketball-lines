# setup_quarter_table.py
import sqlite3
import os

DB_PATH = "data/ebasketball.db"

def create_quarter_table():
    """Create the quarter_line table if it doesn't exist"""
    
    # Ensure the data directory exists
    os.makedirs("data", exist_ok=True)
    
    print("Creating quarter_line table...")
    
    with sqlite3.connect(DB_PATH) as con:
        # Create the table
        con.execute("""
            CREATE TABLE IF NOT EXISTS quarter_line (
                event_id INTEGER NOT NULL,
                bookmaker_id TEXT NOT NULL,
                quarter INTEGER NOT NULL CHECK (quarter IN (1,2,3,4)),
                market TEXT NOT NULL CHECK (market IN ('spread','total')),
                line REAL NOT NULL,
                captured_at_utc TEXT NOT NULL,
                game_time_remaining INTEGER,
                home_score INTEGER,
                away_score INTEGER,
                PRIMARY KEY (event_id, bookmaker_id, quarter, market),
                FOREIGN KEY (event_id) REFERENCES event(event_id)
            )
        """)
        con.commit()
        
        # Verify it was created
        cursor = con.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='quarter_line'
        """)
        
        if cursor.fetchone():
            print("✅ quarter_line table created successfully!")
            
            # Check if it's empty
            count = con.execute("SELECT COUNT(*) FROM quarter_line").fetchone()[0]
            print(f"   Current records: {count}")
        else:
            print("❌ Failed to create table")
            return False
    
    return True

def verify_setup():
    """Verify all required tables exist"""
    print("\nVerifying database setup...")
    
    required_tables = ['event', 'opener', 'result', 'quarter_line']
    
    with sqlite3.connect(DB_PATH) as con:
        for table in required_tables:
            cursor = con.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name=?
            """, (table,))
            
            if cursor.fetchone():
                count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                print(f"✅ {table}: {count} records")
            else:
                print(f"❌ {table}: MISSING")

if __name__ == "__main__":
    if create_quarter_table():
        verify_setup()
    else:
        print("Setup failed!")