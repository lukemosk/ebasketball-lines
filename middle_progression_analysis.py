# middle_progression_analysis.py
import sqlite3
from typing import Dict, List, Tuple

DB_PATH = "data/ebasketball.db"

def calculate_middle_hits():
    """Calculate middle hit rates for each capture point"""
    
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        
        # Get all games with finals
        all_data = con.execute("""
            SELECT 
                e.event_id,
                e.final_home,
                e.final_away,
                o.line as opener_line,
                q1.line as q1_line,
                q2.line as q2_line,
                q3.line as q3_line
            FROM event e
            LEFT JOIN opener o ON o.event_id = e.event_id AND o.market = 'spread'
            LEFT JOIN quarter_line q1 ON q1.event_id = e.event_id AND q1.quarter = 1 AND q1.market = 'spread'
            LEFT JOIN quarter_line q2 ON q2.event_id = e.event_id AND q2.quarter = 2 AND q2.market = 'spread'
            LEFT JOIN quarter_line q3 ON q3.event_id = e.event_id AND q3.quarter = 3 AND q3.market = 'spread'
            WHERE e.final_home IS NOT NULL AND e.final_away IS NOT NULL
        """).fetchall()
        
        return all_data

def analyze_capture_point(games, line_field: str, label: str, middle_sizes: List[int]):
    """Analyze middle hit rates for a specific capture point"""
    
    # Filter games that have this line
    valid_games = [g for g in games if g[line_field] is not None]
    
    if not valid_games:
        print(f"\n{label}: No data available")
        return
    
    print(f"\n{label} ({len(valid_games)} games)")
    print("-" * 60)
    print(f"{'Size':>4} | {'Low':>7} | {'High':>7} | {'Either':>7} | {'Break-even?':>12}")
    print("-" * 60)
    
    for size in middle_sizes:
        low_hits = 0
        high_hits = 0
        both_hits = 0
        
        for game in valid_games:
            line = float(game[line_field])
            final_margin = abs(game['final_home'] - game['final_away'])
            
            # Low window: (line - size, line)
            # High window: (line, line + size)
            low_hit = (line - size) < final_margin < line
            high_hit = line < final_margin < (line + size)
            
            if low_hit:
                low_hits += 1
            if high_hit:
                high_hits += 1
            if low_hit or high_hit:
                both_hits += 1
        
        total = len(valid_games)
        low_pct = (low_hits / total) * 100
        high_pct = (high_hits / total) * 100
        either_pct = (both_hits / total) * 100
        
        # 9.09% is break-even for -120 odds
        profitable = "YES" if either_pct >= 9.09 else "NO"
        
        print(f"{size:>4} | {low_pct:>6.1f}% | {high_pct:>6.1f}% | {either_pct:>6.1f}% | {profitable:>12}")

def show_summary_comparison(games):
    """Show summary comparison across all capture points"""
    
    print("\nSUMMARY: MIDDLE HIT RATES BY CAPTURE POINT")
    print("=" * 80)
    print("Showing 'either-side' hit rates (low OR high window hits)")
    print("Break-even: 9.09% for -120 odds")
    print("-" * 80)
    
    capture_points = [
        ('opener_line', 'Opening'),
        ('q1_line', 'Q1 End'),
        ('q2_line', 'Q2 End'),
        ('q3_line', 'Q3 End')
    ]
    
    middle_sizes = [1, 2, 3, 4, 5]
    
    # Header
    print(f"{'Capture Point':<12}", end="")
    for size in middle_sizes:
        print(f" | {size}pt:>6", end="")
    print(" | Games")
    print("-" * 80)
    
    # Data rows
    for field, label in capture_points:
        valid_games = [g for g in games if g[field] is not None]
        
        if not valid_games:
            print(f"{label:<12} |   No data available")
            continue
        
        print(f"{label:<12}", end="")
        
        for size in middle_sizes:
            hits = 0
            for game in valid_games:
                line = float(game[field])
                final_margin = abs(game['final_home'] - game['final_away'])
                
                # Check if either window hits
                low_hit = (line - size) < final_margin < line
                high_hit = line < final_margin < (line + size)
                
                if low_hit or high_hit:
                    hits += 1
            
            pct = (hits / len(valid_games)) * 100
            # Highlight profitable rates
            if pct >= 9.09:
                print(f" | {pct:>5.1f}%*", end="")
            else:
                print(f" | {pct:>5.1f}%", end="")
        
        print(f" | {len(valid_games):>5}")
    
    print("\n* = Profitable (≥9.09%)")

def main():
    print("MIDDLE HIT RATE ANALYSIS BY CAPTURE POINT")
    print("=" * 80)
    print("This shows what % of games would have hit a middle bet")
    print("if you had the opening line and could bet the opposite side")
    print("at various point spreads wider.\n")
    
    games = calculate_middle_hits()
    
    if not games:
        print("No games with final results found")
        return
    
    print(f"Total games analyzed: {len(games)}")
    
    # Detailed analysis for each capture point
    middle_sizes = [1, 2, 3, 4, 5]
    
    analyze_capture_point(games, 'opener_line', 'OPENING LINES', middle_sizes)
    analyze_capture_point(games, 'q1_line', 'Q1 END LINES', middle_sizes)
    analyze_capture_point(games, 'q2_line', 'Q2 END LINES', middle_sizes)
    analyze_capture_point(games, 'q3_line', 'Q3 END LINES', middle_sizes)
    
    # Summary comparison
    show_summary_comparison(games)
    
    # Key insights
    print("\nKEY INSIGHTS:")
    print("-" * 40)
    
    # Find best capture points
    best_points = []
    for field, label in [('opener_line', 'Opening'), ('q1_line', 'Q1'), 
                         ('q2_line', 'Q2'), ('q3_line', 'Q3')]:
        valid = [g for g in games if g[field] is not None]
        if valid:
            # Calculate 3-point middle hit rate as representative
            hits = sum(1 for g in valid if abs(g['final_home'] - g['final_away']) != float(g[field]))
            if hits > 0:
                best_points.append((label, len(valid)))
    
    if best_points:
        print(f"• Data available from: {', '.join([f'{p[0]} (n={p[1]})' for p in best_points])}")
    
    print("\nNote: With only 3 games, these percentages are not statistically")
    print("significant. Aim for 100+ games for reliable patterns.")

if __name__ == "__main__":
    main()