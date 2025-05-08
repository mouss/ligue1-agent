import sqlite3
import pandas as pd
import numpy as np
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_squared_error, mean_absolute_error
import joblib
import os
from datetime import datetime
import sys
import json

# Chemins des fichiers
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'db', 'ligue1.db')
MODEL_HOME_PATH = os.path.join(os.path.dirname(__file__), 'model_new_home')
MODEL_AWAY_PATH = os.path.join(os.path.dirname(__file__), 'model_new_away')

def load_data():
    """Charge les données d'entraînement avec features améliorées"""
    conn = sqlite3.connect(DB_PATH)
    
    query = """
    WITH match_stats AS (
        SELECT 
            team,
            strftime('%Y-%m', date) as month,
            AVG(goals_scored) as avg_goals_scored,
            AVG(goals_conceded) as avg_goals_conceded,
            COUNT(*) as matches_played
        FROM (
            SELECT 
                home_team as team, 
                home_score as goals_scored, 
                away_score as goals_conceded,
                date
            FROM matches
            WHERE home_score IS NOT NULL
            UNION ALL
            SELECT 
                away_team, 
                away_score, 
                home_score,
                date
            FROM matches
            WHERE away_score IS NOT NULL
        )
        GROUP BY team, month
    ),
    head_to_head AS (
        SELECT 
            home_team,
            away_team,
            AVG(home_score) as avg_h2h_home_goals,
            AVG(away_score) as avg_h2h_away_goals,
            COUNT(*) as h2h_matches
        FROM matches
        WHERE home_score IS NOT NULL
        GROUP BY home_team, away_team
    )
    SELECT 
        m.home_team,
        m.away_team,
        m.home_score as home_goals,
        m.away_score as away_goals,
        m.date,
        
        -- Forme des équipes
        tf_home.form as home_team_form,
        tf_away.form as away_team_form,
        
        -- Statistiques mensuelles
        h_stats.avg_goals_scored as home_goals_scored_avg,
        h_stats.avg_goals_conceded as home_goals_conceded_avg,
        a_stats.avg_goals_scored as away_goals_scored_avg,
        a_stats.avg_goals_conceded as away_goals_conceded_avg,
        h_stats.matches_played as home_matches_played,
        a_stats.matches_played as away_matches_played,
        
        -- Statistiques head-to-head
        COALESCE(h2h.avg_h2h_home_goals, 0) as avg_h2h_home_goals,
        COALESCE(h2h.avg_h2h_away_goals, 0) as avg_h2h_away_goals,
        COALESCE(h2h.h2h_matches, 0) as h2h_matches,
        
        -- Données météo
        sc.temperature as weather_temp,
        sc.precipitation as weather_rain,
        sc.wind_speed as weather_wind,
        
        -- Données joueurs
        COALESCE(h_missing.missing_count, 0) as home_missing_key_players,
        COALESCE(a_missing.missing_count, 0) as away_missing_key_players,
        
        -- Contexte européen
        CASE WHEN em_home.team IS NOT NULL THEN 1 ELSE 0 END as home_european_match,
        CASE WHEN em_away.team IS NOT NULL THEN 1 ELSE 0 END as away_european_match
        
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
    LEFT JOIN match_stats h_stats ON 
        h_stats.team = m.home_team AND 
        h_stats.month = strftime('%Y-%m', m.date)
    LEFT JOIN match_stats a_stats ON 
        a_stats.team = m.away_team AND
        a_stats.month = strftime('%Y-%m', m.date)
    LEFT JOIN head_to_head h2h ON 
        h2h.home_team = m.home_team AND 
        h2h.away_team = m.away_team
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
    LEFT JOIN european_matches em_home ON 
        em_home.team = m.home_team AND
        em_home.match_date BETWEEN datetime(m.date, '-3 days') AND m.date
    LEFT JOIN european_matches em_away ON 
        em_away.team = m.away_team AND
        em_away.match_date BETWEEN datetime(m.date, '-3 days') AND m.date
    WHERE m.home_score IS NOT NULL 
    AND m.away_score IS NOT NULL
    ORDER BY m.date DESC
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def prepare_features(df):
    """Prépare et normalise les features avec des améliorations"""
    # Convertir les colonnes de forme en valeurs numériques
    df['home_team_form'] = pd.to_numeric(df['home_team_form'], errors='coerce')
    df['away_team_form'] = pd.to_numeric(df['away_team_form'], errors='coerce')
    
    # Calculer des features dérivées
    df['form_difference'] = df['home_team_form'] - df['away_team_form']
    df['goals_scored_diff'] = df['home_goals_scored_avg'] - df['away_goals_scored_avg']
    df['goals_conceded_diff'] = df['home_goals_conceded_avg'] - df['away_goals_conceded_avg']
    df['h2h_goal_diff'] = df['avg_h2h_home_goals'] - df['avg_h2h_away_goals']
    
    # Normaliser le nombre de matchs h2h
    df['h2h_experience'] = np.log1p(df['h2h_matches'])
    
    # Créer des indicateurs de forme récente
    df['home_high_form'] = (df['home_team_form'] > df['home_team_form'].mean()).astype(int)
    df['away_high_form'] = (df['away_team_form'] > df['away_team_form'].mean()).astype(int)
    
    # Remplir les valeurs manquantes
    fill_values = {
        'home_team_form': df['home_team_form'].mean(),
        'away_team_form': df['away_team_form'].mean(),
        'weather_temp': df['weather_temp'].mean(),
        'weather_rain': 0,
        'weather_wind': df['weather_wind'].mean(),
        'home_missing_key_players': 0,
        'away_missing_key_players': 0,
        'home_european_match': 0,
        'away_european_match': 0
    }
    
    df = df.fillna(fill_values)
    
    # Normalisation des features numériques
    numeric_features = [
        'home_team_form', 'away_team_form',
        'home_goals_scored_avg', 'away_goals_scored_avg',
        'home_goals_conceded_avg', 'away_goals_conceded_avg',
        'weather_temp', 'weather_rain', 'weather_wind',
        'home_missing_key_players', 'away_missing_key_players',
        'form_difference', 'goals_scored_diff', 'goals_conceded_diff',
        'h2h_goal_diff', 'h2h_experience'
    ]
    
    for feature in numeric_features:
        mean = df[feature].mean()
        std = df[feature].std()
        if std > 0:
            df[feature] = (df[feature] - mean) / std
    
    return df

def train_models(df):
    """Entraîne les modèles avec validation croisée"""
    # Préparation des features
    features = [
        'home_team_form', 'away_team_form',
        'home_goals_scored_avg', 'away_goals_scored_avg',
        'home_goals_conceded_avg', 'away_goals_conceded_avg',
        'weather_temp', 'weather_rain', 'weather_wind',
        'home_missing_key_players', 'away_missing_key_players',
        'form_difference', 'goals_scored_diff', 'goals_conceded_diff',
        'h2h_goal_diff', 'h2h_experience',
        'home_high_form', 'away_high_form',
        'home_european_match', 'away_european_match'
    ]
    
    X = df[features]
    y_home = df['home_goals']
    y_away = df['away_goals']
    
    # Split des données
    X_train, X_test, y_home_train, y_home_test, y_away_train, y_away_test = train_test_split(
        X, y_home, y_away, test_size=0.2, random_state=42
    )
    
    # Configuration des modèles avec les paramètres optimisés
    params = {
        'n_estimators': 150,
        'learning_rate': 0.05,
        'max_depth': 4,
        'min_child_weight': 2,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'random_state': 42
    }
    
    # Entraînement et évaluation du modèle domicile
    model_home = XGBRegressor(**params)
    home_cv_scores = cross_val_score(model_home, X_train, y_home_train, cv=5, scoring='neg_mean_squared_error')
    model_home.fit(X_train, y_home_train)
    home_predictions = model_home.predict(X_test)
    
    # Entraînement et évaluation du modèle extérieur
    model_away = XGBRegressor(**params)
    away_cv_scores = cross_val_score(model_away, X_train, y_away_train, cv=5, scoring='neg_mean_squared_error')
    model_away.fit(X_train, y_away_train)
    away_predictions = model_away.predict(X_test)
    
    # Calcul des métriques
    metrics = {
        'home': {
            'rmse': np.sqrt(mean_squared_error(y_home_test, home_predictions)),
            'mae': mean_absolute_error(y_home_test, home_predictions),
            'cv_rmse': np.sqrt(-home_cv_scores.mean())
        },
        'away': {
            'rmse': np.sqrt(mean_squared_error(y_away_test, away_predictions)),
            'mae': mean_absolute_error(y_away_test, away_predictions),
            'cv_rmse': np.sqrt(-away_cv_scores.mean())
        }
    }
    
    # Affichage des métriques détaillées
    print("\nMétriques du modèle domicile:")
    print(f"RMSE: {metrics['home']['rmse']:.3f}")
    print(f"MAE: {metrics['home']['mae']:.3f}")
    print(f"CV RMSE: {metrics['home']['cv_rmse']:.3f}")
    
    print("\nMétriques du modèle extérieur:")
    print(f"RMSE: {metrics['away']['rmse']:.3f}")
    print(f"MAE: {metrics['away']['mae']:.3f}")
    print(f"CV RMSE: {metrics['away']['cv_rmse']:.3f}")
    
    return {
        'home': model_home,
        'away': model_away,
        'metrics': metrics,
        'feature_importance': {
            'home': dict(zip(features, model_home.feature_importances_)),
            'away': dict(zip(features, model_away.feature_importances_))
        }
    }

def save_models(models):
    """Sauvegarde les modèles et leurs métriques"""
    try:
        # Sauvegarder les modèles séparément
        joblib.dump(models['home'], MODEL_HOME_PATH)
        joblib.dump(models['away'], MODEL_AWAY_PATH)
        
        # Convertir les valeurs numpy en float pour la sérialisation JSON
        metrics_json = {
            'metrics': {
                'home': {k: float(v) for k, v in models['metrics']['home'].items()},
                'away': {k: float(v) for k, v in models['metrics']['away'].items()}
            },
            'feature_importance': {
                'home': {k: float(v) for k, v in models['feature_importance']['home'].items()},
                'away': {k: float(v) for k, v in models['feature_importance']['away'].items()}
            },
            'timestamp': datetime.now().isoformat()
        }
        
        # Sauvegarder les métriques et l'importance des features
        metrics_path = os.path.join(os.path.dirname(__file__), 'model_metrics.json')
        with open(metrics_path, 'w') as f:
            json.dump(metrics_json, f, indent=2)
        
        print(f"Modèles sauvegardés dans {os.path.dirname(__file__)}")
        print(f"Métriques sauvegardées dans {metrics_path}")
        
    except Exception as e:
        print(f"Erreur lors de la sauvegarde des modèles: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    try:
        print("Chargement des données...")
        df = load_data()
        print(f"Nombre d'échantillons: {len(df)}")
        
        print("\nPréparation des features...")
        df = prepare_features(df)
        
        print("\nEntraînement des modèles...")
        models = train_models(df)
        
        print("\nSauvegarde des modèles...")
        save_models(models)
        
        # Affichage des features les plus importantes
        print("\nFeatures les plus importantes (modèle domicile):")
        home_importance = sorted(models['feature_importance']['home'].items(), key=lambda x: x[1], reverse=True)
        for feature, importance in home_importance[:5]:
            print(f"{feature}: {importance:.3f}")
        
        print("\nFeatures les plus importantes (modèle extérieur):")
        away_importance = sorted(models['feature_importance']['away'].items(), key=lambda x: x[1], reverse=True)
        for feature, importance in away_importance[:5]:
            print(f"{feature}: {importance:.3f}")
        
    except Exception as e:
        print(f"Erreur: {str(e)}", file=sys.stderr)
        sys.exit(1)
