# watchboard.py
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone, timedelta

from rich.console import Console
from rich.table import Table

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

# Prefer package import; fallback for flat-file layout
try:
    from src.betsapi import get_event_score_fast, get_event_result, get_event_view
except Exception:
    from betsapi import get_event_score_fast, get_event_result, get_event_view

DB = "data/ebasketball.db"
WINDOW_MIN = 120

def q(sql: str, args: tuple = ()):
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        return con.execute(sql, args).fetchall()

def get_prematch_openers(eid: int) -> tuple[float|None, float|None]:
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        row = con.execute("""
            WITH start AS (SELECT start_time_utc st FROM event WHERE event_id=?)
            SELECT
              (SELECT line FROM opener
               WHERE event_id=? AND market='spread'
                 AND opened_at_utc < (SELECT st FROM start)
               ORDER BY opened_at_utc ASC LIMIT 1) AS sp,
              (SELECT line FROM opener
               WHERE event_id=? AND market='total'
                 AND opened_at_utc < (SELECT st FROM start)
               ORDER BY opened_at_utc ASC LIMIT 1) AS tt
        """, (eid, eid, eid)).fetchone()
    return (float(row["sp"]) if row and row["sp"] is not None else None,
            float(row["tt"]) if row and row["tt"] is not None else None)

def probe_live_state_and_scores(eid: int) -> tuple[str, str|None]:
    """
    Returns (time_status, score_str_or_None).
    time_status: "0" not started, "1" live, "3" finished, "-" unknown.
    For score_str, prefer fast feed's SS; if missing, try event/view.
    """
    ts = "-"
    score_str = None

    fast = get_event_score_fast(eid) or {}
    raw_ts = fast.get("time_status")
    if raw_ts is not None:
        ts = str(raw_ts)

    # try SS from fast
    ss = fast.get("SS") or fast.get("ss")
    if isinstance(ss, str) and "-" in ss:
        score_str = ss

    # fallback: event/view (sometimes carries ss even when fast lacks it)
    if score_str is None:
        ev = get_event_view(eid) or {}
        vss = ev.get("SS") or ev.get("ss")
        if isinstance(vss, str) and "-" in vss:
            score_str = vss

    # normalize ts
    if ts not in ("0", "1", "3"):
        ts = "-"

    return ts, score_str

def verify_finished_and_finals(eid: int) -> tuple[bool, int|None, int|None]:
    """
    Only finished if:
      - fast feed says time_status == "3", OR
      - /v1/bet365/result returns a final.
    """
    fast = get_event_score_fast(eid) or {}
    ts = str(fast.get("time_status") or "")
    if ts == "3":
        fh = fast.get("final_home")
        fa = fast.get("final_away")
        if fh is not None and fa is not None:
            return True, int(fh), int(fa)
        ss = fast.get("SS") or fast.get("ss")
        if isinstance(ss, str) and "-" in ss:
            try:
                l, r = ss.split("-", 1)
                return True, int(l), int(r)
            except Exception:
                pass

    alt = get_event_result(eid) or {}
    if alt.get("final_home") is not None and alt.get("final_away") is not None:
        return True, int(alt["final_home"]), int(alt["final_away"])

    return False, None, None

def fmt_opener(sp, tt):
    s = f"{sp:.1f}" if sp is not None else "—"
    t = f"{tt:.1f}" if tt is not None else "—"
    return f"{s}/{t}"

def main():
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(minutes=WINDOW_MIN)).strftime("%Y-%m-%d %H:%M:%S")
    rows = q("""
        SELECT event_id, start_time_utc, home_name, away_name
        FROM event
        WHERE start_time_utc >= ?
        ORDER BY start_time_utc DESC
    """, (cutoff,))

    console = Console()
    title = f"EBasketball Watchboard (last {WINDOW_MIN}m) — {now.strftime('%Y-%m-%d %H:%M:%S')} UTC"
    table = Table(title=title, show_lines=False)

    table.add_column("Start", justify="right")
    table.add_column("Age", justify="right")
    table.add_column("FI", justify="right")
    table.add_column("Matchup", justify="left", no_wrap=True)
    table.add_column("Opn S/T", justify="right")
    table.add_column("Score", justify="right")     # NEW: live score display
    table.add_column("Final", justify="right")     # strict final only if finished
    table.add_column("ΔS", justify="right")
    table.add_column("ΔT", justify="right")
    table.add_column("S±5/T±5", justify="center")
    table.add_column("Live", justify="center")

    for r in rows:
        eid = int(r["event_id"])
        st = datetime.fromisoformat(r["start_time_utc"]).replace(tzinfo=timezone.utc)
        age_min = int((now - st).total_seconds() // 60)
        start_str = st.strftime("%H:%M")
        age_str = f"{age_min:>2}m" if age_min >= 0 else f"{age_min}m"

        sp, tt = get_prematch_openers(eid)
        opn = fmt_opener(sp, tt)

        ts, live_score = probe_live_state_and_scores(eid)
        finished, fh, fa = verify_finished_and_finals(eid)

        score_str = live_score if isinstance(live_score, str) else "—"
        final_str = "—"
        dS = dT = None
        sflag = tflag = "—"

        if finished and fh is not None and fa is not None:
            final_str = f"{fh}-{fa}"
            margin = abs(fh - fa)
            total = fh + fa
            if sp is not None:
                dS = abs(margin - sp)
                sflag = "✔" if dS <= 5 else "—"
            if tt is not None:
                dT = abs(total - tt)
                tflag = "✔" if dT <= 5 else "—"

        table.add_row(
            start_str,
            f"{age_str:>3}",
            str(eid),
            f"{r['home_name']} vs {r['away_name']}",
            opn,
            score_str,                                   # live score (context only)
            final_str,                                   # strict final
            f"{dS:.1f}" if dS is not None else "—",
            f"{dT:.1f}" if dT is not None else "—",
            f"{sflag}/{tflag}",
            {"0": "—", "1": "LIVE", "3": "✓", "-": "—"}.get(ts, "—"),
        )

    console.print(table)

if __name__ == "__main__":
    main()
