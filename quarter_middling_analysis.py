# quarter_middling_analysis.py
"""
Quarter-anchored middle analysis for eBasketball
Analyzes middle hit rates when anchored to quarter-end lines instead of pregame openers
"""

import argparse
import random
import sqlite3
import math
from typing import List, Dict, Optional, Tuple

DB = "data/ebasketball.db"

# -------- CONFIG --------
BOOKMAKER_ID: Optional[str] = None   # e.g., "bet365", or None for all bookmakers
REQUIRE_FINAL_STATUS = False         # flip True if event.status is reliable
MIN_PLAUSIBLE_TOTAL = 80
MAX_PLAUSIBLE_TOTAL = 250

SPREAD_MIDDLE_SIZES = [1, 2, 3, 4, 5]
TOTAL_MIDDLE_SIZES  = [2, 3, 4, 5, 6]

AMERICAN_ODDS_PER_SIDE = -120
STAKE_PER_SIDE = 250.0
# ------------------------


# ----- helpers: rounding/quantizing and pricing math -----
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

def format_spread_window(low: float, high: float) -> str:
    """Pretty-print a spread window as -x.x/+y.y, handling negative lows cleanly."""
    low = q05(low); high = q05(high)
    low_str  = f"{low:.1f}" if low < 0 else f"-{low:.1f}"
    high_str = f"+{high:.1f}"
    return f"{low_str}/{high_str}"
# ---------------------------------------------------------


def get_quarter_games(quarters: List[int] = None) -> List[Dict]:
    """
    Get complete games with quarter-end lines and final results.
    quarters: List of quarters to include (default: [1,2,3,4])
    """
    if quarters is None:
        quarters = [1, 2, 3, 4]
    
    quarter_filter = f"AND q.quarter IN ({','.join(map(str, quarters))})"
    
    where_bits = [
        "e.final_home IS NOT NULL",
        "e.final_away IS NOT NULL",
        f"(e.final_home + e.final_away) BETWEEN {MIN_PLAUSIBLE_TOTAL} AND {MAX_PLAUSIBLE_TOTAL}",
    ]
    if REQUIRE_FINAL_STATUS:
        where_bits.append("LOWER(COALESCE(e.status,'')) IN ('final','finished','completed')")

    book_filter = "AND q.bookmaker_id = :bm" if BOOKMAKER_ID is not None else ""
    where_clause = " AND ".join(where_bits)

    sql = f"""
        WITH quarter_agg AS (
            SELECT
                q.event_id,
                q.quarter,
                AVG(CASE WHEN q.market='spread' THEN ABS(q.line) END) AS spread_line_avg,
                AVG(CASE WHEN q.market='total'  THEN       q.line  END) AS total_line_avg
            FROM quarter_line q
            WHERE 1=1 {book_filter} {quarter_filter}
            GROUP BY q.event_id, q.quarter
        )
        SELECT
            e.event_id,
            e.home_name,
            e.away_name,
            e.final_home,
            e.final_away,
            e.start_time_utc,
            qa.quarter,
            qa.spread_line_avg AS spread_quarter_line,
            qa.total_line_avg  AS total_quarter_line
        FROM event e
        JOIN quarter_agg qa ON qa.event_id = e.event_id
        WHERE {where_clause}
          AND (qa.spread_line_avg IS NOT NULL OR qa.total_line_avg IS NOT NULL)
        ORDER BY e.start_time_utc DESC, qa.quarter
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
        if d.get("spread_quarter_line") is not None:
            d["spread_quarter_line"] = q05(float(d["spread_quarter_line"]))
        if d.get("total_quarter_line") is not None:
            d["total_quarter_line"] = q05(float(d["total_quarter_line"]))
        cleaned.append(d)
    return cleaned


# ----- anchored windows (quarter line is one edge; check both directions) -----
def anchored_windows(quarter_line: float, m: int) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """
    Two .5-edge windows at width m:
      - LOW window  (anchor HIGH at quarter_line): (quarter_line - m, quarter_line)
      - HIGH window (anchor LOW  at quarter_line): (quarter_line, quarter_line + m)
    Hit iff integer result lies strictly inside.
    """
    low1, high1 = q05(quarter_line - m), q05(quarter_line)
    low2, high2 = q05(quarter_line), q05(quarter_line + m)
    return (low1, high1), (low2, high2)
# -----------------------------------------------------------------------


def print_quarter_table_header(title: str, quarters: List[int]):
    quarter_str = "Q" + ",Q".join(map(str, quarters))
    print(f"\n{title} (anchored to {quarter_str} lines)")
    print("=" * 78)
    print("m  |  low-only  |  high-only |  either-side | example window")
    print("-" * 78)


def analyze_quarter_block(pairs: List[Dict], sizes: List[int], is_total: bool, quarters: List[int]):
    """
    Core loop used by spreads and totals for quarter analysis.
    pairs: [{ 'quarter_line': float, 'result': int, 'quarter': int, 'home': str, 'away': str, 'date': str, 'final': str }]
    """
    if not pairs:
        print(f"No data available for quarters {quarters}")
        return
    
    avg_line = q05(sum(p["quarter_line"] for p in pairs) / len(pairs))

    for m in sizes:
        low_hits = high_hits = either_hits = total = 0

        for p in pairs:
            (l1, h1), (l2, h2) = anchored_windows(p["quarter_line"], m)
            x = p["result"]
            total += 1
            low_hit  = (l1 < x < h1)    # quarter_line is the HIGH edge
            high_hit = (l2 < x < h2)    # quarter_line is the LOW  edge
            if low_hit:  low_hits  += 1
            if high_hit: high_hits += 1
            if low_hit or high_hit:
                either_hits += 1

        low_rate    = low_hits   / total if total else 0.0
        high_rate   = high_hits  / total if total else 0.0
        either_rate = either_hits/ total if total else 0.0

        # Example window: show LOW window at dataset avg quarter line
        exL, exH = anchored_windows(avg_line, m)[0]
        example = (f"O{exL:.1f}/U{exH:.1f}" if is_total else format_spread_window(exL, exH))

        print(f"{m:<3}|  {low_rate:>7.1%}  |  {high_rate:>7.1%}  |  {either_rate:>9.1%} | {example}")


def analyze_quarter_spreads(games: List[Dict], quarters: List[int]):
    rows = [g for g in games if g.get("spread_quarter_line") is not None]
    if not rows:
        print(f"\nNo spread data available for quarters {quarters}.")
        return

    pairs = [{
        "quarter_line": float(g["spread_quarter_line"]),
        "result": abs(int(g["final_home"]) - int(g["final_away"])),
        "quarter": g["quarter"],
        "home": g["home_name"],
        "away": g["away_name"],
        "date": (g["start_time_utc"] or "")[:10],
        "final": f'{int(g["final_home"])}-{int(g["final_away"])}',
    } for g in rows]

    print_quarter_table_header("SPREADS (anchored at quarter-end; either-side allowed)", quarters)
    analyze_quarter_block(pairs, SPREAD_MIDDLE_SIZES, is_total=False, quarters=quarters)
    return pairs  # for sampling


def analyze_quarter_totals(games: List[Dict], quarters: List[int]):
    rows = [g for g in games if g.get("total_quarter_line") is not None]
    if not rows:
        print(f"\nNo total data available for quarters {quarters}.")
        return

    pairs = [{
        "quarter_line": float(g["total_quarter_line"]),
        "result": int(g["final_home"]) + int(g["final_away"]),
        "quarter": g["quarter"],
        "home": g["home_name"],
        "away": g["away_name"],
        "date": (g["start_time_utc"] or "")[:10],
        "final": f'{int(g["final_home"])}-{int(g["final_away"])}',
    } for g in rows]

    print_quarter_table_header("TOTALS (anchored at quarter-end; either-side allowed)", quarters)
    analyze_quarter_block(pairs, TOTAL_MIDDLE_SIZES, is_total=True, quarters=quarters)
    return pairs  # for sampling


def show_pricing_summary():
    miss_net, hit_net, be_rate, hit_offsets_misses = miss_and_hit_net(
        AMERICAN_ODDS_PER_SIDE, STAKE_PER_SIDE
    )
    print("\nPRICING SUMMARY (applies to both spreads & totals)")
    print("=" * 78)
    print(f"Per-side odds: {AMERICAN_ODDS_PER_SIDE}, Stake per side: ${STAKE_PER_SIDE:.2f}")
    print(f"Miss (one win, one loss): ${miss_net:.2f}")
    print(f"Hit  (both win)         : ${hit_net:.2f}")
    print(f"Breakeven hit-rate      : {be_rate:.2%}  (≈ 1 hit per {int(round(1/be_rate))} attempts)")
    print(f"1 hit offsets about     : {hit_offsets_misses:.1f} misses")


def show_quarter_distribution(games: List[Dict], quarters: List[int]):
    """
    Orientation snapshot: |result - round_half_up(quarter_line)| for sanity.
    """
    print(f"\nDISTRIBUTION SNAPSHOTS (relative to round-half-up(Q{',Q'.join(map(str, quarters))} lines))")
    print("=" * 78)

    # Spreads
    srows = [g for g in games if g.get("spread_quarter_line") is not None]
    if srows:
        diffs = []
        for g in srows:
            center = round_half_up_int(float(g["spread_quarter_line"]))
            margin = abs(int(g["final_home"]) - int(g["final_away"]))
            diffs.append(abs(margin - center))
        bins = [(0.0,0.5,"±0"), (0.5,1.5,"0.5–1.5"), (1.5,2.5,"1.5–2.5"),
                (2.5,3.5,"2.5–3.5"), (3.5,5.5,"3.5–5.5"), (5.5,float('inf'),">5.5")]
        total = len(diffs)
        print(f"\nSPREAD: |margin - near_int(Q{',Q'.join(map(str, quarters))} line)|")
        for a,b,label in bins:
            c = sum(1 for d in diffs if (d >= a and (d < b if b != float('inf') else True)))
            print(f"  {label:>8}: {c:>4} games ({(c/total if total else 0):>5.1%})")

    # Totals
    trows = [g for g in games if g.get("total_quarter_line") is not None]
    if trows:
        diffs = []
        for g in trows:
            center = round_half_up_int(float(g["total_quarter_line"]))
            total_pts = int(g["final_home"]) + int(g["final_away"])
            diffs.append(abs(total_pts - center))
        bins = [(0.0,1.0,"±0"), (1.0,2.0,"1–2"), (2.0,3.0,"2–3"),
                (3.0,5.0,"3–5"), (5.0,8.0,"5–8"), (8.0,float('inf'),">8")]
        total = len(diffs)
        print(f"\nTOTAL: |total - near_int(Q{',Q'.join(map(str, quarters))} line)|")
        for a,b,label in bins:
            c = sum(1 for d in diffs if (d >= a and (d < b if b != float('inf') else True)))
            print(f"  {label:>8}: {c:>4} games ({(c/total if total else 0):>5.1%})")


def show_coverage_stats(quarters: List[int]):
    """Show how many games have quarter line data vs total games"""
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        
        # Total games with finals
        total_games = con.execute("""
            SELECT COUNT(*) as count 
            FROM event 
            WHERE final_home IS NOT NULL AND final_away IS NOT NULL
              AND (final_home + final_away) BETWEEN ? AND ?
        """, (MIN_PLAUSIBLE_TOTAL, MAX_PLAUSIBLE_TOTAL)).fetchone()['count']
        
        # Games with quarter line data
        quarter_filter = f"AND q.quarter IN ({','.join(map(str, quarters))})"
        book_filter = "AND q.bookmaker_id = ?" if BOOKMAKER_ID else ""
        params = [MIN_PLAUSIBLE_TOTAL, MAX_PLAUSIBLE_TOTAL]
        if BOOKMAKER_ID:
            params.append(BOOKMAKER_ID)
            
        quarter_games = con.execute(f"""
            SELECT COUNT(DISTINCT e.event_id) as count
            FROM event e
            JOIN quarter_line q ON q.event_id = e.event_id
            WHERE e.final_home IS NOT NULL AND e.final_away IS NOT NULL
              AND (e.final_home + e.final_away) BETWEEN ? AND ?
              {quarter_filter} {book_filter}
        """, params).fetchone()['count']
        
        coverage_pct = (quarter_games / total_games * 100) if total_games > 0 else 0
        
        print(f"\nCOVERAGE STATS")
        print("=" * 78)
        print(f"Total games with finals: {total_games}")
        print(f"Games with Q{',Q'.join(map(str, quarters))} data: {quarter_games}")
        print(f"Coverage: {coverage_pct:.1f}%")


# ----- Sampling helpers -----
def sample_quarter_spread_examples(pairs: List[Dict], m: int, side: str, quarters: List[int], 
                                  n: int, seed: Optional[int] = None):
    """
    side: 'low' (quarter_line-m..quarter_line), 'high' (quarter_line..quarter_line+m), or 'either'
    """
    if seed is not None:
        random.seed(seed)

    matches = []
    for p in pairs:
        o = p["quarter_line"]
        x = p["result"]
        quarter = p["quarter"]
        (l1, h1), (l2, h2) = anchored_windows(o, m)
        low_hit  = (l1 < x < h1)
        high_hit = (l2 < x < h2)

        if side == "low" and low_hit and not high_hit:
            matches.append((p, (l1, h1), "low"))
        elif side == "high" and high_hit and not low_hit:
            matches.append((p, (l2, h2), "high"))
        elif side == "either" and (low_hit or high_hit):
            win_window = (l1, h1) if low_hit else (l2, h2)
            win_side = "low" if low_hit else "high"
            matches.append((p, win_window, win_side))

    if not matches:
        quarter_str = "Q" + ",Q".join(map(str, quarters))
        print(f"\nNo spread matches for m={m}, side={side} in {quarter_str} data.")
        return

    k = min(n, len(matches))
    picks = random.sample(matches, k)
    quarter_str = "Q" + ",Q".join(map(str, quarters))
    print(f"\nSAMPLE QUARTER SPREAD MATCHES  (m={m}, side={side}, {quarter_str}, n={k})")
    print("-" * 78)
    for (p, (L, H), hit_side) in picks:
        print(f"Q{p['quarter']} | {p['date']} | {p['home']} vs {p['away']}")
        print(f"  quarter line: ±{p['quarter_line']:.1f} | window: {format_spread_window(L, H)} ({hit_side})")
        print(f"  final: {p['final']}  | margin: {p['result']}")

def sample_quarter_total_examples(pairs: List[Dict], m: int, side: str, quarters: List[int],
                                 n: int, seed: Optional[int] = None):
    """
    side: 'low' (O at quarter_line-m, U at quarter_line), 'high' (O at quarter_line, U at quarter_line+m), or 'either'
    """
    if seed is not None:
        random.seed(seed)

    matches = []
    for p in pairs:
        o = p["quarter_line"]
        x = p["result"]
        quarter = p["quarter"]
        (l1, h1), (l2, h2) = anchored_windows(o, m)  # reuse
        low_hit  = (l1 < x < h1)  # Over@l1, Under@o
        high_hit = (l2 < x < h2)  # Over@o,  Under@o+m

        if side == "low" and low_hit and not high_hit:
            matches.append((p, ("O", l1, "U", h1), "low"))
        elif side == "high" and high_hit and not low_hit:
            matches.append((p, ("O", l2, "U", h2), "high"))
        elif side == "either" and (low_hit or high_hit):
            if low_hit:
                matches.append((p, ("O", l1, "U", h1), "low"))
            else:
                matches.append((p, ("O", l2, "U", h2), "high"))

    if not matches:
        quarter_str = "Q" + ",Q".join(map(str, quarters))
        print(f"\nNo total matches for m={m}, side={side} in {quarter_str} data.")
        return

    k = min(n, len(matches))
    picks = random.sample(matches, k)
    quarter_str = "Q" + ",Q".join(map(str, quarters))
    print(f"\nSAMPLE QUARTER TOTAL MATCHES   (m={m}, side={side}, {quarter_str}, n={k})")
    print("-" * 78)
    for (p, (_o, L, _u, H), hit_side) in picks:
        print(f"Q{p['quarter']} | {p['date']} | {p['home']} vs {p['away']}")
        print(f"  quarter line: {p['quarter_line']:.1f} | window: O{L:.1f}/U{H:.1f} ({hit_side})")
        print(f"  final: {p['final']}  | total: {p['result']}")
# ----------------------------


def main():
    parser = argparse.ArgumentParser(description="Quarter-anchored middle analyzer with sampling")
    parser.add_argument("--quarters", type=str, default="1,2,3,4", 
                       help="Comma-separated quarters to analyze (default: 1,2,3,4)")
    parser.add_argument("--sample-market", choices=["spread", "total"], help="Market to sample from")
    parser.add_argument("--sample-side", choices=["low", "high", "either"], help="Which side to sample")
    parser.add_argument("--sample-m", type=int, help="Middle size (points)")
    parser.add_argument("--sample-n", type=int, default=1, help="How many random examples to print")
    parser.add_argument("--seed", type=int, help="Random seed for reproducibility")
    args = parser.parse_args()

    # Parse quarters
    try:
        quarters = [int(q.strip()) for q in args.quarters.split(",")]
        quarters = [q for q in quarters if 1 <= q <= 4]  # Validate
        if not quarters:
            quarters = [1, 2, 3, 4]
    except:
        quarters = [1, 2, 3, 4]

    quarter_str = "Q" + ",Q".join(map(str, quarters))
    print(f"EBASKETBALL QUARTER MIDDLE ANALYZER — {quarter_str} LINES, -120 @ $250/side")
    print("=" * 78)

    games = get_quarter_games(quarters)
    if not games:
        print(f"No complete games found with {quarter_str} line data (check DB path/filters).")
        return

    show_coverage_stats(quarters)
    show_pricing_summary()

    spread_pairs = analyze_quarter_spreads(games, quarters) or []
    total_pairs  = analyze_quarter_totals(games, quarters) or []
    show_quarter_distribution(games, quarters)

    # Sampling (optional)
    if args.sample_market and args.sample_side and args.sample_m is not None:
        if args.sample_market == "spread":
            sample_quarter_spread_examples(spread_pairs, args.sample_m, args.sample_side, 
                                          quarters, args.sample_n, args.seed)
        else:
            sample_quarter_total_examples(total_pairs, args.sample_m, args.sample_side, 
                                        quarters, args.sample_n, args.seed)
    elif any([args.sample_market, args.sample_side, args.sample_m is not None]):
        print("\n[!] To sample, provide --sample-market, --sample-side, and --sample-m together.")

    print(f"\nNotes:")
    print(f"• Anchored windows test ({quarter_str} line-m, {quarter_str} line) and ({quarter_str} line, {quarter_str} line+m); either counts as a hit.")
    print("• Lines are modeled at .5; outcomes (margins/totals) are integers; hit requires strict interior (both bets win).")
    print(f"• This measures middle opportunity from {quarter_str} lines to final results.")
    print("• Coverage shows what % of total games have quarter line data captured.")

# --- quick reference footer ---------------------------------------------------
def _print_quick_reference():
    import textwrap
    msg = textwrap.dedent("""
        QUICK REFERENCE — Sample commands
        ---------------------------------
        • Analyze only Q2 (halftime) lines:
          python quarter_middling_analysis.py --quarters 2

        • Analyze Q1,Q3 lines only:
          python quarter_middling_analysis.py --quarters "1,3"

        • Sample Q2 spread hit at m=3, high side:
          python quarter_middling_analysis.py --quarters 2 --sample-market spread --sample-m 3 --sample-side high

        • Sample any quarter total hit at m=4:
          python quarter_middling_analysis.py --sample-market total --sample-m 4 --sample-side either --sample-n 3
    """).strip()
    print("\n" + msg + "\n")


if __name__ == "__main__":
    main()
    _print_quick_reference()