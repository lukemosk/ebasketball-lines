# variance_analysis.py - Analyze opening line vs final result variance
import sqlite3
from datetime import datetime, timedelta

DB = "data/ebasketball.db"

def analyze_variance():
    print("OPENING LINE vs FINAL RESULT VARIANCE ANALYSIS")
    print("=" * 60)
    
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        
        # Get games with both openers and results
        games = con.execute("""
            SELECT 
                e.event_id,
                e.home_name,
                e.away_name,
                e.start_time_utc,
                e.final_home,
                e.final_away,
                MAX(CASE WHEN o.market='spread' THEN o.line END) AS spread_opener,
                MAX(CASE WHEN o.market='total'  THEN o.line END) AS total_opener,
                r.spread_delta,
                r.total_delta,
                r.within2_spread, r.within3_spread, r.within4_spread, r.within5_spread,
                r.within2_total,  r.within3_total,  r.within4_total,  r.within5_total
            FROM event e
            JOIN opener o ON o.event_id = e.event_id
            JOIN result r ON r.event_id = e.event_id
            WHERE e.final_home IS NOT NULL AND e.final_away IS NOT NULL
            GROUP BY e.event_id
            ORDER BY e.start_time_utc DESC
        """).fetchall()
    
    if not games:
        print("No games with complete data found")
        return
    
    print(f"Analyzing {len(games)} games with complete opener + result data\n")
    
    # Categorize games by variance
    categories = {
        'spread': {
            '±2': [], '±3': [], '±4': [], '±5': [], '>5': []
        },
        'total': {
            '±2': [], '±3': [], '±4': [], '±5': [], '>5': []
        }
    }
    
    for game in games:
        # Calculate actual values
        margin = abs(game['final_home'] - game['final_away'])
        total_points = game['final_home'] + game['final_away']
        
        # Spread analysis
        if game['spread_opener'] is not None:
            spread_diff = abs(margin - abs(game['spread_opener']))
            
            game_data = {
                'event_id': game['event_id'],
                'teams': f"{game['home_name']} vs {game['away_name']}",
                'date': game['start_time_utc'][:10],
                'opener': abs(game['spread_opener']),
                'final_margin': margin,
                'difference': spread_diff,
                'final_score': f"{game['final_home']}-{game['final_away']}"
            }
            
            if spread_diff <= 2:
                categories['spread']['±2'].append(game_data)
            elif spread_diff <= 3:
                categories['spread']['±3'].append(game_data)
            elif spread_diff <= 4:
                categories['spread']['±4'].append(game_data)
            elif spread_diff <= 5:
                categories['spread']['±5'].append(game_data)
            else:
                categories['spread']['>5'].append(game_data)
        
        # Total analysis
        if game['total_opener'] is not None:
            total_diff = abs(total_points - game['total_opener'])
            
            game_data = {
                'event_id': game['event_id'],
                'teams': f"{game['home_name']} vs {game['away_name']}",
                'date': game['start_time_utc'][:10],
                'opener': game['total_opener'],
                'final_total': total_points,
                'difference': total_diff,
                'final_score': f"{game['final_home']}-{game['final_away']}"
            }
            
            if total_diff <= 2:
                categories['total']['±2'].append(game_data)
            elif total_diff <= 3:
                categories['total']['±3'].append(game_data)
            elif total_diff <= 4:
                categories['total']['±4'].append(game_data)
            elif total_diff <= 5:
                categories['total']['±5'].append(game_data)
            else:
                categories['total']['>5'].append(game_data)
    
    return categories, games

def display_variance_report(categories, games):
    """Display detailed variance analysis"""
    
    # Summary statistics
    print("SUMMARY STATISTICS")
    print("-" * 40)
    
    total_spread_games = sum(len(cat) for cat in categories['spread'].values())
    total_total_games = sum(len(cat) for cat in categories['total'].values())
    
    print(f"SPREAD VARIANCE (from {total_spread_games} games):")
    for range_name, games_list in categories['spread'].items():
        count = len(games_list)
        pct = (count / total_spread_games * 100) if total_spread_games > 0 else 0
        print(f"  {range_name:>3}: {count:>3} games ({pct:5.1f}%)")
    
    print(f"\nTOTAL VARIANCE (from {total_total_games} games):")
    for range_name, games_list in categories['total'].items():
        count = len(games_list)
        pct = (count / total_total_games * 100) if total_total_games > 0 else 0
        print(f"  {range_name:>3}: {count:>3} games ({pct:5.1f}%)")

def show_detailed_games(categories, variance_type, range_filter):
    """Show detailed breakdown of specific games"""
    
    if variance_type not in ['spread', 'total']:
        print("Invalid variance type. Use 'spread' or 'total'")
        return
    
    if range_filter not in categories[variance_type]:
        print(f"Invalid range. Use: {', '.join(categories[variance_type].keys())}")
        return
    
    games_list = categories[variance_type][range_filter]
    
    print(f"\nDETAILED {variance_type.upper()} GAMES WITHIN {range_filter}")
    print("=" * 70)
    
    if not games_list:
        print("No games in this category")
        return
    
    # Sort by difference to show closest to furthest
    games_list.sort(key=lambda x: x['difference'])
    
    for i, game in enumerate(games_list, 1):
        print(f"\n{i:2d}. FI {game['event_id']}: {game['teams']}")
        print(f"    Date: {game['date']} | Final: {game['final_score']}")
        
        if variance_type == 'spread':
            print(f"    Opener: {game['opener']:.1f} | Final Margin: {game['final_margin']} | Diff: {game['difference']:.1f}")
        else:
            print(f"    Opener: {game['opener']:.1f} | Final Total: {game['final_total']} | Diff: {game['difference']:.1f}")

def interactive_analysis():
    """Interactive analysis interface"""
    
    categories, games = analyze_variance()
    display_variance_report(categories, games)
    
    while True:
        print(f"\n" + "="*60)
        print("INTERACTIVE ANALYSIS")
        print("1. Show spread games within ±2")
        print("2. Show spread games within ±3") 
        print("3. Show spread games within ±4")
        print("4. Show spread games within ±5")
        print("5. Show spread games >5 difference")
        print("6. Show total games within ±2")
        print("7. Show total games within ±3")
        print("8. Show total games within ±4") 
        print("9. Show total games within ±5")
        print("10. Show total games >5 difference")
        print("11. Show all categories summary")
        print("12. Exit")
        
        choice = input("\nChoose option (1-12): ").strip()
        
        range_map = {
            '1': ('spread', '±2'), '2': ('spread', '±3'), '3': ('spread', '±4'), 
            '4': ('spread', '±5'), '5': ('spread', '>5'),
            '6': ('total', '±2'), '7': ('total', '±3'), '8': ('total', '±4'),
            '9': ('total', '±5'), '10': ('total', '>5')
        }
        
        if choice in range_map:
            variance_type, range_filter = range_map[choice]
            show_detailed_games(categories, variance_type, range_filter)
        elif choice == '11':
            display_variance_report(categories, games)
        elif choice == '12':
            break
        else:
            print("Invalid choice")

def export_analysis(categories):
    """Export detailed analysis to CSV"""
    
    print(f"\nEXPORT OPTIONS:")
    print("1. Export spread variance games")
    print("2. Export total variance games") 
    print("3. Export both")
    
    choice = input("Choose export option (1-3): ").strip()
    
    if choice in ['1', '3']:
        # Export spread data
        with open('spread_variance_analysis.csv', 'w') as f:
            f.write("Range,Event_ID,Teams,Date,Opener,Final_Margin,Difference,Final_Score\n")
            for range_name, games_list in categories['spread'].items():
                for game in games_list:
                    f.write(f"{range_name},{game['event_id']},\"{game['teams']}\",{game['date']},{game['opener']},{game['final_margin']},{game['difference']:.1f},\"{game['final_score']}\"\n")
        print("Exported spread_variance_analysis.csv")
    
    if choice in ['2', '3']:
        # Export total data  
        with open('total_variance_analysis.csv', 'w') as f:
            f.write("Range,Event_ID,Teams,Date,Opener,Final_Total,Difference,Final_Score\n")
            for range_name, games_list in categories['total'].items():
                for game in games_list:
                    f.write(f"{range_name},{game['event_id']},\"{game['teams']}\",{game['date']},{game['opener']},{game['final_total']},{game['difference']:.1f},\"{game['final_score']}\"\n")
        print("Exported total_variance_analysis.csv")

if __name__ == "__main__":
    categories, games = analyze_variance()
    
    if not categories:
        print("No data available for analysis")
    else:
        display_variance_report(categories, games)
        
        detailed = input(f"\nStart interactive analysis? [y/N]: ")
        if detailed.lower() == 'y':
            interactive_analysis()
        
        export = input(f"\nExport data to CSV? [y/N]: ")
        if export.lower() == 'y':
            export_analysis(categories)