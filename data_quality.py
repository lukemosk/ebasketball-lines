# data_quality.py - Comprehensive data quality analysis
import sqlite3
from datetime import datetime, timedelta

DB = "data/ebasketball.db"

def run_quality_checks():
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        
        print("🔍 DATA QUALITY ANALYSIS")
        print("=" * 50)
        
        # 1. Opener timing analysis
        print("\n1️⃣ OPENER TIMING ANALYSIS")
        opener_timing = con.execute("""
            WITH timing AS (
                SELECT 
                    e.event_id,
                    e.start_time_utc,
                    o.opened_at_utc,
                    o.market,
                    JULIANDAY(e.start_time_utc) - JULIANDAY(o.opened_at_utc) AS hours_before_start
                FROM event e
                JOIN opener o ON o.event_id = e.event_id
                WHERE e.start_time_utc >= datetime('now', '-7 days')
                AND o.opened_at_utc < e.start_time_utc
            )
            SELECT 
                market,
                COUNT(*) as count,
                AVG(hours_before_start * 24) as avg_hours_early,
                MIN(hours_before_start * 24) as min_hours_early,
                MAX(hours_before_start * 24) as max_hours_early
            FROM timing
            GROUP BY market
        """).fetchall()
        
        for row in opener_timing:
            print(f"  {row['market'].upper()}: {row['count']} openers")
            print(f"    Avg {row['avg_hours_early']:.1f}h early | Range: {row['min_hours_early']:.1f}h - {row['max_hours_early']:.1f}h")
        
        # 2. Missing data analysis
        print("\n2️⃣ MISSING DATA ANALYSIS")
        missing_data = con.execute("""
            SELECT 
                COUNT(*) as total_games_7d,
                SUM(CASE WHEN sp.event_id IS NULL THEN 1 ELSE 0 END) as missing_spread,
                SUM(CASE WHEN tt.event_id IS NULL THEN 1 ELSE 0 END) as missing_total,
                SUM(CASE WHEN e.final_home IS NULL AND e.start_time_utc < datetime('now', '-2 hours') THEN 1 ELSE 0 END) as missing_finals,
                SUM(CASE WHEN r.event_id IS NULL AND e.final_home IS NOT NULL THEN 1 ELSE 0 END) as missing_results
            FROM event e
            LEFT JOIN opener sp ON sp.event_id = e.event_id AND sp.market = 'spread'
            LEFT JOIN opener tt ON tt.event_id = e.event_id AND tt.market = 'total'
            LEFT JOIN result r ON r.event_id = e.event_id
            WHERE e.start_time_utc >= datetime('now', '-7 days')
        """).fetchone()
        
        total = missing_data['total_games_7d']
        print(f"  Total games (7d): {total}")
        print(f"  Missing spread openers: {missing_data['missing_spread']} ({missing_data['missing_spread']/total*100:.1f}%)")
        print(f"  Missing total openers: {missing_data['missing_total']} ({missing_data['missing_total']/total*100:.1f}%)")
        print(f"  Missing finals (>2h old): {missing_data['missing_finals']}")
        print(f"  Missing result calculations: {missing_data['missing_results']}")
        
        # 3. Spread/Total distribution analysis
        print("\n3️⃣ SPREAD/TOTAL DISTRIBUTION")
        distribution = con.execute("""
            SELECT 
                'spread' as type,
                MIN(line) as min_val,
                AVG(line) as avg_val,
                MAX(line) as max_val,
                COUNT(*) as count
            FROM opener WHERE market = 'spread'
            UNION ALL
            SELECT 
                'total' as type,
                MIN(line) as min_val,
                AVG(line) as avg_val,
                MAX(line) as max_val,
                COUNT(*) as count
            FROM opener WHERE market = 'total'
        """).fetchall()
        
        for row in distribution:
            print(f"  {row['type'].upper()}: {row['count']} values")
            print(f"    Range: {row['min_val']:.1f} - {row['max_val']:.1f} | Avg: {row['avg_val']:.1f}")
        
        # 4. Unusual values detection
        print("\n4️⃣ UNUSUAL VALUES DETECTION")
        unusual = con.execute("""
            SELECT 'High Total' as issue, COUNT(*) as count
            FROM opener WHERE market = 'total' AND line > 200
            UNION ALL
            SELECT 'Low Total' as issue, COUNT(*) as count
            FROM opener WHERE market = 'total' AND line < 50
            UNION ALL
            SELECT 'High Spread' as issue, COUNT(*) as count
            FROM opener WHERE market = 'spread' AND ABS(line) > 30
        """).fetchall()
        
        for row in unusual:
            if row['count'] > 0:
                print(f"  ⚠️  {row['issue']}: {row['count']} cases")
        
        # 5. Accuracy trends
        print("\n5️⃣ ACCURACY TRENDS (by day)")
        trends = con.execute("""
            SELECT 
                DATE(e.start_time_utc) as game_date,
                COUNT(*) as games,
                AVG(CASE WHEN within5_spread THEN 1.0 ELSE 0.0 END) * 100 as spread_acc,
                AVG(CASE WHEN within5_total THEN 1.0 ELSE 0.0 END) * 100 as total_acc
            FROM result r
            JOIN event e ON e.event_id = r.event_id
            WHERE e.start_time_utc >= datetime('now', '-7 days')
            GROUP BY DATE(e.start_time_utc)
            ORDER BY game_date DESC
        """).fetchall()
        
        for row in trends:
            print(f"  {row['game_date']}: {row['games']} games | Spread ±5: {row['spread_acc'] or 0:.1f}% | Total ±5: {row['total_acc'] or 0:.1f}%")
        
        # 6. System health summary
        print("\n6️⃣ SYSTEM HEALTH SUMMARY")
        health = con.execute("""
            SELECT 
                COUNT(*) as recent_games,
                SUM(CASE WHEN status = 'live' AND final_home IS NOT NULL THEN 1 ELSE 0 END) as false_positives,
                SUM(CASE WHEN status = 'finished' AND final_home IS NULL THEN 1 ELSE 0 END) as missing_finals_finished
            FROM event
            WHERE start_time_utc >= datetime('now', '-4 hours')
        """).fetchone()
        
        print(f"  Recent games (4h): {health['recent_games']}")
        print(f"  False positives: {health['false_positives']} {'✅' if health['false_positives'] == 0 else '❌'}")
        print(f"  Missing finals on finished: {health['missing_finals_finished']} {'✅' if health['missing_finals_finished'] == 0 else '⚠️'}")
        
        overall_health = health['false_positives'] == 0
        print(f"\n🎯 Overall Health: {'🟢 EXCELLENT' if overall_health else '🟡 NEEDS ATTENTION'}")

if __name__ == "__main__":
    run_quality_checks()