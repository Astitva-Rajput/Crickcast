import json
import os
from functools import lru_cache

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH   = os.path.join(BASE_DIR, "data", "processed", "all_matches_clean.csv")
RAW_DIR    = os.path.join(BASE_DIR, "data", "raw", "t20s_male_json")
MODEL_PATH = os.path.join(BASE_DIR, "models", "win_probability.pkl")

app = FastAPI(title="CrickCast win-probability API")

# no auth on this api, cors just wide open
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

bundle   = joblib.load(MODEL_PATH)
MODEL    = bundle["model"]
FEATURES = bundle["features"]

overs_df = pd.read_csv(CSV_PATH)

# one match in the dataset only has one innings on record, probably a
# washout that still got a result somehow. cant replay that properly so
# just drop it from the list
_innings_count = overs_df.groupby("match_id")["innings"].nunique()
VALID_MATCH_IDS = set(_innings_count[_innings_count == 2].index)


# reads the raw ball-by-ball json so the replay can show each over's
# actual balls (4, 1, W, dot...) not just the over total
def build_ball_ticker(match_id):
    path = os.path.join(RAW_DIR, f"{match_id}.json")
    if not os.path.exists(path):
        return {}

    with open(path) as f:
        match = json.load(f)

    ticker = {}
    for innings_index, innings in enumerate(match["innings"], start=1):
        for over in innings["overs"]:
            balls = []
            for delivery in over["deliveries"]:
                extras  = delivery.get("extras", {})
                wickets = delivery.get("wickets", [])
                if wickets:
                    balls.append("W")
                elif "wides" in extras:
                    balls.append("wd")
                elif "noballs" in extras:
                    balls.append("nb")
                else:
                    balls.append(str(delivery["runs"]["total"]))
            ticker[(innings_index, over["over"])] = balls

    return ticker


@lru_cache(maxsize=1)
def match_catalog():
    rows = []
    for match_id, group in overs_df[overs_df["match_id"].isin(VALID_MATCH_IDS)].groupby("match_id"):
        inn1 = group[group["innings"] == 1]
        inn2 = group[group["innings"] == 2]
        if inn1.empty or inn2.empty:
            continue

        rows.append({
            "match_id": int(match_id),
            "team1"   : inn1["batting_team"].iloc[0],
            "team2"   : inn2["batting_team"].iloc[0],
            "venue"   : inn1["venue"].iloc[0],
            "season"  : str(inn1["season"].iloc[0]),
            "winner"  : inn1["winner"].iloc[0],
        })

    rows.sort(key=lambda r: r["season"], reverse=True)
    return rows


@app.get("/api/matches")
def list_matches():
    return match_catalog()


@app.get("/api/matches/{match_id}/replay")
def replay(match_id: int):
    if match_id not in VALID_MATCH_IDS:
        raise HTTPException(status_code=404, detail="match not found")

    match_df = overs_df[overs_df["match_id"] == match_id].sort_values(["innings", "over"]).copy()

    # probabilities aren't precomputed anywhere, model runs right here
    # when the match is requested
    match_df["win_prob_batting_team"] = MODEL.predict_proba(match_df[FEATURES])[:, 1]

    ticker = build_ball_ticker(match_id)

    overs = []
    for _, row in match_df.iterrows():
        overs.append({
            "innings"             : int(row["innings"]),
            "over"                : int(row["over"]),
            "batting_team"        : row["batting_team"],
            "runs_per_over"       : int(row["runs_per_over"]),
            "cum_runs"            : int(row["cum_runs"]),
            "wickets_in_hand"     : int(row["wickets_in_hand"]),
            "wickets_fallen"      : int(row["wickets_fallen"]),
            "target"              : None if row["target"] == 0 else int(row["target"]),
            "crr"                 : round(float(row["crr"]), 2),
            "rrr"                 : None if row["rrr"] == 0 and row["innings"] == 1 else round(float(row["rrr"]), 2),
            "phase"               : row["phase"],
            "fours"               : int(row["fours"]),
            "sixes"               : int(row["sixes"]),
            "win_prob_batting_team": round(float(row["win_prob_batting_team"]), 4),
            "balls"               : ticker.get((int(row["innings"]), int(row["over"])), []),
        })

    inn1 = match_df[match_df["innings"] == 1].iloc[0]
    inn2 = match_df[match_df["innings"] == 2].iloc[0]

    return {
        "match_id": match_id,
        "venue"   : inn1["venue"],
        "season"  : str(inn1["season"]),
        "team1"   : inn1["batting_team"],
        "team2"   : inn2["batting_team"],
        "winner"  : inn1["winner"],
        "target"  : int(inn2["target"]) if inn2["target"] else None,
        "overs"   : overs,
    }


@app.get("/api/health")
def health():
    return {"status": "ok", "matches_loaded": len(VALID_MATCH_IDS)}
