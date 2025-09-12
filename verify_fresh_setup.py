# verify_fresh_setup.py
import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

def verify_setup():
    """Verify the fresh database is ready"""
    
    db_path = "data/ebasketball.db"
    
    if not os.path.exists(db_path):
        print("❌ Database not found!")
        return False
    
    print("🔍 Verifying fresh database setup...\n")
    
    with sqlite3.connect(db_path) as con:
        # Check tables
        tables = con.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            ORDER BY name
        """).fetchall()
        
        required_tables = ['event', 'opener', 'result', 'quarter_line']
        
        print("📊 Table Status:")
        for req_table in required_tables:
            found = any(t[0] == req_table for t in tables)
            if found:
                print(f"  ✅ {req_table} - exists")
            else:
                print(f"  ❌ {req_table} - MISSING!")
    
    # Check environment
    print("\n🔑 Environment:")
    api_key = os.getenv("BETSAPI_KEY")
    if api_key:
        print(f"  ✅ BETSAPI_KEY is set")
    else:
        print(f"  ❌ BETSAPI_KEY is missing!")
    
    print("\n✅ Fresh database is ready to use!")
    print("\nStart collecting data with:")
    print("  python run_integrated_tracker.py")
    
    return True

if __name__ == "__main__":
    verify_setup()