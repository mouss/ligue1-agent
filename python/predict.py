import sqlite3
import pandas as pd
import numpy as np
import joblib
import json
import os
import sys
from datetime import datetime

# Chemins des fichiers
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'db', 'ligue1.db')
MODEL_HOME_PATH = os.path.join(os.path.dirname(__file__), 'model_new_home')
MODEL_AWAY_PATH = os.path.join(os.path.dirname(__file__), 'model_new_away')

def log(message):
    """Écrit les logs sur stderr pour ne pas interférer avec la sortie JSON"""
    print(message, file=sys.stderr)

def get_matches():
    """Récupère les matchs de la base de données"""
    conn = sqlite3.connect(DB_PATH)
    query = """
    WITH match_conditions AS (
        SELECT 
            m.id,
            m.home_team,
            m.away_team,
            m.home_score,
            m.away_score,
            m.date,
            sc.temperature as weather_temp,
            sc.precipitation as weather_rain,
            sc.wind_speed as weather_wind,
            sc.weather_condition,
            CASE 
                WHEN em_home.team IS NOT NULL THEN 1
                ELSE 0 
            END as home_european_match,
            CASE 
                WHEN em_away.team IS NOT NULL THEN 1
                ELSE 0 
            END as away_european_match,
            CASE 
                WHEN julianday(m.date) - julianday(em_home.match_date) <= 3 THEN 1
                ELSE 0
            END as home_team_fatigue,
            CASE 
                WHEN julianday(m.date) - julianday(em_away.match_date) <= 3 THEN 1
                ELSE 0
            END as away_team_fatigue,
            em_home.competition as home_european_competition,
            em_away.competition as away_european_competition
        FROM matches m
        LEFT JOIN stadium_conditions sc ON date(m.date) = date(sc.match_date)
        LEFT JOIN european_matches em_home ON (
            m.home_team = em_home.team
            AND em_home.match_date BETWEEN datetime(m.date, '-7 days') AND m.date
        )
        LEFT JOIN european_matches em_away ON (
            m.away_team = em_away.team
            AND em_away.match_date BETWEEN datetime(m.date, '-7 days') AND m.date
        )
    )
    SELECT DISTINCT 
        MIN(id) as id,
        home_team,
        away_team,
        home_score,
        away_score,
        date,
        AVG(weather_temp) as weather_temp,
        AVG(weather_rain) as weather_rain,
        AVG(weather_wind) as weather_wind,
        MAX(weather_condition) as weather_condition,
        MAX(home_european_match) as home_european_match,
        MAX(away_european_match) as away_european_match,
        MAX(home_team_fatigue) as home_team_fatigue,
        MAX(away_team_fatigue) as away_team_fatigue,
        MAX(home_european_competition) as home_european_competition,
        MAX(away_european_competition) as away_european_competition
    FROM match_conditions
    GROUP BY home_team, away_team, date
    ORDER BY date
    """
    matches = pd.read_sql_query(query, conn)
    conn.close()
    return matches

def get_predictions():
    """Récupère les prédictions depuis la base de données"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Récupérer les prédictions
        cursor.execute("""
            SELECT 
                p.fixture_id,
                p.date,
                p.home_team,
                p.away_team,
                p.home_score_pred,
                p.away_score_pred,
                p.home_win_prob,
                p.draw_prob,
                p.away_win_prob,
                sc.temperature,
                sc.precipitation,
                sc.wind_speed,
                sc.weather_condition,
                em.competition as home_euro_comp,
                em2.competition as away_euro_comp
            FROM predictions p
            LEFT JOIN stadium_conditions sc ON p.date = sc.match_date
            LEFT JOIN european_matches em ON p.home_team = em.team 
                AND DATE(p.date) BETWEEN DATE(em.match_date, '-3 days') AND DATE(em.match_date, '+3 days')
            LEFT JOIN european_matches em2 ON p.away_team = em2.team 
                AND DATE(p.date) BETWEEN DATE(em2.match_date, '-3 days') AND DATE(em2.match_date, '+3 days')
            ORDER BY p.date ASC
        """)
        
        rows = cursor.fetchall()
        predictions = []
        
        for row in rows:
            prediction = {
                'match_id': row[0],
                'date': row[1],
                'home_team': row[2],
                'away_team': row[3],
                'predicted_home_score': row[4],
                'predicted_away_score': row[5],
                'home_win_probability': row[6],
                'draw_probability': row[7],
                'away_win_probability': row[8],
                'weather': {
                    'temperature': row[9],
                    'precipitation': row[10],
                    'wind_speed': row[11],
                    'condition': row[12]
                } if row[9] is not None else None,
                'european_context': {
                    'home_team_european': row[13] is not None,
                    'home_competition': row[13],
                    'home_team_fatigue': row[13] is not None,
                    'away_team_european': row[14] is not None,
                    'away_competition': row[14],
                    'away_team_fatigue': row[14] is not None
                }
            }
            predictions.append(prediction)
        
        conn.close()
        return predictions
        
    except Exception as e:
        print(f"Erreur lors de la récupération des prédictions : {e}")
        return []

def calculate_form(matches, team, n_matches=5):
    """Calcule la forme d'une équipe sur ses n derniers matchs avec pondération"""
    team_matches = matches[
        (matches['home_team'] == team) | 
        (matches['away_team'] == team)
    ].tail(n_matches)
    
    if team_matches.empty:
        return 0
    
    weights = np.exp(np.linspace(-1, 0, len(team_matches)))  # Plus de poids aux matchs récents
    weights = weights / weights.sum()  # Normalisation des poids
    
    form = 0
    for i, (_, match) in enumerate(team_matches.iterrows()):
        points = 0
        if match['home_team'] == team:
            if match['home_score'] > match['away_score']:
                points = 3
            elif match['home_score'] == match['away_score']:
                points = 1
            goal_diff = match['home_score'] - match['away_score']
        else:
            if match['away_score'] > match['home_score']:
                points = 3
            elif match['home_score'] == match['away_score']:
                points = 1
            goal_diff = match['away_score'] - match['home_score']
        
        # Ajout de la différence de buts dans le calcul de la forme
        form += weights[i] * (points + 0.1 * goal_diff)
    
    return form / 3  # Normalisation entre 0 et ~1

def normalize_features(df):
    """Normalise les features numériques"""
    numeric_features = [
        'home_team_form', 'away_team_form',
        'home_goals_scored_avg', 'away_goals_scored_avg',
        'home_goals_conceded_avg', 'away_goals_conceded_avg',
        'weather_temp', 'weather_rain', 'weather_wind',
        'home_european', 'away_european',
        'home_fatigue', 'away_fatigue'
    ]
    
    for feature in numeric_features:
        if feature in df.columns:
            mean = df[feature].mean()
            std = df[feature].std()
            if std > 0:
                df[feature] = (df[feature] - mean) / std
    return df

def prepare_features(upcoming_matches, historical_matches):
    """Prépare les features pour les matchs à venir"""
    # Création du DataFrame avec les features
    df = pd.DataFrame(columns=[
        'home_team', 'away_team',
        'home_team_form', 'away_team_form',
        'home_goals_scored_avg', 'away_goals_scored_avg',
        'home_goals_conceded_avg', 'away_goals_conceded_avg',
        'weather_temp', 'weather_rain', 'weather_wind',
        'home_european', 'away_european',
        'home_fatigue', 'away_fatigue'
    ])
    
    # Ajout des matchs à venir
    for _, match in upcoming_matches.iterrows():
        row = {
            'home_team': match['home_team'],
            'away_team': match['away_team'],
            'home_team_form': calculate_form(historical_matches, match['home_team']),
            'away_team_form': calculate_form(historical_matches, match['away_team']),
            'home_goals_scored_avg': historical_matches[historical_matches['home_team'] == match['home_team']]['home_score'].mean(),
            'away_goals_scored_avg': historical_matches[historical_matches['away_team'] == match['away_team']]['away_score'].mean(),
            'home_goals_conceded_avg': historical_matches[historical_matches['home_team'] == match['home_team']]['away_score'].mean(),
            'away_goals_conceded_avg': historical_matches[historical_matches['away_team'] == match['away_team']]['home_score'].mean(),
            'weather_temp': match['weather_temp'] if pd.notna(match['weather_temp']) else 0,
            'weather_rain': match['weather_rain'] if pd.notna(match['weather_rain']) else 0,
            'weather_wind': match['weather_wind'] if pd.notna(match['weather_wind']) else 0,
            'home_european': match['home_european_match'] if pd.notna(match['home_european_match']) else 0,
            'away_european': match['away_european_match'] if pd.notna(match['away_european_match']) else 0,
            'home_fatigue': match['home_team_fatigue'] if pd.notna(match['home_team_fatigue']) else 0,
            'away_fatigue': match['away_team_fatigue'] if pd.notna(match['away_team_fatigue']) else 0
        }
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    
    # Gestion des NaN
    df = df.fillna(0)
    
    # Normalisation des features
    df = normalize_features(df)
    
    # Colonnes attendues dans l'ordre
    feature_columns = [
        'home_team_form', 'away_team_form',
        'home_goals_scored_avg', 'away_goals_scored_avg',
        'home_goals_conceded_avg', 'away_goals_conceded_avg',
        'weather_temp', 'weather_rain', 'weather_wind',
        'home_european', 'away_european',
        'home_fatigue', 'away_fatigue'
    ]
    
    return df[['home_team', 'away_team'] + feature_columns]

def predict_scores():
    """Prédit les scores des matchs à venir"""
    try:
        # Chargement des données
        log("Chargement des données...")
        matches = get_matches()
        historical_matches = matches[matches['home_score'].notna()]
        upcoming_matches = matches[matches['home_score'].isna()]
        
        if upcoming_matches.empty:
            log("Aucun match à venir trouvé.")
            print(json.dumps([]))
            return []
        
        # Chargement du modèle
        log("Chargement du modèle...")
        model_home = joblib.load(MODEL_HOME_PATH)
        model_away = joblib.load(MODEL_AWAY_PATH)
        
        # Préparation des features
        log("Préparation des features...")
        features = prepare_features(upcoming_matches, historical_matches)
        X = features.drop(['home_team', 'away_team'], axis=1)
        
        # Prédiction
        log("Prédiction des scores...")
        home_scores = model_home.predict(X)
        away_scores = model_away.predict(X)
        
        # Préparation des résultats
        predictions = []
        for i, (_, match) in enumerate(upcoming_matches.iterrows()):
            prediction = {
                'match_id': int(match['id']),
                'home_team': match['home_team'],
                'away_team': match['away_team'],
                'predicted_home_score': round(float(home_scores[i]), 2),
                'predicted_away_score': round(float(away_scores[i]), 2),
                'date': match['date'],
                'weather': {
                    'temperature': float(match['weather_temp']) if pd.notna(match['weather_temp']) else None,
                    'precipitation': float(match['weather_rain']) if pd.notna(match['weather_rain']) else None,
                    'wind_speed': float(match['weather_wind']) if pd.notna(match['weather_wind']) else None,
                    'condition': match['weather_condition'] if pd.notna(match['weather_condition']) else None
                },
                'european_context': {
                    'home_team_european': bool(match['home_european_match']) if pd.notna(match['home_european_match']) else False,
                    'away_team_european': bool(match['away_european_match']) if pd.notna(match['away_european_match']) else False,
                    'home_team_fatigue': bool(match['home_team_fatigue']) if pd.notna(match['home_team_fatigue']) else False,
                    'away_team_fatigue': bool(match['away_team_fatigue']) if pd.notna(match['away_team_fatigue']) else False,
                    'home_competition': match['home_european_competition'] if pd.notna(match['home_european_competition']) else None,
                    'away_competition': match['away_european_competition'] if pd.notna(match['away_european_competition']) else None
                }
            }
            predictions.append(prediction)
        
        # Tri par date
        predictions.sort(key=lambda x: x['date'])
        
        log(f"Prédictions générées pour {len(predictions)} match(s).")
        
        # Sortie JSON uniquement sur stdout
        print(json.dumps(predictions, indent=2))
        return predictions
        
    except Exception as e:
        error_msg = f"Erreur lors de la prédiction : {str(e)}"
        log(error_msg)
        print(json.dumps({"error": error_msg}))
        sys.exit(1)

if __name__ == "__main__":
    predict_scores()
