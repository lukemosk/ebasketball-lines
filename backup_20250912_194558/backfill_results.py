# backfill_results.py
from __future__ import annotations
import os, sqlite3
from typing import Optional, Tuple
from datetime import datetime, timezone
from dotenv import load_dotenv, find_dotenv

# Make sure .env is loaded before importing src.betsapi
load_dotenv(find_dotenv())

from src import betsapi  # uses your already-working wrappers

DB = "data/ebasketball.db"

# Tunables
LOOKBACK_HOURS = int(os.getenv("RESULT_SWEEP_HOURS", "6"))
MIN_AGE_MIN    = int(os.getenv("RESULT_MIN_AGE_MINUTES", "30"))  # don't touch games started <10m ago

def q(sql: str, args: tuple = ()) -> list[sqlite3.Row]:
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        return con.execute(sql, args).fetchall()

def exec_sql(sql: str, args: tuple = ()) -> None:
    with sqlite3.connect(DB) as con:
        con.execute(sql, args)
        con.commit()

def get_true_prematch_openers(con: sqlite3.Connection, eid: int) -> Tuple[Optional[float], Optional[float]]:
    """
    Return earliest opener strictly BEFORE start_time_utc: (spread_line, total_line).
    """
    con.row_factory = sqlite3.Row
    row = con.execute(
        """
        WITH start AS (SELECT start_time_utc AS st FROM event WHERE event_id = :eid),
        sp AS (
          SELECT line FROM opener
          WHERE event_id = :eid AND market='spread' AND opened_at_utc < (SELECT st FROM start)
          ORDER BY opened_at_utc ASC LIMIT 1
        ),
        tt AS (
          SELECT line FROM opener
          WHERE event_id = :eid AND market='total'  AND opened_at_utc < (SELECT st FROM start)
          ORDER BY opened_at_utc ASC LIMIT 1
        )
        SELECT (SELECT line FROM sp) AS sp_line, (SELECT line FROM tt) AS to_line
        """,
        {"eid": eid},
    ).fetchone()
    return (row["sp_line"] if row else None, row["to_line"] if row else None)

def write_result_row(ev_id: int, final_home: int, final_away: int) -> None:
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        sp_line, to_line = get_true_prematch_openers(con, ev_id)

        margin = abs(final_home - final_away)
        total  = final_home + final_away

        spread_delta = abs(margin - float(sp_line)) if sp_line is not None else None
        total_delta  = abs(total  - float(to_line)) if to_line  is not None else None

        def within(d, k): return (d is not None) and (d <= k)

        vals = (
            ev_id,
            spread_delta, total_delta,
            within(spread_delta,2), within(spread_delta,3), within(spread_delta,4), within(spread_delta,5),
            within(total_delta,2),  within(total_delta,3),  within(total_delta,4),  within(total_delta,5),
        )

        con.execute("""
            INSERT INTO result(
              event_id, spread_delta, total_delta,
              within2_spread, within3_spread, within4_spread, within5_spread,
              within2_total,  within3_total,  within4_total,  within5_total
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(event_id) DO UPDATE SET
              spread_delta=excluded.spread_delta,
              total_delta=excluded.total_delta,
              within2_spread=excluded.within2_spread,
              within3_spread=excluded.within3_spread,
              within4_spread=excluded.within4_spread,
              within5_spread=excluded.within5_spread,
              within2_total=excluded.within2_total,
              within3_total=excluded.within3_total,
              within4_total=excluded.within4_total,
              within5_total=excluded.within5_total
        """, vals)
        con.commit()

def parse_ss(ss: str) -> Optional[Tuple[int,int]]:
    if not isinstance(ss, str) or "-" not in ss: return None
    try:
        l, r = ss.split("-", 1)
        return int(l), int(r)
    except Exception:
        return None

def try_settle_via_fast(fi: int) -> Tuple[Optional[int], Optional[int], str]:
    """Use /v1/bet365/event fast endpoint. Accept if ts=='3' OR explicit finals present."""
    fast = betsapi.get_event_score_fast(fi) or {}
    ts = (fast.get("time_status") or "").strip()
    fh = fast.get("final_home")
    fa = fast.get("final_away")
    # Some variants only offer 'ss' as a string—pull it if present via our own parse
    ss_pair = parse_ss(fast.get("ss")) if isinstance(fast.get("ss"), str) else None
    if fh is None or fa is None:
        if ss_pair: fh, fa = ss_pair
    if (ts == "3") or (fh is not None and fa is not None):
        return (int(fh), int(fa)) if (fh is not None and fa is not None) else (None, None), "bet365:event-fast"
    return (None, None), "none"

def try_settle_via_event_view(fi: int, start_iso: str) -> Tuple[Optional[int], Optional[int], str]:
    """Use /v1/event/view (events API). Only accept when time_status=='3'."""
    ev = betsapi.get_event_view(fi) or {}
    ts = str(ev.get("time_status") or "").strip()
    if ts != "3":
        return (None, None), "none"
    # Prefer explicit finals / ft_* then fall back to ss
    fh = ev.get("final_home") or (ev.get("scores") or {}).get("ft_home")
    fa = ev.get("final_away") or (ev.get("scores") or {}).get("ft_away")
    if fh is None or fa is None:
        pair = parse_ss(ev.get("ss") or "")
        if pair: fh, fa = pair
    return ((int(fh), int(fa)) if (fh is not None and fa is not None) else (None, None), "events:view")

def try_settle_via_events_ended(fi: int, start_iso: str) -> Tuple[Optional[int], Optional[int], str]:
    """Scan /v1/events/ended for the date and match by id (cheapest + safest)."""
    date_str = start_iso[:10]  # 'YYYY-MM-DD'
    fh, fa = betsapi.find_final_in_ended(fi, date_str, league_id=None)
    if fh is not None and fa is not None:
        return (int(fh), int(fa)), "events:ended"
    return (None, None), "none"

def try_settle_via_result(fi: int) -> Tuple[Optional[int], Optional[int], str]:
    """Use /v1/bet365/result as last resort."""
    res = betsapi.get_event_result(fi) or {}
    fh = res.get("final_home")
    fa = res.get("final_away")
    if fh is not None and fa is not None:
        return (int(fh), int(fa)), "bet365:result"
    return (None, None), "none"

def main():
    # Candidates = events with missing finals OR missing result row, within last LOOKBACK_HOURS, and not too fresh
    rows = q(f"""
        WITH recent AS (
          SELECT *
          FROM event
          WHERE start_time_utc >= datetime('now', '-{LOOKBACK_HOURS} hours')
        ),
        needs AS (
          SELECT r.event_id IS NULL AS missing_result, e.*
          FROM recent e
          LEFT JOIN result r ON r.event_id = e.event_id
        )
        SELECT event_id, start_time_utc, home_name, away_name, final_home, final_away, missing_result
        FROM needs
        WHERE (final_home IS NULL OR final_away IS NULL OR missing_result)
          AND start_time_utc < datetime('now', '-{MIN_AGE_MIN} minutes')
        ORDER BY start_time_utc ASC
    """)

    print(f"candidates: {len(rows)}")
    for r in rows:
        ev_id = int(r["event_id"])
        start_iso = r["start_time_utc"]

        # If finals already on event but missing result row, just compute result
        if r["final_home"] is not None and r["final_away"] is not None and r["missing_result"]:
            fh = int(r["final_home"]); fa = int(r["final_away"])
            write_result_row(ev_id, fh, fa)
            print(f"- {ev_id}: computed result from existing finals ({fh}-{fa})")
            continue

        final = src = None

        # 1) bet365 fast
        final, src = try_settle_via_fast(ev_id)
        fh, fa = final if final != (None, None) else (None, None)

        # 2) events view (strict ended)
        if fh is None or fa is None:
            final, src = try_settle_via_event_view(ev_id, start_iso)
            fh, fa = final

        # 3) events ended (by id on same date)
        if fh is None or fa is None:
            final, src = try_settle_via_events_ended(ev_id, start_iso)
            fh, fa = final

        # 4) bet365 result
        if fh is None or fa is None:
            final, src = try_settle_via_result(ev_id)
            fh, fa = final

        if fh is None or fa is None:
            print(f"- {ev_id}: unresolved [{r['home_name']} vs {r['away_name']}]")
            continue

        # Persist: update event, then write/upssert result
        exec_sql("UPDATE event SET status='ended', final_home=?, final_away=? WHERE event_id=?",
                 (fh, fa, ev_id))
        write_result_row(ev_id, fh, fa)

        print(f"- {ev_id}: final {fh}-{fa} | src={src}")

if __name__ == "__main__":
    main()
