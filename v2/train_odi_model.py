import json
import warnings

import pandas as pd
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import GroupKFold, cross_val_predict
from xgboost import XGBClassifier
import joblib

warnings.filterwarnings("ignore")

# odi twin of train_live_model.py - same 9 live-compatible features, the
# format difference lives in the data (50-over rrr, odi scoring patterns)
DATA_PATH  = "data/processed/odi_matches_clean.csv"
MODEL_OUT  = "models/win_probability_odi.pkl"
REPORT_OUT = "models/model_comparison_odi.json"

FEATURES = [
    "innings",
    "over",
    "cum_runs",
    "wickets_in_hand",
    "crr",
    "rrr",
    "crr_vs_rrr",
    "momentum",
    "toss_winner_batting",
]

TARGET = "batting_team_won"


def load_data():
    df = pd.read_csv(DATA_PATH)
    return df, df[FEATURES], df[TARGET], df["match_id"]


def bakeoff(X, y, groups):
    candidates = {
        "logistic_regression": LogisticRegression(max_iter=1000),
        "random_forest": RandomForestClassifier(
            n_estimators=300, max_depth=12, min_samples_leaf=10,
            random_state=42, n_jobs=-1,
        ),
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
    print(f"Rows: {len(df)}   Matches: {groups.nunique()}   Features: {FEATURES}")

    print("\n5-fold grouped CV (odi, live-compatible feature set):")
    candidates, results = bakeoff(X, y, groups)
    print("\n", results)

    # keeping xgboost across all three models (v1 t20, live t20, odi) unless
    # something actually beats it by a real margin, same reasoning as before
    winner_name = "xgboost"
    print(f"\nBest by log loss: {results.iloc[0]['model']} (shipping {winner_name})")

    calibrated = CalibratedClassifierCV(clone(candidates[winner_name]), method="isotonic", cv=5)
    calibrated.fit(X, y)

    joblib.dump({"model": calibrated, "features": FEATURES}, MODEL_OUT)
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
