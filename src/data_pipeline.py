import os
import glob
import json
import pandas as pd
import warnings

warnings.filterwarnings("ignore")

JSON_FOLDER = "data/raw/t20s_male_json/"
OUT_RAW     = "data/processed/all_matches.csv"
OUT_CLEAN   = "data/processed/all_matches_clean.csv"

# glob finds every .json file in the folder
all_files = glob.glob(os.path.join(JSON_FOLDER, "*.json"))


def process_match(file_path):

    # --- Load the JSON ---
    with open(file_path) as f:
        match = json.load(f)

    # --- Extract match-level info (same for every over in this match) ---
    match_id = os.path.basename(file_path).replace(".json", "")
    venue    = match["info"].get("venue", "unknown")
    season   = match["info"].get("season", "unknown")

    outcome = match["info"]["outcome"]
    winner  = outcome.get("winner")

    # ties/no-results have no winner, cant label either team as won/lost,
    # so just skip the match
    if winner is None:
        return None

    toss_winner   = match["info"]["toss"]["winner"]
    toss_decision = match["info"]["toss"]["decision"]

    # --- Build ball-by-ball rows ---
    ball_rows = []

    for innings_index, innings in enumerate(match["innings"], start=1):
        batting_team = innings["team"]

        # Target only exists in 2nd innings
        target = innings.get("target", {}).get("runs", None)

        # Did batting team win the toss and choose to bat?
        toss_winner_batting = 1 if (
            toss_winner == batting_team and toss_decision == "bat"
        ) else 0

        for over in innings["overs"]:
            over_number = over["over"]

            for delivery in over["deliveries"]:
                extras  = delivery.get("extras", {})
                wickets = delivery.get("wickets", [])

                ball_rows.append({
                    "match_id"           : match_id,
                    "innings"            : innings_index,
                    "batting_team"       : batting_team,
                    "over"               : over_number,
                    "runs_off_bat"       : delivery["runs"]["batter"],
                    "total_runs"         : delivery["runs"]["total"],
                    "is_wicket"          : 1 if wickets else 0,
                    "is_wide"            : 1 if "wides" in extras else 0,
                    "is_noball"          : 1 if "noballs" in extras else 0,
                    "is_dot"             : 1 if (delivery["runs"]["total"] == 0 and "wides" not in extras) else 0,
                    "is_four"            : 1 if delivery["runs"]["batter"] == 4 else 0,
                    "is_six"             : 1 if delivery["runs"]["batter"] == 6 else 0,
                    # match-level context (repeated per ball, needed later)
                    "target"             : target,
                    "winner"             : winner,
                    "venue"              : venue,
                    "season"             : season,
                    "toss_winner_batting": toss_winner_batting,
                })

    ball_df = pd.DataFrame(ball_rows)

    # --- Aggregate to over level ---
    over_df = ball_df.groupby(["match_id", "innings", "batting_team", "over"]).agg(
        runs_per_over      = ("total_runs",   "sum"),
        intent_runs        = ("runs_off_bat", "sum"),
        dot_balls          = ("is_dot",       "sum"),
        wides              = ("is_wide",      "sum"),
        noballs            = ("is_noball",    "sum"),
        wickets            = ("is_wicket",    "sum"),
        fours              = ("is_four",      "sum"),
        sixes              = ("is_six",       "sum"),
        # same value on every row, just take the first
        target             = ("target",       "first"),
        winner             = ("winner",       "first"),
        venue              = ("venue",        "first"),
        season             = ("season",       "first"),
        toss_winner_batting= ("toss_winner_batting", "first"),
    ).reset_index()

    return over_df


def build_master_df():
    all_dfs = []   # one DataFrame per match
    errors  = []   # any files that fail or get skipped
    skipped = 0

    for file_path in all_files:
        try:
            df = process_match(file_path)
            if df is None:
                skipped += 1
                continue
            all_dfs.append(df)
        except Exception as e:
            errors.append({"file": file_path, "error": str(e)})

    print(f"\n Success: {len(all_dfs)} matches")
    print(f" Skipped (no result): {skipped} matches")
    print(f" Errors:  {len(errors)} matches")

    master_df = pd.concat(all_dfs, ignore_index=True)

    print(f"Total rows: {master_df.shape[0]}")
    print(f"Total columns: {master_df.shape[1]}")
    print(f"Unique matches: {master_df['match_id'].nunique()}")

    # gotta sort first or the cumsum below breaks
    master_df = master_df.sort_values(["match_id", "innings", "over"]).reset_index(drop=True)

    # --- Cumulative stats per innings per match ---
    g = master_df.groupby(["match_id", "innings"])

    master_df["cum_runs"]       = g["runs_per_over"].cumsum()
    master_df["wickets_fallen"] = g["wickets"].cumsum()
    master_df["wickets_in_hand"] = 10 - master_df["wickets_fallen"]

    # --- Run rates ---
    master_df["crr"] = master_df["cum_runs"] / (master_df["over"] + 1)

    # required run rate only makes sense in the 2nd innings
    mask = (master_df["innings"] == 2) & (master_df["target"].notna())
    master_df["overs_left"] = 20 - master_df["over"]
    master_df.loc[mask, "rrr"] = (
        (master_df.loc[mask, "target"] - master_df.loc[mask, "cum_runs"]) /
        master_df.loc[mask, "overs_left"].clip(lower=1)
    )
    master_df["crr_vs_rrr"] = master_df["crr"] - master_df["rrr"]

    # --- Phase ---
    def phase(over):
        if over <= 5:    return "powerplay"
        elif over <= 15: return "middle"
        else:            return "death"

    master_df["phase"] = master_df["over"].apply(phase)

    # --- Momentum (3-over rolling run rate) ---
    master_df["momentum"] = (
        master_df.groupby(["match_id", "innings"])["runs_per_over"]
        .transform(lambda x: x.rolling(3, min_periods=1).mean())
    )

    # --- Boundary rate ---
    master_df["boundary_rate"] = (master_df["fours"] + master_df["sixes"]) / 6

    # --- Legal balls ---
    master_df["legal_balls"] = 6 - master_df["wides"]

    # --- YOUR TARGET LABEL ---
    master_df["batting_team_won"] = (
        master_df["batting_team"] == master_df["winner"]
    ).astype(int)

    return master_df


if __name__ == "__main__":
    master_df = build_master_df()

    os.makedirs(os.path.dirname(OUT_RAW), exist_ok=True)
    master_df.to_csv(OUT_RAW, index=False)

    df = master_df.copy()
    df["rrr"]        = df["rrr"].fillna(0)
    df["crr_vs_rrr"] = df["crr_vs_rrr"].fillna(0)
    df["target"]     = df["target"].fillna(0)
    df = df[df["innings"].isin([1, 2])].reset_index(drop=True)

    df.to_csv(OUT_CLEAN, index=False)
    print("Clean CSV saved!", df.shape)
