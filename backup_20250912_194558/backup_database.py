# backup_database.py
import shutil
import os
from datetime import datetime

def backup_database():
    """Create timestamped backup of current database"""
    
    source = "data/ebasketball.db"
    
    if not os.path.exists(source):
        print("No database found to backup")
        return
    
    # Create backup filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = "data/backups"
    os.makedirs(backup_dir, exist_ok=True)
    
    backup_file = f"{backup_dir}/ebasketball_backup_{timestamp}.db"
    
    # Copy the database
    shutil.copy2(source, backup_file)
    print(f"✅ Database backed up to: {backup_file}")
    
    # Show some stats from the backup
    import sqlite3
    with sqlite3.connect(backup_file) as con:
        tables = con.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            ORDER BY name
        """).fetchall()
        
        print("\nBacked up tables:")
        for table in tables:
            count = con.execute(f"SELECT COUNT(*) FROM {table[0]}").fetchone()[0]
            print(f"  - {table[0]}: {count} records")

if __name__ == "__main__":
    backup_database()