import sqlite3
import pandas as pd
import numpy as np
from xgboost import XGBRegressor
from sklearn.model_selection import cross_val_score, KFold
from sklearn.preprocessing import StandardScaler
import joblib
import os
import sys
import json

# Chemins des fichiers
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'db', 'ligue1.db')
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'enhanced_model.joblib')

# Liste des features utilisées pour l'entraînement
FEATURES = [
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

def load_data():
    """Charge les données d'entraînement depuis la base de données"""
    conn = sqlite3.connect(DB_PATH)
    
    query = """
    WITH RECURSIVE 
    match_stats AS (
        SELECT 
            team,
            strftime('%Y-%m', date) as month,
            AVG(goals_scored) as avg_goals_scored,
            AVG(goals_conceded) as avg_goals_conceded,
            COUNT(*) as matches_played,
            SUM(CASE WHEN goals_scored > goals_conceded THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN goals_scored = goals_conceded THEN 1 ELSE 0 END) as draws,
            SUM(CASE WHEN goals_scored < goals_conceded THEN 1 ELSE 0 END) as losses
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
    team_streaks AS (
        SELECT 
            team,
            date,
            SUM(CASE WHEN result = 'W' THEN 1 ELSE 0 END) OVER (
                PARTITION BY team ORDER BY date ROWS BETWEEN 5 PRECEDING AND CURRENT ROW
            ) as win_streak,
            SUM(CASE WHEN result = 'L' THEN 1 ELSE 0 END) OVER (
                PARTITION BY team ORDER BY date ROWS BETWEEN 5 PRECEDING AND CURRENT ROW
            ) as loss_streak
        FROM (
            SELECT 
                home_team as team,
                date,
                CASE 
                    WHEN home_score > away_score THEN 'W'
                    WHEN home_score < away_score THEN 'L'
                    ELSE 'D'
                END as result
            FROM matches
            WHERE home_score IS NOT NULL
            UNION ALL
            SELECT 
                away_team,
                date,
                CASE 
                    WHEN away_score > home_score THEN 'W'
                    WHEN away_score < home_score THEN 'L'
                    ELSE 'D'
                END
            FROM matches
            WHERE away_score IS NOT NULL
        )
    ),
    head_to_head AS (
        SELECT 
            home_team,
            away_team,
            AVG(home_score) as avg_h2h_home_goals,
            AVG(away_score) as avg_h2h_away_goals,
            COUNT(*) as h2h_matches,
            SUM(CASE WHEN home_score > away_score THEN 1 ELSE 0 END) as home_wins,
            SUM(CASE WHEN home_score = away_score THEN 1 ELSE 0 END) as draws,
            SUM(CASE WHEN home_score < away_score THEN 1 ELSE 0 END) as away_wins
        FROM matches
        WHERE home_score IS NOT NULL
        GROUP BY home_team, away_team
    )
    SELECT 
        m.id,
        m.home_team,
        m.away_team,
        m.home_score,
        m.away_score,
        m.date,
        
        -- Forme des équipes
        tf_home.form as home_team_form,
        tf_away.form as away_team_form,
        
        -- Statistiques mensuelles
        h_stats.avg_goals_scored as home_goals_scored_avg,
        h_stats.avg_goals_conceded as home_goals_conceded_avg,
        h_stats.wins as home_wins,
        h_stats.draws as home_draws,
        h_stats.losses as home_losses,
        
        a_stats.avg_goals_scored as away_goals_scored_avg,
        a_stats.avg_goals_conceded as away_goals_conceded_avg,
        a_stats.wins as away_wins,
        a_stats.draws as away_draws,
        a_stats.losses as away_losses,
        
        -- Séries de victoires/défaites
        ts_home.win_streak as home_win_streak,
        ts_home.loss_streak as home_loss_streak,
        ts_away.win_streak as away_win_streak,
        ts_away.loss_streak as away_loss_streak,
        
        -- Statistiques head-to-head
        COALESCE(h2h.avg_h2h_home_goals, 0) as avg_h2h_home_goals,
        COALESCE(h2h.avg_h2h_away_goals, 0) as avg_h2h_away_goals,
        COALESCE(h2h.h2h_matches, 0) as h2h_matches,
        COALESCE(h2h.home_wins, 0) as h2h_home_wins,
        COALESCE(h2h.draws, 0) as h2h_draws,
        COALESCE(h2h.away_wins, 0) as h2h_away_wins,
        
        -- Données météo
        sc.temperature as weather_temp,
        sc.precipitation as weather_rain,
        sc.wind_speed as weather_wind,
        
        -- Données joueurs
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
    LEFT JOIN match_stats h_stats ON 
        h_stats.team = m.home_team AND 
        h_stats.month = strftime('%Y-%m', m.date)
    LEFT JOIN match_stats a_stats ON 
        a_stats.team = m.away_team AND
        a_stats.month = strftime('%Y-%m', m.date)
    LEFT JOIN team_streaks ts_home ON 
        ts_home.team = m.home_team AND
        ts_home.date = m.date
    LEFT JOIN team_streaks ts_away ON 
        ts_away.team = m.away_team AND
        ts_away.date = m.date
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
    WHERE m.home_score IS NOT NULL 
    AND m.away_score IS NOT NULL
    ORDER BY m.date DESC
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def prepare_features(df):
    """Prépare et normalise les features"""
    # Convertir les colonnes de forme en valeurs numériques
    df['home_team_form'] = pd.to_numeric(df['home_team_form'], errors='coerce')
    df['away_team_form'] = pd.to_numeric(df['away_team_form'], errors='coerce')
    
    # Calculer les différences
    df['form_difference'] = df['home_team_form'] - df['away_team_form']
    df['goals_scored_diff'] = df['home_goals_scored_avg'] - df['away_goals_scored_avg']
    df['goals_conceded_diff'] = df['home_goals_conceded_avg'] - df['away_goals_conceded_avg']
    
    # Calculer les statistiques H2H
    df['h2h_goal_diff'] = df['avg_h2h_home_goals'] - df['avg_h2h_away_goals']
    df['h2h_experience'] = np.log1p(df['h2h_matches'])
    
    # Indicateurs de forme
    df['home_high_form'] = (df['home_team_form'] > df['home_team_form'].mean()).astype(int)
    df['away_high_form'] = (df['away_team_form'] > df['away_team_form'].mean()).astype(int)
    
    # Indicateurs de match européen
    df['home_european_match'] = 0
    df['away_european_match'] = 0
    
    # Remplir les valeurs manquantes
    fill_values = {
        'home_team_form': df['home_team_form'].mean(),
        'away_team_form': df['away_team_form'].mean(),
        'home_goals_scored_avg': df['home_goals_scored_avg'].mean(),
        'away_goals_scored_avg': df['away_goals_scored_avg'].mean(),
        'home_goals_conceded_avg': df['home_goals_conceded_avg'].mean(),
        'away_goals_conceded_avg': df['away_goals_conceded_avg'].mean(),
        'weather_temp': df['weather_temp'].mean(),
        'weather_rain': 0,
        'weather_wind': df['weather_wind'].mean(),
        'home_missing_key_players': 0,
        'away_missing_key_players': 0,
        'form_difference': 0,
        'goals_scored_diff': 0,
        'goals_conceded_diff': 0,
        'h2h_goal_diff': 0,
        'h2h_experience': 0,
        'home_high_form': 0,
        'away_high_form': 0,
        'home_european_match': 0,
        'away_european_match': 0
    }
    
    return df.fillna(fill_values)

def train_models(df):
    """Entraîne les modèles de prédiction avec validation croisée"""
    # Préparation des features
    X = df[FEATURES]
    y_home = df['home_score']
    y_away = df['away_score']
    
    # Normalisation des features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Configuration des modèles avec hyperparamètres optimisés
    params = {
        'n_estimators': 200,
        'learning_rate': 0.03,
        'max_depth': 5,
        'min_child_weight': 3,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'gamma': 0.1,
        'reg_alpha': 0.1,
        'reg_lambda': 1,
        'random_state': 42
    }
    
    # Validation croisée
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    
    # Modèle pour les buts à domicile
    model_home = XGBRegressor(**params)
    cv_scores_home = cross_val_score(model_home, X_scaled, y_home, cv=kf, scoring='neg_root_mean_squared_error')
    home_rmse = -cv_scores_home.mean()
    
    # Modèle pour les buts à l'extérieur
    model_away = XGBRegressor(**params)
    cv_scores_away = cross_val_score(model_away, X_scaled, y_away, cv=kf, scoring='neg_root_mean_squared_error')
    away_rmse = -cv_scores_away.mean()
    
    # Entraînement final sur toutes les données
    model_home.fit(X_scaled, y_home)
    model_away.fit(X_scaled, y_away)
    
    print(f"CV RMSE domicile : {home_rmse:.3f}")
    print(f"CV RMSE extérieur : {away_rmse:.3f}")
    print("Les scores proches du RMSE indiquent une bonne stabilité du modèle")
    
    return {
        'home': model_home,
        'away': model_away,
        'scaler': scaler,
        'features': FEATURES,
        'metrics': {
            'home_rmse': float(home_rmse),
            'away_rmse': float(away_rmse),
            'cv_scores_home': cv_scores_home.tolist(),
            'cv_scores_away': cv_scores_away.tolist()
        }
    }

def save_models(models, filename='enhanced_model.joblib'):
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
