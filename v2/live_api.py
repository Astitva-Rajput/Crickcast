import os
import time
import threading

import joblib
import pandas as pd
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# one model per format, same 9 features. a t20 model can't score odi states,
# over 35 is outside anything it trained on and its rrr assumes 20 overs
MODEL_PATHS = {
    "t20": os.path.join(BASE_DIR, "models", "win_probability_live.pkl"),
    "odi": os.path.join(BASE_DIR, "models", "win_probability_odi.pkl"),
}
FORMAT_OVERS = {"t20": 20, "odi": 50}

API_BASE = "https://api.cricapi.com/v1"
API_KEY  = os.environ.get("CRICKETDATA_API_KEY", "")

# free tier is 100 hits/day. one match polled every 2 min for ~3.5h is ~105
# hits, so 150s keeps a full t20 comfortably inside the budget with room
# for the match-list calls around it
POLL_SECONDS = 150

app = FastAPI(title="CrickCast live API (v2)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BUNDLES = {fmt: joblib.load(path) for fmt, path in MODEL_PATHS.items()}


def api_get(path, **params):
    params["apikey"] = API_KEY
    r = requests.get(f"{API_BASE}/{path}", params=params, timeout=15)
    r.raise_for_status()
    payload = r.json()
    if payload.get("status") != "success":
        raise RuntimeError(f"cricketdata.org error: {payload.get('reason', 'unknown')}")
    return payload["data"]


# cricketdata gives overs as a decimal like 18.2 meaning 18 overs 2 balls,
# not 18.2 overs
def parse_overs(o):
    whole = int(o)
    balls = round((o - whole) * 10)
    return whole, balls


# polls one match and grows the same over-by-over probability curve the
# replay endpoint produces, from score summaries alone
class LiveMatch:

    def __init__(self, match_id):
        self.match_id = match_id
        self.info = {}
        self.curve = []          # over-level points, same shape the frontend already reads
        self.last_poll = 0.0
        self.last_success = 0.0
        self.done = False
        self.error = None
        self.toss_winner = ""
        self.toss_choice = ""
        self.batting_first = ""
        self.format = None       # "t20" or "odi", detected on first poll
        self.lock = threading.Lock()

    def poll(self):
        # respect the budget no matter how often the frontend asks - only
        # the very first call (last_poll still 0) is allowed through early
        polled_recently = self.last_poll > 0 and (time.time() - self.last_poll) < POLL_SECONDS
        if polled_recently:
            return
        self.last_poll = time.time()

        m = api_get("match_info", id=self.match_id)
        self.last_success = time.time()
        self.error = None
        self.info = {
            "name"  : m.get("name", ""),
            "venue" : m.get("venue", ""),
            "status": m.get("status", ""),
            "teams" : m.get("teams", []),
        }
        self.done = m.get("matchEnded", False)

        if self.format is None:
            # matchType is sometimes missing and sometimes present-but-null,
            # so "or" catches both instead of just the missing case .get()'s
            # default would
            mt = (m.get("matchType") or "").lower()
            name = (m.get("name") or "").lower()
            self.format = mt if mt in FORMAT_OVERS else ("odi" if "odi" in name else "t20")
        self.toss_winner = (m.get("tossWinner") or "").lower()
        self.toss_choice = (m.get("tossChoice") or "").lower()

        # batting side of innings 1 is whichever team's name leads the first
        # score entry's label - innings 2 is the other one
        score = m.get("score", [])
        if score and not self.batting_first:
            label = (score[0].get("inning") or "").lower()
            for team in m.get("teams", []):
                if label.startswith(team.lower()):
                    self.batting_first = team.lower()
                    break

        for innings_index, s in enumerate(m.get("score", []), start=1):
            overs_done, _ = parse_overs(s.get("o", 0))
            self._advance(innings_index, overs_done, s.get("r", 0), s.get("w", 0),
                          target=self._target(m, innings_index))

    def _target(self, m, innings_index):
        if innings_index != 2:
            return None
        score = m.get("score", [])
        return score[0]["r"] + 1 if score else None

    # one curve point per completed over we haven't seen yet. if several
    # overs passed between polls the in-between ones get interpolated
    def _advance(self, innings, overs_done, runs, wickets, target=None):
        with self.lock:
            seen = [p for p in self.curve if p["innings"] == innings]
            last_over = seen[-1]["over"] + 1 if seen else 0
            prev_runs = seen[-1]["cum_runs"] if seen else 0
            prev_wkts = seen[-1]["wickets_fallen"] if seen else 0

            for n in range(last_over + 1, overs_done + 1):
                frac = (n - last_over) / max(overs_done - last_over, 1)
                cum_runs = round(prev_runs + (runs - prev_runs) * frac)
                cum_wkts = round(prev_wkts + (wickets - prev_wkts) * frac)
                self._append_point(innings, n - 1, cum_runs, cum_wkts, target=target)

    def _append_point(self, innings, over, cum_runs, wickets_fallen, target=None):
        # same formulas as the pipelines so the model sees what it trained on
        total_overs = FORMAT_OVERS[self.format]
        crr = cum_runs / (over + 1)
        rrr = None
        if innings == 2 and target:
            overs_left = max(total_overs - over, 1)
            rrr = (target - cum_runs) / overs_left

        recent = [p for p in self.curve if p["innings"] == innings][-2:]
        window = [p["runs_per_over"] for p in recent]
        this_over = cum_runs - (recent[-1]["cum_runs"] if recent else 0)
        window.append(this_over)
        momentum = sum(window) / len(window)

        row = {
            "innings"            : innings,
            "over"               : over,
            "cum_runs"           : cum_runs,
            "wickets_in_hand"    : 10 - wickets_fallen,
            "crr"                : crr,
            "rrr"                : rrr if rrr is not None else 0,
            "crr_vs_rrr"         : (crr - rrr) if rrr is not None else 0,
            "momentum"           : momentum,
            "toss_winner_batting": self.toss_winner_batting(innings),
        }
        bundle = BUNDLES[self.format]
        proba = bundle["model"].predict_proba(pd.DataFrame([row])[bundle["features"]])[0, 1]

        self.curve.append({
            "innings"              : innings,
            "over"                 : over,
            "cum_runs"             : cum_runs,
            "wickets_fallen"       : wickets_fallen,
            "wickets_in_hand"      : 10 - wickets_fallen,
            "runs_per_over"        : this_over,
            "crr"                  : round(crr, 2),
            "rrr"                  : round(rrr, 2) if rrr is not None else None,
            "win_prob_batting_team": round(float(proba), 4),
        })

    def toss_winner_batting(self, innings):
        # same definition as data_pipeline.py: did this innings' batting team
        # win the toss and choose to bat. match_info gives tossWinner and
        # tossChoice, batting_first is worked out from the score labels
        if not self.toss_winner or not self.batting_first:
            return 0
        if innings == 1:
            batting = self.batting_first
        else:
            others = [t.lower() for t in self.info.get("teams", []) if t.lower() != self.batting_first]
            batting = others[0] if others else ""
        return 1 if (batting == self.toss_winner and self.toss_choice == "bat") else 0


TRACKED = {}


@app.get("/api/live/matches")
def live_matches():
    if not API_KEY:
        raise HTTPException(status_code=500, detail="CRICKETDATA_API_KEY not set")
    try:
        matches = api_get("currentMatches", offset=0)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"couldn't reach cricketdata.org: {e}")

    out = []
    for m in matches:
        # one odd entry from cricketdata.org shouldn't take the whole list
        # down - skip it and keep going instead of crashing the request
        try:
            if not m.get("id"):
                continue
            mt = (m.get("matchType") or "").lower()
            name = (m.get("name") or "").lower()
            fmt = mt if mt in FORMAT_OVERS else ("odi" if "odi" in name else None)
            if fmt is None:
                continue
            if not m.get("matchStarted") or m.get("matchEnded"):
                continue
            out.append({
                "id"    : m["id"],
                "name"  : m.get("name", ""),
                "format": fmt,
                "venue" : m.get("venue", ""),
                "teams" : m.get("teams", []),
                "status": m.get("status", ""),
            })
        except Exception:
            continue

    return out


@app.get("/api/live/{match_id}")
def live_curve(match_id: str):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="CRICKETDATA_API_KEY not set")

    tracker = TRACKED.setdefault(match_id, LiveMatch(match_id))
    try:
        tracker.poll()
    except Exception as e:
        tracker.error = str(e)
        if not tracker.curve:
            raise HTTPException(status_code=502, detail=f"couldn't reach cricketdata.org: {e}")

    # team1 = whoever batted first, keeps the frontend's scoreboard/chart
    # conventions identical to the replay payload
    teams = tracker.info.get("teams", [])
    team1 = next((t for t in teams if t.lower() == tracker.batting_first), teams[0] if teams else "")
    team2 = next((t for t in teams if t != team1), "")

    stale_seconds = int(time.time() - tracker.last_success) if tracker.last_success else None

    return {
        "match_id"    : match_id,
        "format"      : tracker.format,
        "total_overs" : FORMAT_OVERS.get(tracker.format),
        "team1"       : team1,
        "team2"       : team2,
        "info"        : tracker.info,
        "done"        : tracker.done,
        "overs"       : tracker.curve,
        "next_poll_in": max(0, int(POLL_SECONDS - (time.time() - tracker.last_poll))),
        # non-null only when the most recent poll failed but we still have
        # older data to show instead of a blank screen
        "error"        : tracker.error,
        "stale_seconds": stale_seconds,
    }


@app.get("/api/live-health")
def health():
    return {"status": "ok", "tracking": len(TRACKED), "key_set": bool(API_KEY)}
