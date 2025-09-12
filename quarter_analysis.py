# quarter_analysis.py - Analyze quarter-end lines vs final results
import sqlite3
from typing import Dict, List, Optional
from datetime import datetime, timezone

DB_PATH = "data/ebasketball.db"

class QuarterAnalysis:
    def __init__(self):
        self.db_path = DB_PATH
    
    def get_complete_quarter_games(self) -> List[Dict]:
        """Get games with quarter lines and final results"""
        with sqlite3.connect(self.db_path) as con:
            con.row_factory = sqlite3.Row
            
            query = """
            SELECT DISTINCT
                e.event_id,
                e.home_name,
                e.away_name, 
                e.final_home,
                e.final_away,
                e.start_time_utc
            FROM event e
            JOIN quarter_line ql ON ql.event_id = e.event_id
            WHERE e.final_home IS NOT NULL 
              AND e.final_away IS NOT NULL
            ORDER BY e.start_time_utc DESC
            """
            
            return [dict(row) for row in con.execute(query).fetchall()]
    
    def get_quarter_lines_for_game(self, event_id: int) -> Dict:
        """Get all quarter lines for a specific game"""
        with sqlite3.connect(self.db_path) as con:
            con.row_factory = sqlite3.Row
            
            query = """
            SELECT quarter, market, line, captured_at_utc
            FROM quarter_line
            WHERE event_id = ?
            ORDER BY quarter, market
            """
            
            rows = con.execute(query, (event_id,)).fetchall()
            
            # Organize by quarter and market
            lines = {}
            for row in rows:
                quarter = f"Q{row['quarter']}"
                if quarter not in lines:
                    lines[quarter] = {}
                lines[quarter][row['market']] = {
                    'line': row['line'],
                    'captured_at': row['captured_at_utc']
                }
            
            return lines
    
    def get_opener_lines_for_game(self, event_id: int) -> Dict:
        """Get pregame opener lines for comparison"""
        with sqlite3.connect(self.db_path) as con:
            con.row_factory = sqlite3.Row
            
            query = """
            SELECT market, line, opened_at_utc
            FROM opener
            WHERE event_id = ?
            """
            
            rows = con.execute(query, (event_id,)).fetchall()
            
            opener_lines = {}
            for row in rows:
                opener_lines[row['market']] = {
                    'line': row['line'],
                    'opened_at': row['opened_at_utc']
                }
            
            return opener_lines
    
    def calculate_variances(self, final_home: int, final_away: int, lines: Dict) -> Dict:
        """Calculate how close each line was to the final result"""
        margin = abs(final_home - final_away)
        total_points = final_home + final_away
        
        variances = {}
        
        for period, period_lines in lines.items():
            variances[period] = {}
            
            if 'spread' in period_lines:
                spread_line = abs(float(period_lines['spread']['line']))
                spread_delta = abs(margin - spread_line)
                variances[period]['spread'] = {
                    'line': spread_line,
                    'delta': spread_delta,
                    'within2': spread_delta <= 2,
                    'within3': spread_delta <= 3,
                    'within5': spread_delta <= 5
                }
            
            if 'total' in period_lines:
                total_line = float(period_lines['total']['line'])
                total_delta = abs(total_points - total_line)
                variances[period]['total'] = {
                    'line': total_line,
                    'delta': total_delta,
                    'within2': total_delta <= 2,
                    'within3': total_delta <= 3,
                    'within5': total_delta <= 5
                }
        
        return variances
    
    def analyze_all_games(self) -> Dict:
        """Analyze all games with quarter data"""
        games = self.get_complete_quarter_games()
        
        if not games:
            print("No games with quarter line data found")
            return {}
        
        print(f"Analyzing {len(games)} games with quarter line data")
        
        analysis_results = {
            'total_games': len(games),
            'games_by_quarters': {'Q1': 0, 'Q2': 0, 'Q3': 0},
            'accuracy_by_quarter': {},
            'games': []
        }
        
        for game in games:
            event_id = game['event_id']
            final_home = game['final_home']
            final_away = game['final_away']
            
            # Get lines for this game
            quarter_lines = self.get_quarter_lines_for_game(event_id)
            opener_lines = self.get_opener_lines_for_game(event_id)
            
            # Add opener to lines dict for comparison
            if opener_lines:
                quarter_lines['Opener'] = opener_lines
            
            # Calculate variances
            variances = self.calculate_variances(final_home, final_away, quarter_lines)
            
            # Count quarters available
            for quarter in ['Q1', 'Q2', 'Q3']:
                if quarter in quarter_lines:
                    analysis_results['games_by_quarters'][quarter] += 1
            
            game_analysis = {
                'event_id': event_id,
                'teams': f"{game['home_name']} vs {game['away_name']}",
                'final_score': f"{final_home}-{final_away}",
                'date': game['start_time_utc'][:10],
                'lines': quarter_lines,
                'variances': variances
            }
            
            analysis_results['games'].append(game_analysis)
        
        # Calculate accuracy statistics by quarter
        for quarter in ['Opener', 'Q1', 'Q2', 'Q3']:
            analysis_results['accuracy_by_quarter'][quarter] = self.calculate_quarter_accuracy(
                analysis_results['games'], quarter
            )
        
        return analysis_results
    
    def calculate_quarter_accuracy(self, games: List[Dict], quarter: str) -> Dict:
        """Calculate accuracy statistics for a specific quarter"""
        stats = {
            'spread': {'total': 0, 'within2': 0, 'within3': 0, 'within5': 0},
            'total': {'total': 0, 'within2': 0, 'within3': 0, 'within5': 0}
        }
        
        for game in games:
            variances = game.get('variances', {})
            if quarter not in variances:
                continue
            
            quarter_vars = variances[quarter]
            
            for market in ['spread', 'total']:
                if market in quarter_vars:
                    stats[market]['total'] += 1
                    if quarter_vars[market]['within2']:
                        stats[market]['within2'] += 1
                    if quarter_vars[market]['within3']:
                        stats[market]['within3'] += 1
                    if quarter_vars[market]['within5']:
                        stats[market]['within5'] += 1
        
        # Convert to percentages
        for market in ['spread', 'total']:
            total = stats[market]['total']
            if total > 0:
                stats[market]['within2_pct'] = stats[market]['within2'] / total * 100
                stats[market]['within3_pct'] = stats[market]['within3'] / total * 100
                stats[market]['within5_pct'] = stats[market]['within5'] / total * 100
            else:
                stats[market]['within2_pct'] = 0
                stats[market]['within3_pct'] = 0
                stats[market]['within5_pct'] = 0
        
        return stats
    
    def display_summary(self, results: Dict):
        """Display analysis summary"""
        print("\n🏀 QUARTER LINE ANALYSIS SUMMARY")
        print("=" * 60)
        
        total_games = results['total_games']
        print(f"Total games analyzed: {total_games}")
        
        print(f"\nQuarter line availability:")
        for quarter, count in results['games_by_quarters'].items():
            pct = (count / total_games * 100) if total_games > 0 else 0
            print(f"  {quarter}: {count} games ({pct:.1f}%)")
        
        print(f"\n📊 ACCURACY COMPARISON (% within variance)")
        print("-" * 60)
        print(f"Period    | Spread Games | ±2pts | ±3pts | ±5pts | Total Games | ±2pts | ±3pts | ±5pts")
        print("-" * 60)
        
        periods = ['Opener', 'Q1', 'Q2', 'Q3']
        for period in periods:
            stats = results['accuracy_by_quarter'].get(period, {})
            
            s_total = stats.get('spread', {}).get('total', 0)
            s_w2 = stats.get('spread', {}).get('within2_pct', 0)
            s_w3 = stats.get('spread', {}).get('within3_pct', 0) 
            s_w5 = stats.get('spread', {}).get('within5_pct', 0)
            
            t_total = stats.get('total', {}).get('total', 0)
            t_w2 = stats.get('total', {}).get('within2_pct', 0)
            t_w3 = stats.get('total', {}).get('within3_pct', 0)
            t_w5 = stats.get('total', {}).get('within5_pct', 0)
            
            print(f"{period:<9} | {s_total:>11} | {s_w2:>4.1f} | {s_w3:>4.1f} | {s_w5:>4.1f} | "
                  f"{t_total:>10} | {t_w2:>4.1f} | {t_w3:>4.1f} | {t_w5:>4.1f}")
    
    def show_detailed_games(self, results: Dict, quarter: str, limit: int = 10):
        """Show detailed results for specific quarter"""
        print(f"\n🔍 DETAILED {quarter.upper()} LINE ANALYSIS")
        print("=" * 70)
        
        games_with_quarter = [
            game for game in results['games'] 
            if quarter in game.get('variances', {})
        ]
        
        if not games_with_quarter:
            print(f"No games found with {quarter} data")
            return
        
        # Sort by spread accuracy (best to worst)
        def sort_key(game):
            var = game['variances'].get(quarter, {})
            spread_var = var.get('spread', {})
            return spread_var.get('delta', 999)
        
        sorted_games = sorted(games_with_quarter, key=sort_key)[:limit]
        
        for i, game in enumerate(sorted_games, 1):
            print(f"\n{i:2d}. FI {game['event_id']}: {game['teams']}")
            print(f"    Date: {game['date']} | Final: {game['final_score']}")
            
            lines = game['lines'].get(quarter, {})
            variances = game['variances'].get(quarter, {})
            
            if 'spread' in lines and 'spread' in variances:
                s_line = variances['spread']['line']
                s_delta = variances['spread']['delta']
                print(f"    Spread: {s_line:.1f} → Δ{s_delta:.1f} pts")
            
            if 'total' in lines and 'total' in variances:
                t_line = variances['total']['line']
                t_delta = variances['total']['delta']
                print(f"    Total:  {t_line:.1f} → Δ{t_delta:.1f} pts")
    
    def export_to_csv(self, results: Dict, filename: str = "quarter_analysis.csv"):
        """Export detailed results to CSV"""
        import csv
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow([
                'Event_ID', 'Teams', 'Date', 'Final_Score',
                'Opener_Spread', 'Opener_Spread_Delta', 'Opener_Total', 'Opener_Total_Delta',
                'Q1_Spread', 'Q1_Spread_Delta', 'Q1_Total', 'Q1_Total_Delta',
                'Q2_Spread', 'Q2_Spread_Delta', 'Q2_Total', 'Q2_Total_Delta',
                'Q3_Spread', 'Q3_Spread_Delta', 'Q3_Total', 'Q3_Total_Delta'
            ])
            
            for game in results['games']:
                row = [
                    game['event_id'],
                    game['teams'],
                    game['date'],
                    game['final_score']
                ]
                
                # Add data for each period
                for period in ['Opener', 'Q1', 'Q2', 'Q3']:
                    var = game['variances'].get(period, {})
                    
                    # Spread
                    if 'spread' in var:
                        row.extend([var['spread']['line'], var['spread']['delta']])
                    else:
                        row.extend([None, None])
                    
                    # Total
                    if 'total' in var:
                        row.extend([var['total']['line'], var['total']['delta']])
                    else:
                        row.extend([None, None])
                
                writer.writerow(row)
        
        print(f"📁 Exported detailed analysis to {filename}")

def main():
    analyzer = QuarterAnalysis()
    results = analyzer.analyze_all_games()
    
    if not results or results['total_games'] == 0:
        print("No quarter line data available for analysis")
        print("\nTo collect quarter data:")
        print("1. Run: python live_quarter_monitor.py")
        print("2. Let it monitor live games during eBasketball hours")
        print("3. It will automatically capture lines at quarter endings")
        return
    
    # Show summary
    analyzer.display_summary(results)
    
    # Interactive options
    while True:
        print(f"\n" + "="*60)
        print("INTERACTIVE QUARTER ANALYSIS")
        print("1. Show detailed Opener line results")
        print("2. Show detailed Q1 line results")
        print("3. Show detailed Q2 line results") 
        print("4. Show detailed Q3 line results")
        print("5. Export all data to CSV")
        print("6. Show summary again")
        print("7. Exit")
        
        choice = input("\nChoose option (1-7): ").strip()
        
        if choice == '1':
            analyzer.show_detailed_games(results, 'Opener')
        elif choice == '2':
            analyzer.show_detailed_games(results, 'Q1')
        elif choice == '3':
            analyzer.show_detailed_games(results, 'Q2')
        elif choice == '4':
            analyzer.show_detailed_games(results, 'Q3')
        elif choice == '5':
            analyzer.export_to_csv(results)
        elif choice == '6':
            analyzer.display_summary(results)
        elif choice == '7':
            break
        else:
            print("Invalid choice")

if __name__ == "__main__":
    main()