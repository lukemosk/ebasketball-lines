# middling_analysis.py - Fixed middle betting math
import sqlite3

DB = "data/ebasketball.db"

def analyze_middling_opportunities():
    print("MIDDLING OPPORTUNITY ANALYSIS")
    print("=" * 50)
    
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        
        games = con.execute("""
            SELECT 
                e.event_id,
                e.final_home,
                e.final_away,
                MAX(CASE WHEN o.market='spread' THEN o.line END) AS spread_opener,
                MAX(CASE WHEN o.market='total'  THEN o.line END) AS total_opener
            FROM event e
            JOIN opener o ON o.event_id = e.event_id
            WHERE e.final_home IS NOT NULL AND e.final_away IS NOT NULL
            GROUP BY e.event_id
        """).fetchall()
    
    if not games:
        print("No complete games found")
        return
    
    print(f"Analyzing {len(games)} games for middling opportunities\n")
    
    spread_data = []
    total_data = []
    
    for game in games:
        margin = abs(game['final_home'] - game['final_away'])
        total_points = game['final_home'] + game['final_away']
        
        if game['spread_opener'] is not None:
            spread_data.append({
                'opener': abs(game['spread_opener']),
                'final': margin
            })
        
        if game['total_opener'] is not None:
            total_data.append({
                'opener': game['total_opener'],
                'final': total_points
            })
    
    return spread_data, total_data

def calculate_middle_probabilities(data, market_type):
    print(f"\n{market_type.upper()} MIDDLE ANALYSIS")
    print("-" * 50)
    
    total_games = len(data)
    if total_games == 0:
        print("No data available")
        return
    
    # Correct middle betting math using your example:
    # Bet $250 each side at -120 odds
    # If middle hits: win $208.33 profit
    # If middle misses: lose $41.67 juice
    bet_per_side = 250
    profit_if_hit = 208.33
    loss_if_miss = 41.67
    
    # Break-even: need to hit enough to cover losses
    # profit_if_hit * hit_rate = loss_if_miss * miss_rate
    # 208.33 * hit_rate = 41.67 * (1 - hit_rate)
    # 208.33 * hit_rate = 41.67 - 41.67 * hit_rate
    # 208.33 * hit_rate + 41.67 * hit_rate = 41.67
    # hit_rate * (208.33 + 41.67) = 41.67
    # hit_rate = 41.67 / 250 = 0.1667 = 16.67%
    
    breakeven_rate = loss_if_miss / (profit_if_hit + loss_if_miss)
    
    print(f"Sample size: {total_games} games")
    print(f"Bet: ${bet_per_side} each side at -120 odds")
    print(f"Win: ${profit_if_hit:.2f} | Lose: ${loss_if_miss:.2f}")
    print(f"Break-even: {breakeven_rate:.1%} (1 in {1/breakeven_rate:.1f})\n")
    
    print("Range  | Hit Rate | Profit/Loss | Status")
    print("-" * 45)
    
    for range_size in [1, 2, 3, 4, 5]:
        hits = 0
        for game in data:
            opener = game['opener']
            final = game['final']
            
            # Check if final result is within range_size points of opener
            # This represents how often you could find profitable middle opportunities
            # if you found sportsbooks with lines range_size points different from opener
            if abs(final - opener) <= range_size:
                hits += 1
        
        hit_rate = hits / total_games
        profit_per_attempt = (hit_rate * profit_if_hit) - ((1 - hit_rate) * loss_if_miss)
        
        if hit_rate >= breakeven_rate:
            status = "PROFITABLE"
        elif hit_rate >= breakeven_rate * 0.9:
            status = "CLOSE"
        else:
            status = "UNPROFITABLE"
        
        print(f"{middle_size:>6}pt | {hit_rate:>7.1%} | {profit_per_attempt:>+8.2f} | {status}")

def show_distribution(data, market_type):
    print(f"\n{market_type.upper()} DISTRIBUTION:")
    print("-" * 30)
    
    differences = [abs(game['final'] - game['opener']) for game in data]
    total = len(differences)
    
    ranges = [
        (0, 0.5, "Exact"),
        (0.5, 1, "±0.5pt"),
        (1, 1.5, "±1pt"), 
        (1.5, 2, "±1.5pt"),
        (2, 3, "±2-3pt"),
        (3, 5, "±3-5pt"),
        (5, float('inf'), ">5pt")
    ]
    
    for start, end, label in ranges:
        if end == float('inf'):
            count = sum(1 for d in differences if d > start)
        else:
            count = sum(1 for d in differences if start < d <= end)
        
        pct = count / total if total > 0 else 0
        print(f"  {label:>8}: {count:>3} games ({pct:>5.1%})")

def main():
    spread_data, total_data = analyze_middling_opportunities()
    
    if spread_data:
        calculate_middle_probabilities(spread_data, "spread")
        show_distribution(spread_data, "spread")
    
    if total_data:
        calculate_middle_probabilities(total_data, "total")
        show_distribution(total_data, "total")
    
    print(f"\n" + "="*50)
    print("INTERPRETATION:")
    print("- Hit rates above 16.7% are profitable at -120 odds")
    print("- 1pt middles need exact or ±0.5pt results to hit")
    print("- 2pt middles need results within ±1pt to hit")

if __name__ == "__main__":
    main()