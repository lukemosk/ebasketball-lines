from loguru import logger
from sqlalchemy import text
from src.db import engine, init_db
from src.config import CONF
from src import betsapi

# Simpler fix for src/etl.py - just be very conservative

def upsert_event(ev, league_id):
    # CONSERVATIVE: Don't set finals in ETL, let backfill handle it
    final_home, final_away = None, None
    
    # Only set finals if game is very clearly finished AND we're certain
    if ev.get("status") == "finished" and ev.get("ss"):
        try:
            # Only if the start time suggests game should definitely be over
            start_time_str = ev.get("time", "")
            if start_time_str:
                from datetime import datetime, timezone, timedelta
                
                # Parse start time
                try:
                    if isinstance(start_time_str, (int, float)):
                        start_time = datetime.utcfromtimestamp(int(start_time_str))
                    else:
                        start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                    
                    if start_time.tzinfo is None:
                        start_time = start_time.replace(tzinfo=timezone.utc)
                    
                    now = datetime.now(timezone.utc)
                    minutes_since_start = (now - start_time).total_seconds() / 60
                    
                    # Only set finals if game started >30 minutes ago (definitely should be done)
                    if minutes_since_start > 30:
                        a, b = ev["ss"].split("-")
                        final_home, final_away = int(a), int(b)
                    # Otherwise, let backfill_results.py handle it later
                        
                except Exception:
                    # If time parsing fails, don't set finals - be safe
                    pass
                    
        except Exception:
            # If anything fails, don't set finals
            pass
    
    # For any non-finished status, ensure finals are NULL
    elif ev.get("status") in ("live", "not_started"):
        final_home, final_away = None, None
    
    sql = """
    INSERT INTO event(event_id, league_id, start_time_utc, status, home_name, away_name, final_home, final_away)
    VALUES (:id, :lid, :time, :status, :home, :away, :fh, :fa)
    ON CONFLICT(event_id) DO UPDATE SET
      status=excluded.status, start_time_utc=excluded.start_time_utc,
      home_name=excluded.home_name, away_name=excluded.away_name,
      final_home=CASE 
        WHEN excluded.status='finished' AND excluded.final_home IS NOT NULL THEN excluded.final_home 
        WHEN excluded.status IN ('live', 'not_started') THEN NULL
        ELSE event.final_home 
      END,
      final_away=CASE 
        WHEN excluded.status='finished' AND excluded.final_away IS NOT NULL THEN excluded.final_away 
        WHEN excluded.status IN ('live', 'not_started') THEN NULL
        ELSE event.final_away 
      END;
    """
    with engine.begin() as c:
        c.execute(text(sql), {"id":ev["id"],"lid":league_id,"time":ev["time"],"status":ev["status"],
                              "home":ev["home"],"away":ev["away"],"fh":final_home,"fa":final_away})
        
def candidates_to_process():
    q = """
    SELECT e.event_id, e.final_home, e.final_away FROM event e
    LEFT JOIN result r ON r.event_id=e.event_id
    WHERE e.status='finished' AND e.final_home IS NOT NULL AND e.final_away IS NOT NULL
      AND r.event_id IS NULL
    """
    with engine.begin() as c:
        return [dict(row) for row in c.execute(text(q)).mappings().all()]

def upsert_opener(event_id, book, market, line, ph, pa, ts):
    sql = """
    INSERT INTO opener(event_id, bookmaker_id, market, line, price_home, price_away, opened_at_utc)
    VALUES (:eid,:book,:mkt,:line,:ph,:pa,:ts)
    ON CONFLICT(event_id, bookmaker_id, market) DO NOTHING;
    """
    from sqlalchemy import text as T
    with engine.begin() as c:
        c.execute(T(sql), {"eid":event_id,"book":book,"mkt":market,"line":line,"ph":ph,"pa":pa,"ts":ts})

def insert_result(event_id, fh, fa, sp_line, tot_line):
    spread_delta = abs(abs(fh - fa) - abs(sp_line)) if sp_line is not None else None  # FIXED: abs(margin - abs(spread))
    total_delta  = abs((fh + fa) - tot_line) if tot_line is not None else None
    def flags(d): return [(d is not None and d <= k) for k in (2,3,4,5)]
    w2s,w3s,w4s,w5s = flags(spread_delta)
    w2t,w3t,w4t,w5t = flags(total_delta)
    sql = """
    INSERT INTO result(event_id, spread_delta, total_delta,
      within2_spread, within3_spread, within4_spread, within5_spread,
      within2_total,  within3_total,  within4_total,  within5_total)
    VALUES (:eid,:sd,:td,:a,:b,:c,:d,:e,:f,:g,:h)
    """
    with engine.begin() as c:
        c.execute(text(sql), {"eid":event_id,"sd":spread_delta,"td":total_delta,
                              "a":w2s,"b":w3s,"c":w4s,"d":w5s,"e":w2t,"f":w3t,"g":w4t,"h":w5t})

def main():
    init_db()
    for lid in CONF["league_ids"]:
        for ev in betsapi.list_fixtures(lid):
            upsert_event(ev, lid)
    for row in candidates_to_process():
        # FIXED: Use get_odds_openers instead of non-existent get_odds_snapshots
        odds = betsapi.get_odds_openers(row["event_id"])
        sp_line = odds.get("spread") if odds else None
        tot_line = odds.get("total") if odds else None
        
        if sp_line is not None:
            upsert_opener(row["event_id"], CONF["book"], "spread", sp_line, None, None, odds.get("opened_at_utc", ""))
        if tot_line is not None:
            upsert_opener(row["event_id"], CONF["book"], "total", tot_line, None, None, odds.get("opened_at_utc", ""))
        
        if sp_line is not None or tot_line is not None:
            insert_result(row["event_id"], row["final_home"], row["final_away"], sp_line, tot_line)
    
    logger.info("Cycle complete.")

if __name__ == "__main__":
    main()