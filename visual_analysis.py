# visual_analysis.py
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import sqlite3
import numpy as np

# Set style
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")

def create_heatmap():
    """Create a heatmap of hit rates by capture point and middle size"""
    
    con = sqlite3.connect("data/ebasketball.db")
    df = pd.read_sql_query("""
        SELECT 
            e.final_home - e.final_away as final_margin,
            o.line as opener,
            q1.line as q1,
            q2.line as q2,
            q3.line as q3
        FROM event e
        LEFT JOIN opener o ON o.event_id = e.event_id
        LEFT JOIN quarter_line q1 ON q1.event_id = e.event_id AND q1.quarter = 1
        LEFT JOIN quarter_line q2 ON q2.event_id = e.event_id AND q2.quarter = 2
        LEFT JOIN quarter_line q3 ON q3.event_id = e.event_id AND q3.quarter = 3
        WHERE e.final_home IS NOT NULL
    """, con)
    
    # Calculate hit rates
    capture_points = ['opener', 'q1', 'q2', 'q3']
    middle_sizes = range(1, 6)
    
    hit_matrix = []
    for point in capture_points:
        row = []
        for size in middle_sizes:
            valid = df[df[point].notna()]
            if len(valid) > 0:
                hits = sum(
                    ((valid[point] - size < valid['final_margin']) & 
                     (valid['final_margin'] < valid[point])) |
                    ((valid[point] < valid['final_margin']) & 
                     (valid['final_margin'] < valid[point] + size))
                )
                row.append(hits / len(valid) * 100)
            else:
                row.append(0)
        hit_matrix.append(row)
    
    # Create heatmap
    plt.figure(figsize=(10, 6))
    sns.heatmap(hit_matrix, 
                xticklabels=[f'{i}pt' for i in middle_sizes],
                yticklabels=['Opening', 'Q1 End', 'Q2 End', 'Q3 End'],
                annot=True, fmt='.1f', cmap='RdYlGn',
                cbar_kws={'label': 'Hit Rate (%)'},
                vmin=0, vmax=30)
    
    plt.title('Middle Hit Rates Heatmap\n(Darker green = Higher hit rate)')
    plt.tight_layout()
    plt.show()

def create_line_movement_boxplot():
    """Show distribution of line movements between capture points"""
    
    con = sqlite3.connect("data/ebasketball.db")
    df = pd.read_sql_query("""
        SELECT 
            o.line as opener,
            q1.line as q1,
            q2.line as q2,
            q3.line as q3
        FROM event e
        JOIN opener o ON o.event_id = e.event_id
        LEFT JOIN quarter_line q1 ON q1.event_id = e.event_id AND q1.quarter = 1
        LEFT JOIN quarter_line q2 ON q2.event_id = e.event_id AND q2.quarter = 2
        LEFT JOIN quarter_line q3 ON q3.event_id = e.event_id AND q3.quarter = 3
        WHERE e.final_home IS NOT NULL
    """, con)
    
    # Calculate movements
    movements = []
    if 'opener' in df.columns and 'q1' in df.columns:
        movements.extend([('Open→Q1', abs(df['q1'] - df['opener']).dropna())])
    if 'q1' in df.columns and 'q2' in df.columns:
        movements.extend([('Q1→Q2', abs(df['q2'] - df['q1']).dropna())])
    if 'q2' in df.columns and 'q3' in df.columns:
        movements.extend([('Q2→Q3', abs(df['q3'] - df['q2']).dropna())])
    
    # Create boxplot
    fig, ax = plt.subplots(figsize=(10, 6))
    
    data = [move[1] for move in movements]
    labels = [move[0] for move in movements]
    
    bp = ax.boxplot(data, labels=labels, patch_artist=True)
    
    # Color boxes
    colors = ['lightblue', 'lightgreen', 'lightcoral']
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
    
    ax.set_ylabel('Line Movement (points)')
    ax.set_title('Distribution of Line Movements Between Capture Points')
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    create_heatmap()
    create_line_movement_boxplot()