# performance_optimizer.py - Analyze and optimize system performance
import sqlite3
import time
from datetime import datetime

DB = "data/ebasketball.db"

def analyze_db_performance():
    print("⚡ DATABASE PERFORMANCE ANALYSIS")
    print("=" * 50)
    
    with sqlite3.connect(DB) as con:
        # 1. Table sizes
        print("\n1️⃣ TABLE SIZES")
        tables = ['event', 'opener', 'result', 'odds_snapshot', 'quarter_line']
        for table in tables:
            try:
                count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                print(f"  {table}: {count:,} rows")
            except:
                print(f"  {table}: table not found")
        
        # 2. Index analysis
        print("\n2️⃣ INDEX ANALYSIS")
        indexes = con.execute("""
            SELECT name, tbl_name, sql 
            FROM sqlite_master 
            WHERE type='index' AND sql IS NOT NULL
            ORDER BY tbl_name
        """).fetchall()
        
        for idx in indexes:
            print(f"  {idx[1]}.{idx[0]}")
        
        # 3. Query performance test
        print("\n3️⃣ QUERY PERFORMANCE TESTS")
        queries = [
            ("Recent events", "SELECT COUNT(*) FROM event WHERE start_time_utc >= datetime('now', '-24 hours')"),
            ("Events with openers", "SELECT COUNT(DISTINCT e.event_id) FROM event e JOIN opener o ON o.event_id = e.event_id"),
            ("Accuracy calculation", "SELECT AVG(CASE WHEN within5_spread THEN 1.0 ELSE 0.0 END) FROM result"),
            ("Complex join", """
                SELECT COUNT(*) FROM event e 
                LEFT JOIN opener o ON o.event_id = e.event_id 
                LEFT JOIN result r ON r.event_id = e.event_id 
                WHERE e.start_time_utc >= datetime('now', '-7 days')
            """)
        ]
        
        for name, query in queries:
            start = time.time()
            con.execute(query).fetchone()
            duration = time.time() - start
            print(f"  {name}: {duration*1000:.1f}ms")

def suggest_optimizations():
    print("\n4️⃣ OPTIMIZATION SUGGESTIONS")
    
    with sqlite3.connect(DB) as con:
        # Check for missing indexes
        event_count = con.execute("SELECT COUNT(*) FROM event").fetchone()[0]
        opener_count = con.execute("SELECT COUNT(*) FROM opener").fetchone()[0]
        
        suggestions = []
        
        if event_count > 10000:
            suggestions.append("Consider partitioning old events (>30 days)")
        
        if opener_count > 50000:
            suggestions.append("Consider archiving old opener data")
            
        # Check for inefficient queries
        try:
            # Test a potentially slow query
            start = time.time()
            con.execute("""
                SELECT e.event_id, COUNT(o.market) 
                FROM event e 
                LEFT JOIN opener o ON o.event_id = e.event_id 
                GROUP BY e.event_id 
                LIMIT 1000
            """).fetchall()
            duration = time.time() - start
            
            if duration > 0.1:
                suggestions.append("Add composite index on opener(event_id, market)")
        except:
            pass
        
        if suggestions:
            for i, suggestion in enumerate(suggestions, 1):
                print(f"  {i}. {suggestion}")
        else:
            print("  ✅ No immediate optimizations needed")

def create_recommended_indexes():
    print("\n5️⃣ RECOMMENDED INDEX CREATION")
    
    indexes_to_create = [
        "CREATE INDEX IF NOT EXISTS idx_event_start_status ON event(start_time_utc, status)",
        "CREATE INDEX IF NOT EXISTS idx_opener_event_market ON opener(event_id, market)",
        "CREATE INDEX IF NOT EXISTS idx_opener_opened_at ON opener(opened_at_utc)",
        "CREATE INDEX IF NOT EXISTS idx_result_flags ON result(within5_spread, within5_total)"
    ]
    
    with sqlite3.connect(DB) as con:
        for idx_sql in indexes_to_create:
            try:
                start = time.time()
                con.execute(idx_sql)
                duration = time.time() - start
                idx_name = idx_sql.split("IF NOT EXISTS ")[1].split(" ON")[0]
                print(f"  ✅ Created {idx_name} ({duration*1000:.1f}ms)")
            except Exception as e:
                print(f"  ⚠️  Failed to create index: {e}")

def cleanup_old_data():
    print("\n6️⃣ DATA CLEANUP RECOMMENDATIONS")
    
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        
        # Check for old data
        old_events = con.execute("""
            SELECT COUNT(*) as count 
            FROM event 
            WHERE start_time_utc < datetime('now', '-30 days')
        """).fetchone()['count']
        
        old_snapshots = con.execute("""
            SELECT COUNT(*) as count 
            FROM odds_snapshot 
            WHERE update_time_utc < datetime('now', '-7 days')
        """).fetchone()['count'] if con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='odds_snapshot'").fetchone() else 0
        
        print(f"  Events older than 30 days: {old_events:,}")
        print(f"  Odds snapshots older than 7 days: {old_snapshots:,}")
        
        if old_events > 0:
            print(f"  💡 Consider archiving events older than 30 days")
        
        if old_snapshots > 1000:
            print(f"  💡 Consider cleaning old odds snapshots")

def run_full_analysis():
    analyze_db_performance()
    suggest_optimizations()
    create_recommended_indexes()
    cleanup_old_data()
    
    print(f"\n🎯 ANALYSIS COMPLETE")
    print(f"Run this regularly to maintain optimal performance!")

if __name__ == "__main__":
    run_full_analysis()