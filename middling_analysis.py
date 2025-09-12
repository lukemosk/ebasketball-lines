# middling_analysis.py — Anchored eBasketball middle analysis (half-point lines, integer outcomes)
import sqlite3
import math
from typing import List, Dict, Optional

DB = "data/ebasketball.db"

# -------- CONFIG --------
BOOKMAKER_ID: Optional[int] = None   # set to an int to restrict (e.g., 1 for Bet365) or leave None for consensus
REQUIRE_FINAL_STATUS = False         # set True if your event.status has reliable 'final/completed' values
MIN_PLAUSIBLE_TOTAL = 80             # guard vs premature finals; tweak for your league
MAX_PLAUSIBLE_TOTAL = 250

SPREAD_MIDDLE_SIZES = [1, 2, 3, 4, 5]
TOTAL_MIDDLE_SIZES  = [2, 3, 4, 5, 6]

# Pricing assumptions (-110 / -110, equal stakes)
# Miss (one win, one loss) = -$10 net; Hit (both win) = +$200 net.
PRICE_OVERROUND = 10
PRICE_HIT_WIN   = 200
# ------------------------


# -------- Helpers (rounding & quantizing) --------
def round_half_up_int(x: float) -> int:
    """Round halves up to the nearest integer (2.5 -> 3, 3.5 -> 4)."""
    return math.floor(x + 0.5)

def q05(x: float) -> float:
    """Quantize to nearest 0.5 (always produce *.0 or *.5)."""
    return round(x * 2.0) / 2.0

def is_half_step(x: float) -> bool:
    return abs(x * 2 - round(x * 2)) < 1e-9
# -------------------------------------------------


def get_complete_games() -> List[Dict]:
    """
    Return complete games with consensus (AVG) openers by market.
    We take ABS(spread) in SQL, average across rows (or single book),
    then quantize to 0.5 in Python before analysis.
    """
    where_bits = [
        "e.final_home IS NOT NULL",
        "e.final_away IS NOT NULL",
        f"(e.final_home + e.final_away) BETWEEN {MIN_PLAUSIBLE_TOTAL} AND {MAX_PLAUSIBLE_TOTAL}",
    ]
    if REQUIRE_FINAL_STATUS:
        # Adjust values to your DB if different
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

    # Quantize openers to .5; cast finals to int
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


# -------- Anchored middle window builders (half-point edges) --------
def spread_windows_anchored(opener_half: float, m: int):
    """
    Two possible anchored spread windows at width m (points):
      1) Anchor HIGH at the opener: (opener - m, opener)   → e.g., -3.5 / +5.5 for m=2, opener=5.5
      2) Anchor LOW  at the opener: (opener, opener + m)   → e.g., -5.5 / +6.5 for m=1
    Edges must be half-steps; outcome is integer margin; hit iff low < margin < high.
    """
    assert is_half_step(opener_half), "opener must be quantized to .5"
    low1, high1 = q05(opener_half - m), q05(opener_half)
    low2, high2 = q05(opener_half), q05(opener_half + m)
    return (low1, high1), (low2, high2)

def total_windows_anchored(opener_half: float, m: int):
    """Same as spreads but interpret as O-low / U-high when printing."""
    return spread_windows_anchored(opener_half, m)
# --------------------------------------------------------------------


def analyze_spread_middles(games: List[Dict]) -> None:
    print("SPREAD MIDDLING ANALYSIS (anchored at opener)")
    print("=" * 60)

    rows = [g for g in games if g.get("spread_opener") is not None]
    if not rows:
        print("No spread data available")
        return

    print(f"Analyzing {len(rows)} games with spread openers\n")

    # integer margins
    pairs = [{"opener": float(g["spread_opener"]),
              "margin": abs(int(g["final_home"]) - int(g["final_away"]))}
             for g in rows]

    middle_breakeven = PRICE_OVERROUND / (PRICE_OVERROUND + PRICE_HIT_WIN)

    print("Middle Size | Hit Rate | Expected Value | Status     | Example Scenario")
    print("-" * 75)

    # Example line: use average opener (quantized) and anchor-high window
    avg_open = q05(sum(p["opener"] for p in pairs) / len(pairs))

    for m in SPREAD_MIDDLE_SIZES:
        hits = 0
        total = 0
        for p in pairs:
            total += 1
            (l1, h1), (l2, h2) = spread_windows_anchored(p["opener"], m)
            # Count a hit if EITHER anchored window would have hit
            if (l1 < p["margin"] < h1) or (l2 < p["margin"] < h2):
                hits += 1

        hit_rate = hits / total if total else 0.0
        ev = (hit_rate * PRICE_HIT_WIN) - ((1 - hit_rate) * PRICE_OVERROUND)
        status = ("PROFITABLE" if hit_rate >= middle_breakeven
                  else "CLOSE" if hit_rate >= 0.8 * middle_breakeven
                  else "UNPROFITABLE")

        # Display the opener-anchored (high) example: (-[avg_open - m], +[avg_open])
        exL, exH = spread_windows_anchored(avg_open, m)[0]
        example = f"-{exL:.1f}/+{exH:.1f}"  # always .5/.5

        print(f"{m:>11}pt | {hit_rate:>7.1%} | ${ev:>+11.2f} | {status:<10} | {example}")

    print(f"\nBreak-even rate needed: {middle_breakeven:.1%}")
    print(f"Risk: ${PRICE_OVERROUND} juice | Reward: ${PRICE_HIT_WIN} (both sides win)")


def analyze_total_middles(games: List[Dict]) -> None:
    print("\n\nTOTAL MIDDLING ANALYSIS (anchored at opener)")
    print("=" * 60)

    rows = [g for g in games if g.get("total_opener") is not None]
    if not rows:
        print("No total data available")
        return

    print(f"Analyzing {len(rows)} games with total openers\n")

    pairs = [{"opener": float(g["total_opener"]),
              "total": int(g["final_home"]) + int(g["final_away"])}
             for g in rows]

    middle_breakeven = PRICE_OVERROUND / (PRICE_OVERROUND + PRICE_HIT_WIN)

    print("Middle Size | Hit Rate | Expected Value | Status     | Example Scenario")
    print("-" * 75)

    avg_open = q05(sum(p["opener"] for p in pairs) / len(pairs))

    for m in TOTAL_MIDDLE_SIZES:
        hits = 0
        total = 0
        for p in pairs:
            total += 1
            (l1, h1), (l2, h2) = total_windows_anchored(p["opener"], m)
            if (l1 < p["total"] < h1) or (l2 < p["total"] < h2):
                hits += 1

        hit_rate = hits / total if total else 0.0
        ev = (hit_rate * PRICE_HIT_WIN) - ((1 - hit_rate) * PRICE_OVERROUND)
        status = ("PROFITABLE" if hit_rate >= middle_breakeven
                  else "CLOSE" if hit_rate >= 0.8 * middle_breakeven
                  else "UNPROFITABLE")

        # Example: show anchor-high (Over at low, Under at opener)
        exL, exH = total_windows_anchored(avg_open, m)[0]
        example = f"O{exL:.1f}/U{exH:.1f}"

        print(f"{m:>11}pt | {hit_rate:>7.1%} | ${ev:>+11.2f} | {status:<10} | {example}")

    print(f"\nBreak-even rate needed: {middle_breakeven:.1%}")


def show_distribution_analysis(games: List[Dict]) -> None:
    """
    Orientation plot: how far results sit from the "natural" centers.
    For spreads we compute |margin - C| where C is the integer near the opener (round-half-up).
    For totals we compute |total_pts - C|.
    """
    print("\n\nDISTRIBUTION ANALYSIS (relative to near-integer center)")
    print("=" * 60)

    # Spread
    srows = [g for g in games if g.get("spread_opener") is not None]
    if srows:
        print("\nSPREAD MARGINS vs OPENERS (center = round_half_up(opener)):")
        diffs = []
        for g in srows:
            opener = float(g["spread_opener"])
            center = round_half_up_int(opener)  # integer near opener
            margin = abs(int(g["final_home"]) - int(g["final_away"]))
            diffs.append(abs(margin - center))

        bins = [
            (0.0, 0.5, "Exactly centered (±0)"),
            (0.5, 1.5, "0.5–1.5 off"),
            (1.5, 2.5, "1.5–2.5 off"),
            (2.5, 3.5, "2.5–3.5 off"),
            (3.5, 5.5, "3.5–5.5 off"),
            (5.5, float("inf"), ">5.5 off"),
        ]
        total = len(diffs)
        for a, b, label in bins:
            count = sum(1 for d in diffs if (d >= a and (d < b if b != float("inf") else True)))
            pct = count / total if total else 0.0
            print(f"  {label:>22}: {count:>3} games ({pct:>5.1%})")

    # Totals
    trows = [g for g in games if g.get("total_opener") is not None]
    if trows:
        print("\nTOTAL POINTS vs OPENERS (center = round_half_up(opener)):")
        diffs = []
        for g in trows:
            opener = float(g["total_opener"])
            center = round_half_up_int(opener)
            total_pts = int(g["final_home"]) + int(g["final_away"])
            diffs.append(abs(total_pts - center))

        bins = [
            (0.0, 1.0, "Exactly centered (±0)"),
            (1.0, 2.0, "1–2 off"),
            (2.0, 3.0, "2–3 off"),
            (3.0, 5.0, "3–5 off"),
            (5.0, 8.0, "5–8 off"),
            (8.0, float("inf"), ">8 off"),
        ]
        total = len(diffs)
        for a, b, label in bins:
            count = sum(1 for d in diffs if (d >= a and (d < b if b != float("inf") else True)))
            pct = count / total if total else 0.0
            print(f"  {label:>22}: {count:>3} games ({pct:>5.1%})")


def main():
    print("EBASKETBALL MIDDLING OPPORTUNITY ANALYSIS — ANCHORED")
    print("=" * 60)

    games = get_complete_games()
    if not games:
        print("No complete games found in database (check filters / DB path)")
        return

    print(f"Analyzing {len(games)} complete games\n")
    print("Assumptions:")
    print("• All spreads/totals are posted at half-points (.5).")
    print("• Outcomes are integers (margins & totals).")
    print("• Windows are ANCHORED at the opener: (opener−m, opener) and (opener, opener+m).")
    print("• Hit = strictly inside the two .5 lines (both sides win).")
    print("• Pricing assumes -110/-110 with equal stakes (miss = -$10, hit = +$200).\n")

    analyze_spread_middles(games)
    analyze_total_middles(games)
    show_distribution_analysis(games)

    middle_breakeven = PRICE_OVERROUND / (PRICE_OVERROUND + PRICE_HIT_WIN)
    print("\n" + "=" * 60)
    print("SUMMARY:")
    print(f"• Hit rates above {middle_breakeven:.1%} are profitable at -110/-110.")
    print("• This evaluates *possibility* of a hit given the opener; for realized middles, store timestamped multi-book lines.\n")


if __name__ == "__main__":
    main()
