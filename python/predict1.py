# python/predict.py
import sqlite3
import pandas as pd
import numpy as np
import joblib
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'ligue1.db')
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'ligue1_model.pkl')

def predict_upcoming():
    model = joblib.load(MODEL_PATH)
    rf_home = model['rf_home']
    rf_away = model['rf_away']

    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM matches WHERE home_score IS NULL", conn)
    conn.close()

    if len(df) == 0:
        print("[]")  # pas de match à venir
        return

    df['home_team_id'] = df['home_team'].astype('category').cat.codes
    df['away_team_id'] = df['away_team'].astype('category').cat.codes

    X = df[['home_team_id','away_team_id']].values
    home_pred = rf_home.predict(X)
    away_pred = rf_away.predict(X)

    # Crée un petit dict
    results = []
    for i, row in df.iterrows():
        results.append({
            "fixture_id": row['fixture_id'],
            "date": row['date'],
            "home_team": row['home_team'],
            "away_team": row['away_team'],
            "home_pred": float(home_pred[i]),
            "away_pred": float(away_pred[i])
        })

    import json
    print(json.dumps(results))

if __name__ == "__main__":
    predict_upcoming()
