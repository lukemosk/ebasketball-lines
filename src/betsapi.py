from __future__ import annotations
import os
import datetime
import requests
from typing import List, Dict, Any, Optional, Tuple

# --------------------------------------------------------------------------------------
# Config / constants
# --------------------------------------------------------------------------------------
API_ROOT = "https://api.b365api.com"
BET365_V1 = "/v1/bet365"           # e.g. /v1/bet365/event, /v1/bet365/result, /v1/bet365/upcoming
EVENTS_V1 = "/v1/events"           # e.g. /v1/events/ended
EVENT_V1  = "/v1/event"            # e.g. /v1/event/view
PREMATCH_V3 = "https://api.b365api.com/v3/bet365/prematch"

SPORT_ID_BASKETBALL = 18

TOKEN = os.getenv("BETSAPI_KEY")
if not TOKEN:
    raise RuntimeError("BETSAPI_KEY missing from environment (.env)")

# Include exactly your target league(s) (lowercased)
TARGET_LEAGUE_NAMES = {
    "ebasketball h2h gg league - 4x5mins",
}

# Any snippet here (lowercased) will be excluded
BLOCKED_LEAGUE_SNIPPETS = {
    "ebasketball battle - 4x5mins",
}

DEFAULT_TIMEOUT = 15


# --------------------------------------------------------------------------------------
# HTTP helpers
# --------------------------------------------------------------------------------------
def _get_json(path: str, **params) -> Dict[str, Any]:
    """
    Low-level GET. Returns the full JSON dict from BetsAPI.
    `path` must start with a '/' (e.g. '/v1/bet365/upcoming').
    """
    if not path.startswith("/"):
        raise ValueError("path must start with '/' (e.g. '/v1/bet365/upcoming')")
    params = {"token": TOKEN, **params}
    r = requests.get(f"{API_ROOT}{path}", params=params, timeout=DEFAULT_TIMEOUT)
    r.raise_for_status()
    j = r.json()
    if not isinstance(j, dict):
        return {}
    return j


def _get_results(path: str, **params) -> List[Any]:
    """
    Convenience wrapper: returns the 'results' list (empty list if missing).
    """
    j = _get_json(path, **params)
    res = j.get("results")
    if isinstance(res, list):
        return res
    if isinstance(res, dict):
        # sometimes 'results' is a dict; callers may still want it
        return [res]
    return []


# --------------------------------------------------------------------------------------
# Utilities
# --------------------------------------------------------------------------------------
def _status_from_time_status(ts: str) -> str:
    """
    BetsAPI convention:
      "0" not started, "1" live, "3" finished
    Handle missing/empty time_status properly
    """
    if ts == "0":
        return "not_started"
    elif ts == "1":
        return "live"
    elif ts == "3":
        return "finished"
    else:
        # For empty, None, or unknown values, default to not_started
        # This prevents games from being marked as "ended" incorrectly
        return "not_started"


def _normalize_time(t: Any) -> str:
    """Accepts epoch or 'YYYY-MM-DD HH:MM:SS' and returns 'YYYY-MM-DD HH:MM:SS' UTC."""
    if isinstance(t, (int, float)) or (isinstance(t, str) and t.isdigit()):
        return datetime.datetime.utcfromtimestamp(int(t)).strftime("%Y-%m-%d %H:%M:%S")
    return str(t or "")


def _safe_league_name(ev: Dict[str, Any]) -> str:
    v = ev.get("league") or ev.get("league_name") or ""
    if isinstance(v, dict):
        v = v.get("name") or v.get("league_name") or ""
    return str(v).strip().lower()


def _safe_team_name(side: Any) -> str:
    if isinstance(side, dict):
        return str(side.get("name") or side.get("team_name") or "").strip()
    return str(side or "").strip()


def _normalize_list(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for ev in rows:
        ts = str(ev.get("time_status", "0"))  # Default to "0" if missing
        
        # Only include games that have actual data
        # Skip games with completely missing/invalid data
        if not ev.get("id") or not ev.get("home") or not ev.get("away"):
            continue
            
        out.append({
            "id": int(ev["id"]),
            "home": _safe_team_name(ev.get("home")),
            "away": _safe_team_name(ev.get("away")),
            "time": _normalize_time(ev.get("time")),
            "status": _status_from_time_status(ts),
            "league_name": _safe_league_name(ev),
        })
    return out


# --------------------------------------------------------------------------------------
# Public: Upcoming fixtures (prematch)
# --------------------------------------------------------------------------------------
def list_fixtures(_: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Return prematch fixtures for target eBasketball leagues (de-duped).
    """
    all_rows: List[Dict[str, Any]] = []
    for page in range(1, 6):
        page_rows = _get_results(f"{BET365_V1}/upcoming", sport_id=SPORT_ID_BASKETBALL, page=page)
        if not page_rows:
            break
        all_rows.extend(page_rows)

    if not all_rows:
        return []

    items = _normalize_list(all_rows)

    def is_target(name_lc: str) -> bool:
        if any(b in name_lc for b in BLOCKED_LEAGUE_SNIPPETS):
            return False
        return any(t in name_lc for t in TARGET_LEAGUE_NAMES)

    filtered = [x for x in items if is_target(x["league_name"])]

    # De-dup by FI id
    seen = set()
    uniq: List[Dict[str, Any]] = []
    for x in filtered:
        if x["id"] in seen:
            continue
        seen.add(x["id"])
        uniq.append(x)
    return uniq


# --------------------------------------------------------------------------------------
# Public: Events API (finished status + finals)
# --------------------------------------------------------------------------------------
def get_event_view(event_id: int) -> Dict[str, Any]:
    """
    Events API: details incl. time_status, scores, and 'ss' (e.g. '67-65').
    Use time_status == '3' to confirm finished.
    """
    results = _get_results(f"{EVENT_V1}/view", event_id=event_id)
    return results[0] if results else {}


def get_events_ended(date_str: str, league_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Events API: ended (finished) events for a date. Optionally filter by league_id.
    date_str: 'YYYY-MM-DD'
    """
    params = {"date": date_str}
    if league_id:
        params["league_id"] = league_id
    results = _get_results(f"{EVENTS_V1}/ended", **params)
    return results


def find_final_in_ended(event_id: int, date_str: str, league_id: Optional[int] = None) -> Tuple[Optional[int], Optional[int]]:
    """
    Scan ended list for the event; return (final_home, final_away) parsed from 'ss'
    or from scores.ft_home/ft_away if available.
    """
    for ev in get_events_ended(date_str, league_id):
        if str(ev.get("id")) == str(event_id):
            ss = ev.get("ss")
            if isinstance(ss, str) and "-" in ss:
                try:
                    l, r = ss.split("-", 1)
                    return int(l), int(r)
                except Exception:
                    pass
            scores = ev.get("scores") or {}
            fh = scores.get("ft_home")
            fa = scores.get("ft_away")
            if fh is not None and fa is not None:
                return int(fh), int(fa)
    return None, None


# --------------------------------------------------------------------------------------
# Public: Bet365 API (event live/fast; result; prematch odds)
# --------------------------------------------------------------------------------------
def get_event_score_fast(fi: int) -> Dict[str, Optional[int | str]]:
    """
    Bet365 'fast' endpoint for a single event:
      - time_status: "0" not started, "1" live, "3" finished
      - SS/ss: scoreboard "H-A" (string)
    Returns: {"final_home": int|None, "final_away": int|None, "time_status": str|None}
    """
    results = _get_results(f"{BET365_V1}/event", FI=fi)
    if not results:
        return {"final_home": None, "final_away": None, "time_status": None}

    # depth-first walk through any nested dict/list to find SS and time_status
    def walk(x):
        if isinstance(x, dict):
            yield x
            for v in x.values():
                yield from walk(v)
        elif isinstance(x, list):
            for v in x:
                yield from walk(v)

    best_ts = None
    for node in walk(results):
        if not isinstance(node, dict):
            continue
        ts = node.get("time_status") or node.get("timeStatus") or node.get("time_status_id")
        if ts is not None and best_ts is None:
            best_ts = str(ts)

        ss = node.get("SS") or node.get("ss")
        if isinstance(ss, str) and "-" in ss:
            try:
                h, a = ss.split("-", 1)
                return {"final_home": int(h), "final_away": int(a), "time_status": str(ts) if ts is not None else best_ts}
            except Exception:
                # keep scanning
                pass

    return {"final_home": None, "final_away": None, "time_status": best_ts}


def get_event_result(fi: int) -> Dict[str, Optional[int]]:
    """
    Bet365 result endpoint (historical results if your key has access).
    Returns {"final_home": int|None, "final_away": int|None}
    """
    results = _get_results(f"{BET365_V1}/result", FI=fi)
    if not results:
        return {"final_home": None, "final_away": None}

    row = results[0]
    ss = row.get("SS") or row.get("ss")
    fh = fa = None
    if isinstance(ss, str) and "-" in ss:
        a, b = ss.split("-", 1)
        try:
            fh, fa = int(a), int(b)
        except ValueError:
            fh = fa = None

    # Some responses also include explicit scores fields
    if fh is None or fa is None:
        scores = row.get("scores") or {}
        ft_home = scores.get("ft_home")
        ft_away = scores.get("ft_away")
        if ft_home is not None and ft_away is not None:
            fh, fa = int(ft_home), int(ft_away)

    return {"final_home": fh, "final_away": fa}


def get_odds_openers(fi: int) -> Dict[str, Any]:
    """
    Prematch odds (v3) — parse 'game_lines' and return a flat shape compatible with your scripts:
      {"spread": float|None, "total": float|None, "opened_at_utc": str}
    """
    import re

    def _coerce_total_str(x: Any) -> Optional[float]:
        # Handles 'O 106.5', 'U106.5', '106.5', etc.
        if x is None:
            return None
        s = str(x).strip()
        s = re.sub(r'^[oOuU]\s*', '', s)   # drop leading O/U
        s = s.replace('+', '')
        m = re.search(r'-?\d+(\.\d+)?', s)
        return float(m.group(0)) if m else None

    def _coerce_number(x: Any) -> Optional[float]:
        if isinstance(x, (int, float)):
            return float(x)
        if x is None:
            return None
        try:
            return float(str(x).replace('+', '').strip())
        except Exception:
            return None

    r = requests.get(PREMATCH_V3, params={"token": TOKEN, "FI": fi}, timeout=DEFAULT_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    results = data.get("results") or []
    if not results:
        return {"spread": None, "total": None, "opened_at_utc": ""}

    row = results[0]
    main = row.get("main") or {}
    updated_at = main.get("updated_at") or row.get("update_time") or row.get("last_update") or ""
    opened_at_utc = _normalize_time(updated_at)

    sp = (main.get("sp") or {})
    gl = (sp.get("game_lines") or {})
    odds_list = gl.get("odds")

    if not isinstance(odds_list, list):
        return {"spread": None, "total": None, "opened_at_utc": opened_at_utc}

    spread_vals: List[float] = []
    total_vals:  List[float] = []

    for o in odds_list:
        if not isinstance(o, dict):
            continue

        name   = str(o.get("name")   or "").strip().lower()
        header = str(o.get("header") or "").strip().lower()
        itype  = str(o.get("type")   or "").strip().lower()
        title  = str(o.get("title")  or "").strip().lower()

        hcap  = o.get("handicap")
        hdp   = o.get("hdp")
        line  = o.get("line")
        total = o.get("total")
        if isinstance(hcap, dict):
            hcap = hcap.get("handicap") or hcap.get("points") or hcap.get("line")
        if isinstance(line, dict):
            line = line.get("handicap") or line.get("points") or line.get("line")
        if isinstance(total, dict):
            total = total.get("handicap") or total.get("points") or total.get("line")

        # --- SPREAD detection ---
        if (
            "spread" in (name + header + itype + title)
            or "handicap" in (name + header + itype + title)
        ):
            num = (_coerce_number(hcap) or _coerce_number(hdp) or _coerce_number(line))
            if num is not None:
                spread_vals.append(abs(num))  # store magnitude for margin closeness

        # --- TOTAL detection ---
        if (
            "total" in (name + header + itype + title)
            or "over" in name or "under" in name or "o/u" in name or "o/u" in header
        ):
            tnum = (_coerce_number(total) or _coerce_number(line) or
                    _coerce_total_str(o.get("handicap")) or _coerce_total_str(hcap))
            if tnum is not None:
                total_vals.append(float(tnum))

    spread_line = float(min(spread_vals)) if spread_vals else None
    total_line  = float(min(total_vals))  if total_vals  else None

    return {
        "spread": spread_line,
        "total": total_line,
        "opened_at_utc": opened_at_utc,
    }
