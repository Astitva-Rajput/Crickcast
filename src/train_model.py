import json
import warnings

import pandas as pd
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import GroupKFold, GroupShuffleSplit, cross_val_predict
from xgboost import XGBClassifier
import joblib

warnings.filterwarnings("ignore")

DATA_PATH  = "data/processed/all_matches_clean.csv"
MODEL_OUT  = "models/win_probability.pkl"
REPORT_OUT = "models/model_comparison.json"

FEATURES = [
    "innings",
    "over",
    "cum_runs",
    "wickets_in_hand",
    "crr",
    "rrr",
    "crr_vs_rrr",
    "momentum",
    "boundary_rate",
    "dot_balls",
    "toss_winner_batting",
]

TARGET = "batting_team_won"


def load_data():
    df = pd.read_csv(DATA_PATH)
    return df, df[FEATURES], df[TARGET], df["match_id"]


# old notebook used a random 80/20 split, which let overs from the same
# match land on both sides - basically letting the model peek. grouping by
# match_id below fixes that. accuracy drops a bit after this, that's just
# the leak going away
def bakeoff(X, y, groups):
    candidates = {
        "logistic_regression": LogisticRegression(max_iter=1000),
        "random_forest": RandomForestClassifier(
            n_estimators=300, max_depth=12, min_samples_leaf=10,
            random_state=42, n_jobs=-1,
        ),
        # sklearn's built-in gradient boosting, same idea as lightgbm,
        # no extra dependency needed
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            max_iter=300, max_depth=6, learning_rate=0.08, random_state=42,
        ),
        "xgboost": XGBClassifier(
            n_estimators=300, max_depth=6, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            random_state=42, n_jobs=-1, verbosity=0,
        ),
    }

    gkf = GroupKFold(n_splits=5)
    rows = []

    for name, model in candidates.items():
        oof_proba = cross_val_predict(
            model, X, y, groups=groups, cv=gkf,
            method="predict_proba", n_jobs=-1,
        )[:, 1]
        oof_pred = (oof_proba >= 0.5).astype(int)

        rows.append({
            "model"    : name,
            "accuracy" : round(accuracy_score(y, oof_pred), 4),
            "log_loss" : round(log_loss(y, oof_proba), 4),
            "brier"    : round(brier_score_loss(y, oof_proba), 4),
            "roc_auc"  : round(roc_auc_score(y, oof_proba), 4),
        })
        print(f"{name:24s} logloss={rows[-1]['log_loss']}  brier={rows[-1]['brier']}  "
              f"auc={rows[-1]['roc_auc']}  acc={rows[-1]['accuracy']}")

    return candidates, pd.DataFrame(rows).sort_values("log_loss").reset_index(drop=True)


if __name__ == "__main__":
    df, X, y, groups = load_data()
    print(f"Rows: {len(df)}   Matches: {groups.nunique()}")

    print("\n5-fold grouped CV (out-of-fold predictions, no leakage across matches):")
    candidates, results = bakeoff(X, y, groups)
    print("\n", results)

    winner_name = results.iloc[0]["model"]
    print(f"\nBest by log loss: {winner_name}")

    # separate holdout just to sanity check the winner on data it hasn't
    # seen at all, mostly for the writeup/plots
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_idx, test_idx = next(splitter.split(X, y, groups=groups))
    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
    groups_train = groups.iloc[train_idx]

    base_model = clone(candidates[winner_name])

    # raw xgboost scores are fine for ranking but not real probabilities,
    # calibrating so "73%" on the chart actually means 73%
    calibrated = CalibratedClassifierCV(base_model, method="isotonic", cv=5)
    calibrated.fit(X_train, y_train)

    raw = clone(candidates[winner_name])
    raw.fit(X_train, y_train)

    for tag, mdl in [("uncalibrated", raw), ("calibrated", calibrated)]:
        proba = mdl.predict_proba(X_test)[:, 1]
        print(f"holdout [{tag:12s}] logloss={log_loss(y_test, proba):.4f}  "
              f"brier={brier_score_loss(y_test, proba):.4f}")

    # refit on all the data for the version we actually ship, holdout
    # above already showed it generalizes fine
    final_model = CalibratedClassifierCV(clone(candidates[winner_name]), method="isotonic", cv=5)
    final_model.fit(X, y)

    joblib.dump({"model": final_model, "features": FEATURES}, MODEL_OUT)
    print(f"\nSaved {winner_name} (calibrated) to {MODEL_OUT}")

    with open(REPORT_OUT, "w") as f:
        json.dump({
            "cv_results": results.to_dict(orient="records"),
            "winner": winner_name,
            "features": FEATURES,
            "rows": len(df),
            "matches": int(groups.nunique()),
        }, f, indent=2)
    print(f"Saved comparison report to {REPORT_OUT}")
