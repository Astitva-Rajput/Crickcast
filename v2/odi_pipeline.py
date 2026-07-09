import os
import glob
import json
import pandas as pd
import warnings

warnings.filterwarnings("ignore")

# same shape as src/data_pipeline.py, redone for 50-over cricket. the raw
# odi dump is training-only (nothing reads it at runtime) so it stays
# gitignored, and this script regenerates the csv from it when needed
JSON_FOLDER = "data/raw/odis_male_json/"
OUT_CLEAN   = "data/processed/odi_matches_clean.csv"

TOTAL_OVERS = 50

all_files = glob.glob(os.path.join(JSON_FOLDER, "*.json"))


def process_match(file_path):

    with open(file_path) as f:
        match = json.load(f)

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

    ball_rows = []

    for innings_index, innings in enumerate(match["innings"], start=1):
        batting_team = innings["team"]

        target = innings.get("target", {}).get("runs", None)

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
                    "total_runs"         : delivery["runs"]["total"],
                    "is_wicket"          : 1 if wickets else 0,
                    "target"             : target,
                    "winner"             : winner,
                    "venue"              : venue,
                    "season"             : season,
                    "toss_winner_batting": toss_winner_batting,
                })

    ball_df = pd.DataFrame(ball_rows)

    over_df = ball_df.groupby(["match_id", "innings", "batting_team", "over"]).agg(
        runs_per_over      = ("total_runs", "sum"),
        wickets            = ("is_wicket",  "sum"),
        # same value on every row, just take the first
        target             = ("target",     "first"),
        winner             = ("winner",     "first"),
        venue              = ("venue",      "first"),
        season             = ("season",     "first"),
        toss_winner_batting= ("toss_winner_batting", "first"),
    ).reset_index()

    return over_df


def build_master_df():
    all_dfs = []
    errors  = []
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

    # gotta sort first or the cumsum below breaks
    master_df = master_df.sort_values(["match_id", "innings", "over"]).reset_index(drop=True)

    g = master_df.groupby(["match_id", "innings"])

    master_df["cum_runs"]        = g["runs_per_over"].cumsum()
    master_df["wickets_fallen"]  = g["wickets"].cumsum()
    master_df["wickets_in_hand"] = 10 - master_df["wickets_fallen"]

    master_df["crr"] = master_df["cum_runs"] / (master_df["over"] + 1)

    # required run rate only makes sense in the 2nd innings
    mask = (master_df["innings"] == 2) & (master_df["target"].notna())
    master_df["overs_left"] = TOTAL_OVERS - master_df["over"]
    master_df.loc[mask, "rrr"] = (
        (master_df.loc[mask, "target"] - master_df.loc[mask, "cum_runs"]) /
        master_df.loc[mask, "overs_left"].clip(lower=1)
    )
    master_df["crr_vs_rrr"] = master_df["crr"] - master_df["rrr"]

    master_df["momentum"] = (
        master_df.groupby(["match_id", "innings"])["runs_per_over"]
        .transform(lambda x: x.rolling(3, min_periods=1).mean())
    )

    master_df["batting_team_won"] = (
        master_df["batting_team"] == master_df["winner"]
    ).astype(int)

    return master_df


if __name__ == "__main__":
    master_df = build_master_df()

    df = master_df.copy()
    df["rrr"]        = df["rrr"].fillna(0)
    df["crr_vs_rrr"] = df["crr_vs_rrr"].fillna(0)
    df["target"]     = df["target"].fillna(0)
    df = df[df["innings"].isin([1, 2])].reset_index(drop=True)

    os.makedirs(os.path.dirname(OUT_CLEAN), exist_ok=True)
    df.to_csv(OUT_CLEAN, index=False)
    print("Clean ODI CSV saved!", df.shape)
