import sqlite3
import pandas as pd
import numpy as np
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
import joblib
import os
from datetime import datetime
import sys
import json

# Chemins des fichiers
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'db', 'ligue1.db')
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'model.joblib')

def load_data():
    """Charge les données d'entraînement depuis la base de données"""
    conn = sqlite3.connect(DB_PATH)
    
    # Requête pour récupérer les matches avec toutes les features
    query = """
    WITH match_stats AS (
        SELECT 
            team,
            AVG(goals_scored) as avg_goals_scored,
            AVG(goals_conceded) as avg_goals_conceded
        FROM (
            SELECT home_team as team, home_score as goals_scored, away_score as goals_conceded
            FROM matches
            WHERE home_score IS NOT NULL
            UNION ALL
            SELECT away_team, away_score, home_score
            FROM matches
            WHERE away_score IS NOT NULL
        )
        GROUP BY team
    )
    SELECT 
        m.home_team,
        m.away_team,
        m.home_score as home_goals,
        m.away_score as away_goals,
        m.date,
        
        -- Statistiques de forme
        tf_home.form as home_team_form,
        tf_away.form as away_team_form,
        
        -- Moyennes de buts précalculées
        h_stats.avg_goals_scored as home_goals_scored_avg,
        h_stats.avg_goals_conceded as home_goals_conceded_avg,
        a_stats.avg_goals_scored as away_goals_scored_avg,
        a_stats.avg_goals_conceded as away_goals_conceded_avg,
        
        -- Données météo
        sc.temperature as weather_temp,
        sc.precipitation as weather_rain,
        sc.wind_speed as weather_wind,
        
        -- Données joueurs (optimisées)
        COALESCE(h_missing.missing_count, 0) as home_missing_key_players,
        COALESCE(a_missing.missing_count, 0) as away_missing_key_players
        
    FROM matches m
    LEFT JOIN team_form tf_home ON tf_home.team = m.home_team 
        AND tf_home.date = (
            SELECT MAX(date) 
            FROM team_form 
            WHERE team = m.home_team AND date <= m.date
        )
    LEFT JOIN team_form tf_away ON tf_away.team = m.away_team 
        AND tf_away.date = (
            SELECT MAX(date) 
            FROM team_form 
            WHERE team = m.away_team AND date <= m.date
        )
    LEFT JOIN match_stats h_stats ON h_stats.team = m.home_team
    LEFT JOIN match_stats a_stats ON a_stats.team = m.away_team
    LEFT JOIN stadium_conditions sc ON sc.match_date = m.date
    LEFT JOIN (
        SELECT team, COUNT(*) as missing_count
        FROM player_availability
        WHERE is_key_player = 1
        GROUP BY team
    ) h_missing ON h_missing.team = m.home_team
    LEFT JOIN (
        SELECT team, COUNT(*) as missing_count
        FROM player_availability
        WHERE is_key_player = 1
        GROUP BY team
    ) a_missing ON a_missing.team = m.away_team
    WHERE m.home_score IS NOT NULL 
    AND m.away_score IS NOT NULL
    ORDER BY m.date DESC
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def prepare_features(df):
    """Prépare et normalise les features"""
    # Remplir les valeurs manquantes
    df = df.fillna({
        'weather_temp': df['weather_temp'].mean(),
        'weather_rain': 0,
        'weather_wind': df['weather_wind'].mean(),
        'home_missing_key_players': 0,
        'away_missing_key_players': 0
    })
    
    # Normalisation des features numériques
    numeric_features = [
        'home_team_form', 'away_team_form',
        'home_goals_scored_avg', 'away_goals_scored_avg',
        'home_goals_conceded_avg', 'away_goals_conceded_avg',
        'weather_temp', 'weather_rain', 'weather_wind',
        'home_missing_key_players', 'away_missing_key_players'
    ]
    
    for feature in numeric_features:
        mean = df[feature].mean()
        std = df[feature].std()
        if std > 0:
            df[feature] = (df[feature] - mean) / std
    
    return df

def train_models(df):
    """Entraîne les modèles de prédiction"""
    # Préparation des features
    features = [
        'home_team_form', 'away_team_form',
        'home_goals_scored_avg', 'away_goals_scored_avg',
        'home_goals_conceded_avg', 'away_goals_conceded_avg',
        'weather_temp', 'weather_rain', 'weather_wind',
        'home_missing_key_players', 'away_missing_key_players'
    ]
    
    X = df[features]
    y_home = df['home_goals']
    y_away = df['away_goals']
    
    # Split des données
    X_train, X_test, y_home_train, y_home_test, y_away_train, y_away_test = train_test_split(
        X, y_home, y_away, test_size=0.2, random_state=42
    )
    
    # Configuration des modèles
    params = {
        'n_estimators': 150,
        'learning_rate': 0.05,
        'max_depth': 4,
        'min_child_weight': 2,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'random_state': 42
    }
    
    # Entraînement du modèle pour les buts à domicile
    model_home = XGBRegressor(**params)
    model_home.fit(X_train, y_home_train)
    
    # Entraînement du modèle pour les buts à l'extérieur
    model_away = XGBRegressor(**params)
    model_away.fit(X_train, y_away_train)
    
    # Évaluation des modèles
    home_rmse = np.sqrt(((model_home.predict(X_test) - y_home_test) ** 2).mean())
    away_rmse = np.sqrt(((model_away.predict(X_test) - y_away_test) ** 2).mean())
    
    print(f"RMSE buts domicile: {home_rmse:.3f}")
    print(f"RMSE buts extérieur: {away_rmse:.3f}")
    
    return {
        'home': model_home,
        'away': model_away,
        'metrics': {
            'home_rmse': home_rmse,
            'away_rmse': away_rmse
        }
    }

def save_models(models, filename='ligue1_model.pkl'):
    """Sauvegarde les modèles entraînés"""
    try:
        joblib.dump(models, filename)
        print(f"Modèles sauvegardés dans {filename}")
    except Exception as e:
        print(f"Erreur lors de la sauvegarde des modèles: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    try:
        # Chargement des données
        print("Chargement des données...")
        df = load_data()
        
        # Préparation des features
        print("Préparation des features...")
        df = prepare_features(df)
        
        # Entraînement des modèles
        print("Entraînement des modèles...")
        models = train_models(df)
        
        # Sauvegarde des modèles
        save_models(models, MODEL_PATH)
        
        # Affichage des métriques finales
        print("\nMétriques finales:")
        print(json.dumps(models['metrics'], indent=2))
        
    except Exception as e:
        print(f"Erreur: {str(e)}", file=sys.stderr)
        sys.exit(1)
