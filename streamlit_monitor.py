# streamlit_monitor.py
import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import time

st.set_page_config(page_title="eBasketball Live Monitor", layout="wide")

def load_latest_data():
    con = sqlite3.connect("data/ebasketball.db")
    
    # Recent captures
    recent = pd.read_sql_query("""
        SELECT 
            q.captured_at_utc,
            q.quarter,
            q.line,
            e.home_name || ' vs ' || e.away_name as game,
            q.home_score || '-' || q.away_score as score
        FROM quarter_line q
        JOIN event e ON e.event_id = q.event_id
        ORDER BY q.captured_at_utc DESC
        LIMIT 20
    """, con)
    
    # Hit rate trends
    trends = pd.read_sql_query("""
        SELECT 
            date(e.start_time_utc) as date,
            COUNT(*) as games,
            AVG(CASE WHEN ABS(e.final_home - e.final_away) != o.line THEN 1 ELSE 0 END) * 100 as hit_rate
        FROM event e
        JOIN opener o ON o.event_id = e.event_id
        WHERE e.final_home IS NOT NULL
        GROUP BY date(e.start_time_utc)
        ORDER BY date
    """, con)
    
    return recent, trends

# Auto-refresh
if st.button("Start Auto-Refresh"):
    placeholder = st.empty()
    
    while True:
        with placeholder.container():
            recent, trends = load_latest_data()
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Recent Captures")
                st.dataframe(recent)
            
            with col2:
                st.subheader("Hit Rate Trend")
                fig = px.line(trends, x='date', y='hit_rate',
                             title='Daily Middle Hit Rate %')
                st.plotly_chart(fig)
            
            time.sleep(10)  # Refresh every 10 seconds