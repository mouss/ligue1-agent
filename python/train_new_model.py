import sqlite3
import pandas as pd
import numpy as np
import joblib
import xgboost as xgb
from sklearn.model_selection import train_test_split
import os

# Chemins des fichiers
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'db', 'ligue1.db')
MODEL_HOME_PATH = os.path.join(os.path.dirname(__file__), 'model_new_home')
MODEL_AWAY_PATH = os.path.join(os.path.dirname(__file__), 'model_new_away')

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
            CASE 
                WHEN em.competition IS NOT NULL THEN 1 
                ELSE 0 
            END as has_european_match,
            CASE 
                WHEN julianday(m.date) - julianday(em.match_date) <= 3 THEN 1
                ELSE 0
            END as european_match_fatigue
        FROM matches m
        LEFT JOIN stadium_conditions sc ON date(m.date) = date(sc.match_date)
        LEFT JOIN european_matches em ON (
            (m.home_team = em.team OR m.away_team = em.team)
            AND em.match_date BETWEEN datetime(m.date, '-7 days') AND m.date
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
        MAX(has_european_match) as has_european_match,
        MAX(european_match_fatigue) as european_match_fatigue
    FROM match_conditions
    GROUP BY home_team, away_team, date
    ORDER BY date
    """
    matches = pd.read_sql_query(query, conn)
    conn.close()
    return matches

def calculate_form(matches, team, n_matches=5):
    """Calcule la forme d'une équipe sur ses n derniers matchs avec pondération"""
    team_matches = matches[
        (matches['home_team'] == team) | 
        (matches['away_team'] == team)
    ].tail(n_matches)
    
    if team_matches.empty:
        return 0
    
    weights = np.exp(np.linspace(-1, 0, len(team_matches)))
    weights = weights / weights.sum()
    
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
        
        form += weights[i] * (points + 0.1 * goal_diff)
    
    return form / 3

def prepare_features(matches):
    """Prépare les features pour l'entraînement"""
    features = []
    targets_home = []
    targets_away = []
    
    for i in range(len(matches)):
        if i < 5:  # Skip first 5 matches as we need history
            continue
            
        match = matches.iloc[i]
        past_matches = matches.iloc[:i]
        
        # Features de base
        home_team = match['home_team']
        away_team = match['away_team']
        
        # Calcul des moyennes de buts
        home_games = past_matches[past_matches['home_team'] == home_team]
        away_games = past_matches[past_matches['away_team'] == away_team]
        
        home_goals_scored_avg = home_games['home_score'].mean() if not home_games.empty else 0
        home_goals_conceded_avg = home_games['away_score'].mean() if not home_games.empty else 0
        away_goals_scored_avg = away_games['away_score'].mean() if not away_games.empty else 0
        away_goals_conceded_avg = away_games['home_score'].mean() if not away_games.empty else 0
        
        # Calcul de la forme
        home_form = calculate_form(past_matches, home_team)
        away_form = calculate_form(past_matches, away_team)
        
        # Normalisation des données météo
        weather_temp = match['weather_temp'] if pd.notna(match['weather_temp']) else 20  # température par défaut
        weather_rain = match['weather_rain'] if pd.notna(match['weather_rain']) else 0
        weather_wind = match['weather_wind'] if pd.notna(match['weather_wind']) else 0
        
        # Impact des matchs européens
        home_european = match['has_european_match'] if pd.notna(match['has_european_match']) else 0
        away_european = match['has_european_match'] if pd.notna(match['has_european_match']) else 0
        
        # Fatigue due aux matchs européens
        home_fatigue = match['european_match_fatigue'] if pd.notna(match['european_match_fatigue']) else 0
        away_fatigue = match['european_match_fatigue'] if pd.notna(match['european_match_fatigue']) else 0
        
        feature_vector = [
            home_form, away_form,
            home_goals_scored_avg, away_goals_scored_avg,
            home_goals_conceded_avg, away_goals_conceded_avg,
            weather_temp / 30.0,  # Normalisation température (0-30°C)
            weather_rain / 100.0,  # Normalisation pluie (0-100%)
            weather_wind / 50.0,   # Normalisation vent (0-50 km/h)
            home_european,
            away_european,
            home_fatigue,
            away_fatigue
        ]
        
        features.append(feature_vector)
        targets_home.append(match['home_score'])
        targets_away.append(match['away_score'])
    
    return np.array(features), np.array(targets_home), np.array(targets_away)

def train_models():
    """Entraîne les modèles de prédiction"""
    print("Chargement des données...")
    matches = get_matches()
    matches = matches[matches['home_score'].notna()]  # Keep only matches with scores
    
    print("Préparation des features...")
    X, y_home, y_away = prepare_features(matches)
    
    # Split des données
    X_train, X_test, y_home_train, y_home_test, y_away_train, y_away_test = train_test_split(
        X, y_home, y_away, test_size=0.2, random_state=42
    )
    
    # Paramètres XGBoost optimisés
    params = {
        'n_estimators': 150,
        'learning_rate': 0.05,
        'max_depth': 4,
        'min_child_weight': 2,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'objective': 'reg:squarederror',
        'random_state': 42
    }
    
    print("Entraînement du modèle home...")
    model_home = xgb.XGBRegressor(**params)
    model_home.fit(X_train, y_home_train)
    
    print("Entraînement du modèle away...")
    model_away = xgb.XGBRegressor(**params)
    model_away.fit(X_train, y_away_train)
    
    # Calcul des métriques
    home_pred = model_home.predict(X_test)
    away_pred = model_away.predict(X_test)
    
    home_rmse = np.sqrt(np.mean((y_home_test - home_pred) ** 2))
    away_rmse = np.sqrt(np.mean((y_away_test - away_pred) ** 2))
    
    print(f"RMSE buts domicile: {home_rmse:.3f}")
    print(f"RMSE buts extérieur: {away_rmse:.3f}")
    
    # Sauvegarde des modèles
    print("Sauvegarde des modèles...")
    joblib.dump(model_home, MODEL_HOME_PATH)
    joblib.dump(model_away, MODEL_AWAY_PATH)
    
    print("Modèles sauvegardés avec succès!")

if __name__ == "__main__":
    train_models()
