# dashboard.py
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import sqlite3
import dash
from dash import dcc, html, Input, Output

# Load your data
def load_data():
    con = sqlite3.connect("data/ebasketball.db")
    
    # Get line progression data
    query = """
    SELECT 
        e.event_id,
        e.start_time_utc,
        e.final_home - e.final_away as final_margin,
        o.line as opener,
        q1.line as q1_line,
        q2.line as q2_line,
        q3.line as q3_line
    FROM event e
    LEFT JOIN opener o ON o.event_id = e.event_id AND o.market = 'spread'
    LEFT JOIN quarter_line q1 ON q1.event_id = e.event_id AND q1.quarter = 1
    LEFT JOIN quarter_line q2 ON q2.event_id = e.event_id AND q2.quarter = 2
    LEFT JOIN quarter_line q3 ON q3.event_id = e.event_id AND q3.quarter = 3
    WHERE e.final_home IS NOT NULL
    """
    
    return pd.read_sql_query(query, con)

# Create Dash app
app = dash.Dash(__name__)

df = load_data()

app.layout = html.Div([
    html.H1("eBasketball Middle Analysis Dashboard"),
    
    # Middle size selector
    dcc.Slider(
        id='middle-size',
        min=1, max=5, step=1,
        marks={i: f'{i}pt' for i in range(1, 6)},
        value=3
    ),
    
    # Charts
    dcc.Graph(id='hit-rate-chart'),
    dcc.Graph(id='line-movement-chart'),
    dcc.Graph(id='distribution-chart')
])

@app.callback(
    Output('hit-rate-chart', 'figure'),
    Input('middle-size', 'value')
)
def update_hit_rate(middle_size):
    # Calculate hit rates for each capture point
    capture_points = ['opener', 'q1_line', 'q2_line', 'q3_line']
    hit_rates = []
    
    for point in capture_points:
        valid_df = df[df[point].notna()]
        if len(valid_df) > 0:
            hits = sum(
                ((valid_df[point] - middle_size < valid_df['final_margin']) & 
                 (valid_df['final_margin'] < valid_df[point])) |
                ((valid_df[point] < valid_df['final_margin']) & 
                 (valid_df['final_margin'] < valid_df[point] + middle_size))
            )
            hit_rates.append(hits / len(valid_df) * 100)
        else:
            hit_rates.append(0)
    
    fig = go.Figure(data=[
        go.Bar(x=['Opening', 'Q1 End', 'Q2 End', 'Q3 End'], 
               y=hit_rates,
               text=[f'{r:.1f}%' for r in hit_rates],
               textposition='auto')
    ])
    
    fig.add_hline(y=9.09, line_dash="dash", 
                  annotation_text="Break-even (9.09%)")
    
    fig.update_layout(
        title=f"{middle_size}-Point Middle Hit Rates by Capture Point",
        yaxis_title="Hit Rate (%)",
        showlegend=False
    )
    
    return fig

if __name__ == '__main__':
    app.run(debug=True)