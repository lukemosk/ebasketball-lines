-- update_schema_quarter.sql - Add quarter line table if not exists

-- Ensure the quarter_line table exists with proper structure
CREATE TABLE IF NOT EXISTS quarter_line(
  event_id INTEGER NOT NULL,
  bookmaker_id TEXT NOT NULL,
  market TEXT NOT NULL CHECK (market IN ('spread','total')),
  quarter INTEGER NOT NULL CHECK (quarter IN (1,2,3)),
  line REAL NOT NULL,
  captured_at_utc TEXT NOT NULL,
  PRIMARY KEY(event_id, bookmaker_id, market, quarter),
  FOREIGN KEY(event_id) REFERENCES event(event_id)
);

-- Create index for efficient querying
CREATE INDEX IF NOT EXISTS idx_quarter_line_event ON quarter_line(event_id);
CREATE INDEX IF NOT EXISTS idx_quarter_line_captured ON quarter_line(captured_at_utc);

-- Add a view for easier quarter analysis
CREATE VIEW IF NOT EXISTS quarter_analysis AS
SELECT 
    e.event_id,
    e.home_name,
    e.away_name,
    e.final_home,
    e.final_away,
    e.start_time_utc,
    
    -- Pregame opener lines
    MAX(CASE WHEN o.market='spread' THEN o.line END) as opener_spread,
    MAX(CASE WHEN o.market='total' THEN o.line END) as opener_total,
    
    -- Q1 lines
    MAX(CASE WHEN ql.quarter=1 AND ql.market='spread' THEN ql.line END) as q1_spread,
    MAX(CASE WHEN ql.quarter=1 AND ql.market='total' THEN ql.line END) as q1_total,
    
    -- Q2 lines
    MAX(CASE WHEN ql.quarter=2 AND ql.market='spread' THEN ql.line END) as q2_spread,
    MAX(CASE WHEN ql.quarter=2 AND ql.market='total' THEN ql.line END) as q2_total,
    
    -- Q3 lines
    MAX(CASE WHEN ql.quarter=3 AND ql.market='spread' THEN ql.line END) as q3_spread,
    MAX(CASE WHEN ql.quarter=3 AND ql.market='total' THEN ql.line END) as q3_total,
    
    -- Calculate deltas
    ABS(ABS(e.final_home - e.final_away) - ABS(MAX(CASE WHEN o.market='spread' THEN o.line END))) as opener_spread_delta,
    ABS((e.final_home + e.final_away) - MAX(CASE WHEN o.market='total' THEN o.line END)) as opener_total_delta,
    
    ABS(ABS(e.final_home - e.final_away) - ABS(MAX(CASE WHEN ql.quarter=1 AND ql.market='spread' THEN ql.line END))) as q1_spread_delta,
    ABS((e.final_home + e.final_away) - MAX(CASE WHEN ql.quarter=1 AND ql.market='total' THEN ql.line END)) as q1_total_delta,
    
    ABS(ABS(e.final_home - e.final_away) - ABS(MAX(CASE WHEN ql.quarter=2 AND ql.market='spread' THEN ql.line END))) as q2_spread_delta,
    ABS((e.final_home + e.final_away) - MAX(CASE WHEN ql.quarter=2 AND ql.market='total' THEN ql.line END)) as q2_total_delta,
    
    ABS(ABS(e.final_home - e.final_away) - ABS(MAX(CASE WHEN ql.quarter=3 AND ql.market='spread' THEN ql.line END))) as q3_spread_delta,
    ABS((e.final_home + e.final_away) - MAX(CASE WHEN ql.quarter=3 AND ql.market='total' THEN ql.line END)) as q3_total_delta

FROM event e
LEFT JOIN opener o ON o.event_id = e.event_id
LEFT JOIN quarter_line ql ON ql.event_id = e.event_id
WHERE e.final_home IS NOT NULL AND e.final_away IS NOT NULL
GROUP BY e.event_id, e.home_name, e.away_name, e.final_home, e.final_away, e.start_time_utc;