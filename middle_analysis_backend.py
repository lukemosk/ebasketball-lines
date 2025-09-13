# middle_analysis_backend.py
"""
Backend to calculate middle hit rates from your eBasketball database
Serves data for the visualization component
"""

import sqlite3
from flask import Flask, jsonify, request
from flask_cors import CORS
from typing import Dict, List, Any
import json

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

DB_PATH = "data/ebasketball.db"

def calculate_anchored_windows(opener: float, m: int):
    """Calculate anchored middle windows"""
    # Quantize to 0.5
    opener_half = round(opener * 2) / 2
    
    # Two windows: (opener-m, opener) and (opener, opener+m)
    low_window = (opener_half - m, opener_half)
    high_window = (opener_half, opener_half + m)
    
    return low_window, high_window

def check_middle_hit(margin: int, opener: float, m: int):
    """Check if a result hits either anchored middle window"""
    low_window, high_window = calculate_anchored_windows(opener, m)
    
    low_hit = low_window[0] < margin < low_window[1]
    high_hit = high_window[0] < margin < high_window[1]
    
    return {
        'low_hit': low_hit,
        'high_hit': high_hit,
        'either_hit': low_hit or high_hit
    }

def get_middle_analysis_data(middle_size: int = 2):
    """Calculate middle hit rates for all capture points"""
    
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        
        # Get all games with results and opener data
        games = con.execute("""
            SELECT 
                e.event_id,
                e.final_home,
                e.final_away,
                o.line as opener_line
            FROM event e
            JOIN opener o ON e.event_id = o.event_id
            JOIN result r ON e.event_id = r.event_id
            WHERE e.final_home IS NOT NULL 
              AND e.final_away IS NOT NULL
              AND o.market = 'spread'
              AND o.line IS NOT NULL
        """).fetchall()
        
        # Get quarter line data
        quarter_data = con.execute("""
            SELECT 
                event_id,
                quarter,
                line
            FROM quarter_line
            WHERE market = 'spread'
            AND line IS NOT NULL
        """).fetchall()
        
        # Organize quarter data by event and quarter
        quarter_lines = {}
        for row in quarter_data:
            event_id = row['event_id']
            quarter = row['quarter']
            if event_id not in quarter_lines:
                quarter_lines[event_id] = {}
            quarter_lines[event_id][quarter] = row['line']
    
    # Calculate results for each capture point
    results = {
        'opener': {'total': 0, 'low_hits': 0, 'high_hits': 0, 'either_hits': 0},
        'q1_end': {'total': 0, 'low_hits': 0, 'high_hits': 0, 'either_hits': 0},
        'q2_end': {'total': 0, 'low_hits': 0, 'high_hits': 0, 'either_hits': 0},
        'q3_end': {'total': 0, 'low_hits': 0, 'high_hits': 0, 'either_hits': 0}
    }
    
    for game in games:
        event_id = game['event_id']
        margin = abs(game['final_home'] - game['final_away'])
        
        # Opener analysis
        if game['opener_line']:
            opener_result = check_middle_hit(margin, abs(game['opener_line']), middle_size)
            results['opener']['total'] += 1
            if opener_result['low_hit']:
                results['opener']['low_hits'] += 1
            if opener_result['high_hit']:
                results['opener']['high_hits'] += 1
            if opener_result['either_hit']:
                results['opener']['either_hits'] += 1
        
        # Quarter line analysis
        if event_id in quarter_lines:
            for quarter, quarter_key in [(1, 'q1_end'), (2, 'q2_end'), (3, 'q3_end')]:
                if quarter in quarter_lines[event_id]:
                    quarter_line = quarter_lines[event_id][quarter]
                    quarter_result = check_middle_hit(margin, abs(quarter_line), middle_size)
                    
                    results[quarter_key]['total'] += 1
                    if quarter_result['low_hit']:
                        results[quarter_key]['low_hits'] += 1
                    if quarter_result['high_hit']:
                        results[quarter_key]['high_hits'] += 1
                    if quarter_result['either_hit']:
                        results[quarter_key]['either_hits'] += 1
    
    # Calculate hit rates and format for frontend
    formatted_results = []
    capture_points = [
        ('opener', 'Opener'),
        ('q1_end', 'Q1 End'),
        ('q2_end', 'Q2 End'),
        ('q3_end', 'Q3 End')
    ]
    
    for key, name in capture_points:
        data = results[key]
        total = data['total']
        
        if total > 0:
            formatted_results.append({
                'capture': name,
                'lowHitRate': data['low_hits'] / total,
                'highHitRate': data['high_hits'] / total,
                'eitherHitRate': data['either_hits'] / total,
                'lowHits': data['low_hits'],
                'highHits': data['high_hits'],
                'eitherHits': data['either_hits'],
                'totalGames': total
            })
        else:
            formatted_results.append({
                'capture': name,
                'lowHitRate': 0,
                'highHitRate': 0,
                'eitherHitRate': 0,
                'lowHits': 0,
                'highHits': 0,
                'eitherHits': 0,
                'totalGames': 0
            })
    
    return formatted_results

@app.route('/api/middle-analysis')
def middle_analysis():
    """API endpoint for middle analysis data"""
    middle_size = request.args.get('middle_size', 2, type=int)
    
    try:
        data = get_middle_analysis_data(middle_size)
        return jsonify({
            'success': True,
            'data': data,
            'middle_size': middle_size
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/database-stats')
def database_stats():
    """Get basic database statistics"""
    try:
        with sqlite3.connect(DB_PATH) as con:
            stats = {}
            
            # Count games with finals
            stats['total_games'] = con.execute("""
                SELECT COUNT(*) FROM event 
                WHERE final_home IS NOT NULL AND final_away IS NOT NULL
            """).fetchone()[0]
            
            # Count openers
            stats['opener_spreads'] = con.execute("""
                SELECT COUNT(*) FROM opener WHERE market = 'spread'
            """).fetchone()[0]
            
            # Count quarter lines
            stats['quarter_lines'] = con.execute("""
                SELECT COUNT(*) FROM quarter_line WHERE market = 'spread'
            """).fetchone()[0]
            
            # Count results
            stats['results'] = con.execute("""
                SELECT COUNT(*) FROM result
            """).fetchone()[0]
            
            return jsonify({
                'success': True,
                'stats': stats
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    print("Starting Middle Analysis Backend...")
    print("API endpoints:")
    print("  GET /api/middle-analysis?middle_size=2")
    print("  GET /api/database-stats")
    print("\nRunning on http://localhost:5000")
    
    app.run(debug=True, host='0.0.0.0', port=5000)