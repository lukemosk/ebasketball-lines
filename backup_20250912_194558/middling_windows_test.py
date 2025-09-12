# middling_windows_test_v2.py
# Purpose: Correct, unambiguous test-bed for eBasketball middling math.
# - Spreads: "true either-side" using SIGNED margins, with the opposite line fixed at t = s - m (must be >= 0.5).
#            We separately show neg-side, pos-side, cross-zero, plus their union (either-side).
# - Totals: anchored Over/Under windows as usual (lower/upper lines), with m as the gap.
# - Pricing summary: -120 per side at $250 stake (no EV columns; just BE math).
#
# This removes the ambiguity that made your earlier two spread tables disagree.

import sqlite3
import math
from typing import List, Dict, Optional, Tuple

DB = "data/ebasketball.db"

# -------- CONFIG --------
BOOKMAKER_ID: Optional[int] = None   # e.g., 1 for Bet365, or None for consensus AVG
REQUIRE_FINAL_STATUS = False         # flip True if event.status is reliable in your DB
MIN_PLAUSIBLE_TOTAL = 80
MAX_PLAUSIBLE_TOTAL = 250

SPREAD_MIDDLE_SIZES = [1, 2, 3, 4, 5]
TOTAL_MIDDLE_SIZES  = [2, 3, 4, 5, 6]

AMERICAN_ODDS_PER_SIDE = -120
STAKE_PER_SIDE = 250.0
# ------------------------


# ----- helpers -----
def q05(x: float) -> float:
    """Quantize to nearest 0.5 (always *.0 or *.5)."""
    return round(x * 2.0) / 2.0

def round_half_up_int(x: float) -> int:
    """Round halves up to nearest integer (2.5 -> 3)."""
    return math.floor(x + 0.5)

def profit_on_win(neg_odds: int, stake: float) -> float:
    """Profit (not including stake) when a -odds bet of size 'stake' wins."""
    if neg_odds >= 0:
        raise ValueError("Use negative American odds (e.g., -120).")
    return stake * 100.0 / abs(neg_odds)

def miss_and_hit_net(neg_odds: int, stake: float) -> Tuple[float, float, float, float]:
    """
    Returns (miss_net, hit_net, breakeven_rate, hit_offsets_misses).
    Miss: one win + one loss  -> profit - stake (negative).
    Hit : both win           -> 2 * profit.
    """
    prof = profit_on_win(neg_odds, stake)     # e.g., 208.33 on 250 @ -120
    miss_net = prof - stake                   # e.g., -41.67
    hit_net  = 2 * prof                       # e.g., +416.67
    be_rate = abs(miss_net) / (abs(miss_net) + hit_net)  # ≈ 9.09%
    hit_offsets_misses = hit_net / abs(miss_net)         # ≈ 10.0
    return miss_net, hit_net, be_rate, hit_offsets_misses

def fmt_line_pair(a: float, b: float) -> str:
    """
    Pretty-print a pair of spread lines (always show explicit signs),
    e.g., '+3.5/-1.5', '+3.5/+1.5', '-5.5/+3.5'.
    """
    def sgn(v: float) -> str:
        return f"+{v:.1f}" if v > 0 else f"{v:.1f}"  # v already carries sign
    return f"{sgn(a)}/{sgn(b)}"
# --------------------


def get_complete_games() -> List[Dict]:
    """
    Complete games with consensus (AVG) openers by market.
    We take ABS(spread) in SQL, average across rows (or single book),
    then quantize to 0.5 before analysis.
    """
    where_bits = [
        "e.final_home IS NOT NULL",
        "e.final_away IS NOT NULL",
        f"(e.final_home + e.final_away) BETWEEN {MIN_PLAUSIBLE_TOTAL} AND {MAX_PLAUSIBLE_TOTAL}",
    ]
    if REQUIRE_FINAL_STATUS:
        where_bits.append("LOWER(COALESCE(e.status,'')) IN ('final','finished','completed')")

    book_filter = "AND o.bookmaker_id = :bm" if BOOKMAKER_ID is not None else ""
    where_clause = " AND ".join(where_bits)

    sql = f"""
        WITH opener_agg AS (
            SELECT
                o.event_id,
                AVG(CASE WHEN o.market='spread' THEN ABS(o.line) END) AS spread_open_avg,
                AVG(CASE WHEN o.market='total'  THEN       o.line  END) AS total_open_avg
            FROM opener o
            WHERE 1=1 {book_filter}
            GROUP BY o.event_id
        )
        SELECT
            e.event_id,
            e.home_name,
            e.away_name,
            e.final_home,
            e.final_away,
            e.start_time_utc,
            oa.spread_open_avg AS spread_opener,
            oa.total_open_avg  AS total_opener
        FROM event e
        JOIN opener_agg oa ON oa.event_id = e.event_id
        WHERE {where_clause}
          AND (oa.spread_open_avg IS NOT NULL OR oa.total_open_avg IS NOT NULL)
        ORDER BY e.start_time_utc DESC
    """
    params = {"bm": BOOKMAKER_ID} if BOOKMAKER_ID is not None else {}

    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(sql, params).fetchall()

    cleaned: List[Dict] = []
    for r in rows:
        d = dict(r)
        d["final_home"] = int(d["final_home"])
        d["final_away"] = int(d["final_away"])
        if d.get("spread_opener") is not None:
            d["spread_opener"] = q05(float(d["spread_opener"]))
        if d.get("total_opener") is not None:
            d["total_opener"] = q05(float(d["total_opener"]))
        cleaned.append(d)
    return cleaned


# ----- SPREADS: true either-side using SIGNED margins and t = s - m -----
def analyze_spreads_true_either(games: List[Dict]):
    rows = [g for g in games if g.get("spread_opener") is not None]
    if not rows:
        print("\nNo spread data available.")
        return

    # signed margin: + when home wins by that many, - when away wins by that many
    pairs = [{"opener": float(g["spread_opener"]),
              "margin_signed": int(g["final_home"]) - int(g["final_away"])}
             for g in rows]

    print("\nSPREADS — TRUE EITHER-SIDE (signed margins, opposite line t = s − m, t≥0.5)")
    print("=" * 98)
    print("m  |  neg-side  |  pos-side  |  cross-zero |  either-side | example lines")
    print("-" * 98)

    avg_open = q05(sum(p["opener"] for p in pairs) / len(pairs))

    for m in SPREAD_MIDDLE_SIZES:
        neg_hits = pos_hits = cross_hits = either_hits = 0
        total = 0

        for p in pairs:
            s = p["opener"]      # opener magnitude (always .5)
            t = q05(s - m)       # opposite line magnitude, must be >= 0.5 to exist
            x = p["margin_signed"]

            # skip impossible middle gaps (cannot have a book at t < 0.5)
            if t < 0.5:
                continue

            total += 1

            # Basketball has no spread ties; exclude x == 0 from any "both-win".
            if x == 0:
                neg = pos = crz = False
            else:
                # neg-side: +s vs -t  → both win if -s < x < -t
                neg = (-s < x < -t)
                # pos-side: -s vs +t  → both win if  t < x <  s
                pos = (t < x < s)
                # cross-zero: +s vs +t → both win if (-s < x < 0) or (0 < x < t)
                crz = ((-s < x < 0) or (0 < x < t))

            if neg:  neg_hits  += 1
            if pos:  pos_hits  += 1
            if crz:  cross_hits += 1
            if neg or pos or crz:
                either_hits += 1

        # rates
        neg_rate    = neg_hits    / total if total else 0.0
        pos_rate    = pos_hits    / total if total else 0.0
        cross_rate  = cross_hits  / total if total else 0.0
        either_rate = either_hits / total if total else 0.0

        # example lines @ dataset average opener (pick the cross-zero pair if valid; else pos-side)
        ex_t = q05(avg_open - m)
        if ex_t >= 0.5:
            example = fmt_line_pair(+avg_open, +ex_t)  # cross-zero: +s / +t
        else:
            # fall back to pos-side example
            example = fmt_line_pair(-avg_open, +q05(max(0.5, ex_t)))  # show as -s/+t (t clamped for display)

        print(f"{m:<3}|  {neg_rate:>7.1%}  |  {pos_rate:>7.1%}  |   {cross_rate:>7.1%}  |"
              f"  {either_rate:>9.1%} | {example}")


# ----- TOTALS: anchored O/U (same as before, with either-side union) -----
def analyze_totals_either(games: List[Dict]):
    rows = [g for g in games if g.get("total_opener") is not None]
    if not rows:
        print("\nNo total data available.")
        return

    pairs = [{"opener": float(g["total_opener"]),
              "total": int(g["final_home"]) + int(g["final_away"])}
             for g in rows]

    print("\nTOTALS — ANCHORED (either-side, absolute totals)")
    print("=" * 78)
    print("m  |  low-only  |  high-only |  either-side | example window")
    print("-" * 78)

    avg_open = q05(sum(p["opener"] for p in pairs) / len(pairs))

    for m in TOTAL_MIDDLE_SIZES:
        low_hits = high_hits = either_hits = total = 0

        for p in pairs:
            s = p["opener"]
            t = q05(s - m)  # lower line
            x = p["total"]

            # Both-win requires O at lower line and U at upper line.
            # If t < 0.5 (nonsensical for totals), skip this event for this m.
            if t < 0.5:
                continue

            total += 1

            lowL, lowH   = q05(t), q05(s)    # Over @ t, Under @ s
            highL, highH = q05(s), q05(s+m)  # Over @ s, Under @ s+m

            low_hit  = (lowL  < x < lowH)
            high_hit = (highL < x < highH)

            if low_hit:  low_hits  += 1
            if high_hit: high_hits += 1
            if low_hit or high_hit:
                either_hits += 1

        low_rate    = low_hits   / total if total else 0.0
        high_rate   = high_hits  / total if total else 0.0
        either_rate = either_hits/ total if total else 0.0

        ex_t = q05(avg_open - m)
        if ex_t >= 0.5:
            example = f"O{ex_t:.1f}/U{avg_open:.1f}"
        else:
            example = "(n/a)"

        print(f"{m:<3}|  {low_rate:>7.1%}  |  {high_rate:>7.1%}  |  {either_rate:>9.1%} | {example}")


# ----- Pricing summary & distributions -----
def show_pricing_summary():
    miss_net, hit_net, be_rate, hit_offsets_misses = miss_and_hit_net(
        AMERICAN_ODDS_PER_SIDE, STAKE_PER_SIDE
    )
    print("\nPRICING SUMMARY (applies to spreads & totals)")
    print("=" * 78)
    print(f"Per-side odds: {AMERICAN_ODDS_PER_SIDE}, Stake per side: ${STAKE_PER_SIDE:.2f}")
    print(f"Miss (one win, one loss): ${miss_net:.2f}")
    print(f"Hit  (both win)         : ${hit_net:.2f}")
    print(f"Breakeven hit-rate      : {be_rate:.2%}  (≈ 1 hit per {int(round(1/be_rate))} attempts)")
    print(f"1 hit offsets about     : {hit_offsets_misses:.1f} misses")

def show_distribution_snapshots(games: List[Dict]):
    """
    Orientation snapshot: |result - round_half_up(opener)| for sanity.
    """
    print("\nDISTRIBUTION SNAPSHOTS (relative to round-half-up(opener))")
    print("=" * 78)

    # Spreads
    srows = [g for g in games if g.get("spread_opener") is not None]
    if srows:
        diffs = []
        for g in srows:
            center = round_half_up_int(float(g["spread_opener"]))
            margin_abs = abs(int(g["final_home"]) - int(g["final_away"]))
            diffs.append(abs(margin_abs - center))
        bins = [(0.0,0.5,"±0"), (0.5,1.5,"0.5–1.5"), (1.5,2.5,"1.5–2.5"),
                (2.5,3.5,"2.5–3.5"), (3.5,5.5,"3.5–5.5"), (5.5,float('inf'),">5.5")]
        total = len(diffs)
        print("\nSPREAD: |margin - near_int(opener)|")
        for a,b,label in bins:
            c = sum(1 for d in diffs if (d >= a and (d < b if b != float('inf') else True)))
            print(f"  {label:>8}: {c:>4} games ({(c/total if total else 0):>5.1%})")

    # Totals
    trows = [g for g in games if g.get("total_opener") is not None]
    if trows:
        diffs = []
        for g in trows:
            center = round_half_up_int(float(g["total_opener"]))
            total_pts = int(g["final_home"]) + int(g["final_away"])
            diffs.append(abs(total_pts - center))
        bins = [(0.0,1.0,"±0"), (1.0,2.0,"1–2"), (2.0,3.0,"2–3"),
                (3.0,5.0,"3–5"), (5.0,8.0,"5–8"), (8.0,float('inf'),">8")]
        total = len(diffs)
        print("\nTOTAL: |total - near_int(opener)|")
        for a,b,label in bins:
            c = sum(1 for d in diffs if (d >= a and (d < b if b != float('inf') else True)))
            print(f"  {label:>8}: {c:>4} games ({(c/total if total else 0):>5.1%})")


def main():
    print("EBASKETBALL MIDDLE WINDOWS — TRUE EITHER-SIDE (t = s − m)")
    print("=" * 98)

    games = get_complete_games()
    if not games:
        print("No complete games found (check DB path/filters).")
        return

    show_pricing_summary()
    analyze_spreads_true_either(games)
    analyze_totals_either(games)
    show_distribution_snapshots(games)

    print("\nNotes:")
    print("• Spreads use SIGNED margins and only allow the opposite line at t = s − m (and t ≥ 0.5).")
    print("• We report neg-side (+s/−t), pos-side (−s/+t), cross-zero (+s/+t), and their union (either-side).")
    print("• Totals are the usual O@lower & U@upper anchored windows.")
    print("• Basketball has no spread ties (margin=0), and these are excluded by construction.\n")


if __name__ == "__main__":
    main()
