# middling_compare.py — Anchored middle analysis for eBasketball
# Focus: -120 per side at $250 stake; show hit rates + pricing summary (no EV column)
# Adds: CLI to sample random example games for a given middle size & side (spread/total)
#
# Model: absolute, anchored windows (no cross-zero special case, no t>=0.5 enforcement).
#        Spreads use absolute margin; Totals use absolute total points.
#        Hit requires strict interior: low < result < high (both bets win).

import argparse
import random
import sqlite3
import math
from typing import List, Dict, Optional, Tuple

DB = "data/ebasketball.db"

# -------- CONFIG --------
BOOKMAKER_ID: Optional[int] = None   # e.g., 1 for Bet365, or None for consensus AVG
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


# ----- anchored windows (opener is one edge; check both directions) -----
def anchored_windows(opener_half: float, m: int) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """
    Two .5-edge windows at width m:
      - LOW window  (anchor HIGH at opener): (opener - m, opener)
      - HIGH window (anchor LOW  at opener): (opener, opener + m)
    Hit iff integer result lies strictly inside.
    """
    low1, high1 = q05(opener_half - m), q05(opener_half)
    low2, high2 = q05(opener_half), q05(opener_half + m)
    return (low1, high1), (low2, high2)
# -----------------------------------------------------------------------


def print_table_header(title: str):
    print(f"\n{title}")
    print("=" * 78)
    print("m  |  low-only  |  high-only |  either-side | example window")
    print("-" * 78)


def analyze_block(pairs: List[Dict], sizes: List[int], is_total: bool):
    """
    Core loop used by spreads and totals.
    pairs: [{ 'opener': float, 'result': int, 'home': str, 'away': str, 'date': str, 'final': str }]
    """
    avg_open = q05(sum(p["opener"] for p in pairs) / len(pairs))

    for m in sizes:
        low_hits = high_hits = either_hits = total = 0

        for p in pairs:
            (l1, h1), (l2, h2) = anchored_windows(p["opener"], m)
            x = p["result"]
            total += 1
            low_hit  = (l1 < x < h1)    # opener is the HIGH edge
            high_hit = (l2 < x < h2)    # opener is the LOW  edge
            if low_hit:  low_hits  += 1
            if high_hit: high_hits += 1
            if low_hit or high_hit:
                either_hits += 1

        low_rate    = low_hits   / total if total else 0.0
        high_rate   = high_hits  / total if total else 0.0
        either_rate = either_hits/ total if total else 0.0

        # Example window: show LOW window at dataset avg opener
        exL, exH = anchored_windows(avg_open, m)[0]
        example = (f"O{exL:.1f}/U{exH:.1f}" if is_total else format_spread_window(exL, exH))

        print(f"{m:<3}|  {low_rate:>7.1%}  |  {high_rate:>7.1%}  |  {either_rate:>9.1%} | {example}")


def analyze_spreads(games: List[Dict]):
    rows = [g for g in games if g.get("spread_opener") is not None]
    if not rows:
        print("\nNo spread data available.")
        return

    pairs = [{
        "opener": float(g["spread_opener"]),
        "result": abs(int(g["final_home"]) - int(g["final_away"])),
        "home": g["home_name"],
        "away": g["away_name"],
        "date": (g["start_time_utc"] or "")[:10],
        "final": f'{int(g["final_home"])}-{int(g["final_away"])}',
    } for g in rows]

    print_table_header("SPREADS (anchored at opener; either-side allowed)")
    analyze_block(pairs, SPREAD_MIDDLE_SIZES, is_total=False)
    return pairs  # for sampling


def analyze_totals(games: List[Dict]):
    rows = [g for g in games if g.get("total_opener") is not None]
    if not rows:
        print("\nNo total data available.")
        return

    pairs = [{
        "opener": float(g["total_opener"]),
        "result": int(g["final_home"]) + int(g["final_away"]),
        "home": g["home_name"],
        "away": g["away_name"],
        "date": (g["start_time_utc"] or "")[:10],
        "final": f'{int(g["final_home"])}-{int(g["final_away"])}',
    } for g in rows]

    print_table_header("TOTALS (anchored at opener; either-side allowed)")
    analyze_block(pairs, TOTAL_MIDDLE_SIZES, is_total=True)
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


def show_distribution(games: List[Dict]):
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
            margin = abs(int(g["final_home"]) - int(g["final_away"]))
            diffs.append(abs(margin - center))
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


# ----- Sampling helpers -----
def sample_spread_examples(pairs: List[Dict], m: int, side: str, n: int, seed: Optional[int] = None):
    """
    side: 'low' (opener-m..opener), 'high' (opener..opener+m), or 'either'
    """
    if seed is not None:
        random.seed(seed)

    matches = []
    for p in pairs:
        o = p["opener"]
        x = p["result"]
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
        print(f"\nNo spread matches for m={m}, side={side}.")
        return

    k = min(n, len(matches))
    picks = random.sample(matches, k)
    print(f"\nSAMPLE SPREAD MATCHES  (m={m}, side={side}, n={k})")
    print("-" * 78)
    for (p, (L, H), hit_side) in picks:
        print(f"{p['date']} | {p['home']} vs {p['away']}")
        print(f"  opener: ±{p['opener']:.1f} | window: {format_spread_window(L, H)} ({hit_side})")
        print(f"  final: {p['final']}  | margin: {p['result']}")

def sample_total_examples(pairs: List[Dict], m: int, side: str, n: int, seed: Optional[int] = None):
    """
    side: 'low' (O at opener-m, U at opener), 'high' (O at opener, U at opener+m), or 'either'
    """
    if seed is not None:
        random.seed(seed)

    matches = []
    for p in pairs:
        o = p["opener"]
        x = p["result"]
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
        print(f"\nNo total matches for m={m}, side={side}.")
        return

    k = min(n, len(matches))
    picks = random.sample(matches, k)
    print(f"\nSAMPLE TOTAL MATCHES   (m={m}, side={side}, n={k})")
    print("-" * 78)
    for (p, (_o, L, _u, H), hit_side) in picks:
        print(f"{p['date']} | {p['home']} vs {p['away']}")
        print(f"  opener: {p['opener']:.1f} | window: O{L:.1f}/U{H:.1f} ({hit_side})")
        print(f"  final: {p['final']}  | total: {p['result']}")
# ----------------------------


def main():
    parser = argparse.ArgumentParser(description="Anchored middle analyzer with sampling")
    parser.add_argument("--sample-market", choices=["spread", "total"], help="Market to sample from")
    parser.add_argument("--sample-side", choices=["low", "high", "either"], help="Which side to sample")
    parser.add_argument("--sample-m", type=int, help="Middle size (points)")
    parser.add_argument("--sample-n", type=int, default=1, help="How many random examples to print")
    parser.add_argument("--seed", type=int, help="Random seed for reproducibility")
    args = parser.parse_args()

    print("EBASKETBALL MIDDLE ANALYZER — ANCHORED (either-side), -120 @ $250/side")
    print("=" * 78)

    games = get_complete_games()
    if not games:
        print("No complete games found (check DB path/filters).")
        return

    show_pricing_summary()

    spread_pairs = analyze_spreads(games) or []
    total_pairs  = analyze_totals(games) or []
    show_distribution(games)

    # Sampling (optional)
    if args.sample_market and args.sample_side and args.sample_m is not None:
        if args.sample_market == "spread":
            sample_spread_examples(spread_pairs, args.sample_m, args.sample_side, args.sample_n, args.seed)
        else:
            sample_total_examples(total_pairs, args.sample_m, args.sample_side, args.sample_n, args.seed)
    elif any([args.sample_market, args.sample_side, args.sample_m is not None]):
        print("\n[!] To sample, provide --sample-market, --sample-side, and --sample-m together.")

    print("\nNotes:")
    print("• Anchored windows test (opener−m, opener) and (opener, opener+m); either counts as a hit.")
    print("• Lines are modeled at .5; outcomes (margins/totals) are integers; hit requires strict interior (both bets win).")
    print("• This measures possibility relative to the opener (no guarantee the opposite line existed).")

# --- quick reference footer ---------------------------------------------------
def _print_quick_reference():
    import textwrap
    msg = textwrap.dedent("""
        QUICK REFERENCE — Sample commands
        ---------------------------------
        • Grab 1 random spread example that hit m=3 on the HIGH side (opener..opener+3)
          python middling_compare.py --sample-market spread --sample-m 3 --sample-side high

        • 2 random spread examples that hit m=2 on the LOW side (opener-2..opener)
          python middling_compare.py --sample-market spread --sample-m 2 --sample-side low --sample-n 2 --seed 7

        • 1 random total example that hit m=5 on EITHER side
          python middling_compare.py --sample-market total --sample-m 5 --sample-side either
    """).strip()
    print("\n" + msg + "\n")

if __name__ == "__main__":
    main()
    _print_quick_reference()

# Example sample commands:


# Grab 1 random spread example that hit m=3 on the HIGH side (opener..opener+3)
#python middling_compare.py --sample-market spread --sample-m 3 --sample-side high

# 2 random spread examples that hit m=2 on the LOW side (opener-2..opener)
#python middling_compare.py --sample-market spread --sample-m 2 --sample-side low --sample-n 2 --seed 7

# 1 random total example that hit m=5 on EITHER side
#python middling_compare.py --sample-market total --sample-m 5 --sample-side either
