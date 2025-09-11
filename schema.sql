CREATE TABLE IF NOT EXISTS event(
  event_id INTEGER PRIMARY KEY,
  league_id INTEGER,
  start_time_utc TEXT NOT NULL,
  status TEXT NOT NULL,
  home_name TEXT NOT NULL,
  away_name TEXT NOT NULL,
  final_home INTEGER,
  final_away INTEGER
);
CREATE INDEX IF NOT EXISTS idx_event_league_time ON event(league_id, start_time_utc);
CREATE INDEX IF NOT EXISTS idx_event_status ON event(status);

CREATE TABLE IF NOT EXISTS opener(
  event_id INTEGER,
  bookmaker_id TEXT,
  market TEXT CHECK (market IN ('spread','total')),
  line REAL NOT NULL,
  price_home REAL,
  price_away REAL,
  opened_at_utc TEXT NOT NULL,
  PRIMARY KEY(event_id, bookmaker_id, market),
  FOREIGN KEY(event_id) REFERENCES event(event_id)
);

CREATE TABLE IF NOT EXISTS result(
  event_id INTEGER PRIMARY KEY,
  spread_delta REAL,
  total_delta REAL,
  within2_spread BOOLEAN, within3_spread BOOLEAN,
  within4_spread BOOLEAN, within5_spread BOOLEAN,
  within2_total  BOOLEAN, within3_total  BOOLEAN,
  within4_total  BOOLEAN, within5_total  BOOLEAN,
  FOREIGN KEY(event_id) REFERENCES event(event_id)
);

-- odds snapshots (optional; enables Q1/Q2/Q3 capture later)
CREATE TABLE IF NOT EXISTS odds_snapshot(
  event_id INTEGER, bookmaker_id TEXT, market TEXT,
  line REAL, price_home REAL, price_away REAL,
  update_time_utc TEXT,
  PRIMARY KEY(event_id, bookmaker_id, market, update_time_utc)
);

-- pinned quarter lines (for your “final vs Q1/Q2/Q3” comparisons)
CREATE TABLE IF NOT EXISTS quarter_line(
  event_id INTEGER, bookmaker_id TEXT, market TEXT,
  quarter INTEGER,     -- 1,2,3
  line REAL,
  captured_at_utc TEXT,
  PRIMARY KEY(event_id, bookmaker_id, market, quarter)
);
