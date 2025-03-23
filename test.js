import sqlite3
from flask import Flask, request, jsonify
import requests
import json
import pandas as pd
import time
import joblib
import os

app = Flask(__name__)

# Configuration pour l'API RapidAPI-Football
API_KEY = "c16a3bd85cmsh57c4e77612f35fep1b54b0jsnc50c626d3ff5"  # Remplacez par votre clé
RAPIDAPI_HOST = "v3.football.api-sports.io"   # Hôte v3
LEAGUE_ID = 61    # Ligue 1
SEASON_YEAR = 2023  # Saison 2023 (adaptez si besoin)

# URL de base pour l'API-Football v3
BASE_URL = f"https://{RAPIDAPI_HOST}"

# Configuration pour SQLite
DATABASE = "ligue1.db"

############################################
# ROUTES EXISTANTES
############################################

@app.route('/', methods=['GET'])
def home():
    return jsonify({"message": "Application de pronostics Ligue 1"})

@app.route('/data', methods=['GET'])
def get_data():
    """
    Récupère des données depuis l'ancien endpoint (vous pouvez l'adapter ou le retirer).
    """
    try:
        # Exemple d'URL existant (vous n'utilisiez pas le v3)
        # Gardez ou modifiez selon vos besoins
        old_url = f"/v1/matches?apikey={API_KEY}&league_id=FR&season_year={SEASON_YEAR}"
        response = requests.get(old_url)
        if response.status_code == 200:
            data = json.loads(response.text)
            df = pd.DataFrame(data)
            prepared_df = prepare_data(df)
            return jsonify({
                "success": True,
                "data": prepared_df.to_dict('records')
            })
        else:
            return jsonify({"error": f"Erreur de récupération des données. Statut : {response.status_code}"})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/train', methods=['GET'])
def train_model_route():
    """
    Exécute un réentraînement du modèle (exemple existant).
    """
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM matches")
        data_history = pd.DataFrame(cursor.fetchall(), columns=[])

        # Cet ancien url n'utilise pas l'API-Football v3
        # Gardez ou adaptez
        old_url = f"/v1/matches?apikey={API_KEY}&league_id=FR&season_year={SEASON_YEAR}"
        response = requests.get(old_url)
        if response.status_code == 200:
            new_data = json.loads(response.text)
            df_new = pd.DataFrame(new_data)
            full_data = pd.concat([data_history, df_new])
            train_data, test_data = prepare_data(full_data)

            model = train_model(train_data.drop('date', axis=1), train_data['home_score'])
            joblib.dump(model, 'ligue1_model.pkl')

            return jsonify({"message": "Modèle réentraîné avec succès"})
        else:
            return jsonify({"error": f"Erreur lors de la requête. Statut : {response.status_code}"})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/predict', methods=['GET'])
def predict_scores_route():
    """
    Exemple de route de prédiction (existant).
    """
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM matches")
        data = pd.DataFrame(cursor.fetchall(), columns=['home_team', 'away_team', 'date', 'home_score', 'away_score'])
        if not data.empty:
            X_test = prepare_predict_data(data)
            model = joblib.load('ligue1_model.pkl')

            # Attention : vous aviez un predict_scores() function globale ?
            # => Renommez-le si besoin.
            home_pred, away_pred = predict_scores_ml(model, X_test)

            return jsonify({
                "home_pred": home_pred.round().astype(int).tolist(),
                "away_pred": away_pred.round().astype(int).tolist()
            })
        else:
            return jsonify({"error": "Pas de données disponibles pour prédiction"})
    except Exception as e:
        return jsonify({"error": str(e)})

def prepare_predict_data(data):
    """Prépare les données pour la prédiction."""
    recent_matches = data.sort_values('date').tail(5)
    home_avg_goals = recent_matches.groupby('home_team')['home_score'].mean()
    away_avg_goals = recent_matches.groupby('away_team')['away_score'].mean()

    X_test = pd.DataFrame({
        'home_avg_last_5': home_avg_goals,
        'away_avg_last_5': away_avg_goals
    })
    return X_test

def predict_scores_ml(model, X_test):
    """
    Exemple d'une fonction qui fait des prédictions
    (vous aviez "predict_scores()" => renommez pour éviter conflit).
    """
    # Ici, c'est fictif : scinder le modèle (rf_home, rf_away) ?
    # Ou un unique modèle ?
    # Adaptez selon votre pipeline.
    home_pred = model.predict(X_test)
    away_pred = model.predict(X_test)
    return home_pred, away_pred

def train_model(X_train, y_train):
    """Entraîne un modèle de régression."""
    # (Existant)
    model = joblib.load('ligue1_model.pkl')
    return model

def prepare_data(df):
    """Nettoie et prépare les données pour l'entrainement."""
    df = df.dropna()
    team_names = pd.unique(df['home_team'] + df['away_team'])
    for name in team_names:
        df.replace(name, 'Unknown', inplace=True)

    recent_matches = df.sort_values('date').tail(5)
    home_avg_goals = recent_matches.groupby('home_team')['home_score'].mean()
    away_avg_goals = recent_matches.groupby('away_team')['away_score'].mean()

    split_point = int(len(df) * 0.8)
    train_df = df.iloc[:split_point]
    test_df = df.iloc[split_point:]
    return train_df, test_df

@app.route('/new-data', methods=['GET'])
def get_new_data():
    """
    Ancienne route pour récupérer de nouvelles données.
    """
    try:
        old_url = f"/v1/matches?apikey={API_KEY}&league_id=FR&season_year={SEASON_YEAR}"
        response = requests.get(old_url)
        if response.status_code == 200:
            new_data = json.loads(response.text)
            df = pd.DataFrame(new_data)

            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            for idx, row in df.iterrows():
                cursor.execute(
                    "INSERT INTO matches (home_team, away_team, date, home_score, away_score) VALUES (?, ?, ?, ?, ?)",
                    (row['home_team'], row['away_team'], row['date'], row['home_score'], row['away_score'])
                )
            conn.commit()
            return jsonify({"message": "Nouvelles données enregistrées avec succès"})
        else:
            return jsonify({"error": f"Erreur lors de la requête. Statut : {response.status_code}"})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/model-status', methods=['GET'])
def get_model_status():
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM matches")
        data = pd.DataFrame(cursor.fetchall(), columns=['date'])
        last_update_date = data['date'].max()
        return jsonify({
            "last_update": last_update_date,
            "status": "OK"
        })
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/delete-old-data', methods=['GET'])
def delete_old_data():
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM matches")
        conn.commit()

        return jsonify({"message": "Données anciennes supprimées avec succès"})
    except Exception as e:
        return jsonify({"error": str(e)})

############################################
# NOUVELLES ROUTES "fixtures/rounds"
# SELON API-FOOTBALL v3
############################################

@app.route('/fetch-rounds', methods=['GET'])
def fetch_rounds():
    """
    Récupère la liste des "rounds" (journées) via l'endpoint
    /fixtures/rounds de l'API-Football (v3).
    Paramètre : ?current=true|false (optionnel).
    Ex: /fetch-rounds?current=true
    """
    current_param = request.args.get('current', 'false')
    # Ex: 'true' ou 'false'

    url_rounds = f"{BASE_URL}/fixtures/rounds"
    params = {
        "league": LEAGUE_ID,    # Ligue 1
        "season": SEASON_YEAR,  # 2023
        "current": current_param
    }
    headers = {
        "x-rapidapi-key": API_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST
    }

    try:
        r = requests.get(url_rounds, params=params, headers=headers)
        if r.status_code == 200:
            data = r.json()
            # data['response'] est un tableau de strings (ex: ["Regular Season - 1", "Regular Season - 2", ...])
            rounds = data.get('response', [])

            # Vous pouvez :
            # - Soit stocker ces rounds en base dans une table "rounds"
            # - Soit simplement les renvoyer en JSON

            return jsonify({
                "message": f"Fetched {len(rounds)} round(s) (current={current_param})",
                "rounds": rounds
            })
        else:
            return jsonify({"error": f"Erreur API-Football /fixtures/rounds status {r.status_code}"})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/fetch-matches-by-round', methods=['GET'])
def fetch_matches_by_round():
    """
    Récupère les matchs d'une journée précise via l'API-Football (v3),
    param ?round= ex: "Regular Season - 2"
    Ex: /fetch-matches-by-round?round=Regular Season - 2
    Puis insère dans la table 'matches'.
    """
    round_name = request.args.get('round')
    if not round_name:
        return jsonify({"error": "Param ?round=... manquant (ex: 'Regular Season - 2')"})

    url_fixtures = f"{BASE_URL}/fixtures"
    params = {
        "league": LEAGUE_ID,
        "season": SEASON_YEAR,
        "round": round_name
    }
    headers = {
        "x-rapidapi-key": API_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST
    }

    try:
        r = requests.get(url_fixtures, params=params, headers=headers)
        if r.status_code == 200:
            data = r.json()
            fixtures = data.get('response', [])

            # Insérer dans la table 'matches'
            # On peut créer des colonnes supplémentaires si besoin (ex: round)
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()

            # Ajouter la colonne 'round' si vous le souhaitez
            c.execute("""
                CREATE TABLE IF NOT EXISTS matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    home_team TEXT,
                    away_team TEXT,
                    date TEXT,
                    home_score INTEGER,
                    away_score INTEGER,
                    round TEXT
                )
            """)

            # Insertion
            for fix in fixtures:
                fixture_id = fix['fixture']['id']
                date_match = fix['fixture']['date']
                round_api = fix['league']['round']  # ex: "Regular Season - 2"
                home_team = fix['teams']['home']['name']
                away_team = fix['teams']['away']['name']
                home_score = fix['goals']['home']
                away_score = fix['goals']['away']

                c.execute("""
                    INSERT INTO matches (home_team, away_team, date, home_score, away_score, round)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (home_team, away_team, date_match, home_score, away_score, round_api))

            conn.commit()
            conn.close()

            return jsonify({
                "message": f"Inserted {len(fixtures)} fixture(s) for round={round_name}",
                "nb_fixtures": len(fixtures)
            })
        else:
            return jsonify({"error": f"Erreur API-Football /fixtures status {r.status_code}"})
    except Exception as e:
        return jsonify({"error": str(e)})

############################################
# MAIN
############################################

if __name__ == '__main__':
    # S'assurer que la DB est initialisée ?
    # ex: with sqlite3.connect(DATABASE) as conn: ...
    app.run(debug=True)
