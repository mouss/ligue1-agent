import sqlite3
import pandas as pd
import numpy as np
from xgboost import XGBRegressor
import joblib
import os
import json
import sys

# Chemins des fichiers
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'db', 'ligue1.db')
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'enhanced_model.joblib')

# Liste des features utilisées pour la prédiction (doit être identique à train_model.py)
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

def get_matches():
    """Récupère les matchs avec les statistiques nécessaires"""
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
    latest_stats AS (
        SELECT 
            team,
            avg_goals_scored,
            avg_goals_conceded,
            matches_played,
            wins,
            draws,
            losses
        FROM match_stats
        WHERE month = (
            SELECT MAX(month)
            FROM match_stats
        )
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
    ),
    recent_matches AS (
        SELECT 
            team,
            COUNT(*) as matches_last_14_days,
            julianday('now') - julianday(MAX(date)) as days_since_last_match
        FROM (
            SELECT home_team as team, date FROM matches
            UNION ALL
            SELECT away_team as team, date FROM matches
        )
        WHERE julianday('now') - julianday(date) <= 14
        GROUP BY team
    ),
    unique_matches AS (
        SELECT 
            MIN(m.id) as id,
            m.home_team,
            m.away_team,
            m.date,
            m.home_score,
            m.away_score,
            
            -- Forme des équipes
            COALESCE(h_stats.wins * 3 + h_stats.draws, 0) / NULLIF(h_stats.matches_played, 0) as home_team_form,
            COALESCE(a_stats.wins * 3 + a_stats.draws, 0) / NULLIF(a_stats.matches_played, 0) as away_team_form,
            
            -- Statistiques de buts
            COALESCE(h_stats.avg_goals_scored, 0) as home_goals_scored_avg,
            COALESCE(a_stats.avg_goals_scored, 0) as away_goals_scored_avg,
            COALESCE(h_stats.avg_goals_conceded, 0) as home_goals_conceded_avg,
            COALESCE(a_stats.avg_goals_conceded, 0) as away_goals_conceded_avg,
            
            -- Météo (valeurs par défaut)
            20 as weather_temp,
            0 as weather_rain,
            10 as weather_wind,
            
            -- Joueurs clés absents (valeurs par défaut)
            0 as home_missing_key_players,
            0 as away_missing_key_players,
            
            -- Statistiques head-to-head
            COALESCE(h2h.avg_h2h_home_goals, 0) as avg_h2h_home_goals,
            COALESCE(h2h.avg_h2h_away_goals, 0) as avg_h2h_away_goals,
            COALESCE(h2h.h2h_matches, 0) as h2h_matches,
            
            -- Séries de victoires/défaites
            COALESCE(h_streak.win_streak, 0) as home_win_streak,
            COALESCE(h_streak.loss_streak, 0) as home_loss_streak,
            COALESCE(a_streak.win_streak, 0) as away_win_streak,
            COALESCE(a_streak.loss_streak, 0) as away_loss_streak,
            
            -- Fatigue et charge de match
            COALESCE(h_recent.matches_last_14_days, 0) as home_matches_last_14_days,
            COALESCE(h_recent.days_since_last_match, 14) as home_days_since_last_match,
            COALESCE(a_recent.matches_last_14_days, 0) as away_matches_last_14_days,
            COALESCE(a_recent.days_since_last_match, 14) as away_days_since_last_match
            
        FROM matches m
        LEFT JOIN latest_stats h_stats ON m.home_team = h_stats.team
        LEFT JOIN latest_stats a_stats ON m.away_team = a_stats.team
        LEFT JOIN head_to_head h2h ON m.home_team = h2h.home_team AND m.away_team = h2h.away_team
        LEFT JOIN team_streaks h_streak ON m.home_team = h_streak.team AND m.date = h_streak.date
        LEFT JOIN team_streaks a_streak ON m.away_team = a_streak.team AND m.date = a_streak.date
        LEFT JOIN recent_matches h_recent ON m.home_team = h_recent.team
        LEFT JOIN recent_matches a_recent ON m.away_team = a_recent.team
        WHERE m.home_score IS NULL
        GROUP BY m.home_team, m.away_team, m.date
    )
    SELECT * FROM unique_matches
    ORDER BY date ASC;
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    return df

def prepare_features(df):
    """Prépare les features pour la prédiction"""
    # Différence de forme
    df['form_difference'] = df['home_team_form'] - df['away_team_form']
    
    # Différence de buts marqués/encaissés
    df['goals_scored_diff'] = df['home_goals_scored_avg'] - df['away_goals_scored_avg']
    df['goals_conceded_diff'] = df['home_goals_conceded_avg'] - df['away_goals_conceded_avg']
    
    # Statistiques head-to-head
    df['h2h_goal_diff'] = df['avg_h2h_home_goals'] - df['avg_h2h_away_goals']
    df['h2h_experience'] = np.log1p(df['h2h_matches'])
    
    # Indicateurs de forme
    df['home_high_form'] = (df['home_team_form'] > df['home_team_form'].mean()).astype(int)
    df['away_high_form'] = (df['away_team_form'] > df['away_team_form'].mean()).astype(int)
    
    # Indicateurs de match européen (par défaut à 0)
    df['home_european_match'] = 0
    df['away_european_match'] = 0
    
    # Calcul des indices de fatigue
    df['home_fatigue_index'] = (df['home_matches_last_14_days'] / 14) * (14 / (df['home_days_since_last_match'] + 1))
    df['away_fatigue_index'] = (df['away_matches_last_14_days'] / 14) * (14 / (df['away_days_since_last_match'] + 1))
    
    # Remplir les valeurs manquantes avec des valeurs par défaut
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
        'away_european_match': 0,
        'home_fatigue_index': 0,
        'away_fatigue_index': 0
    }
    
    return df.fillna(fill_values)

def predict_scores():
    """Prédit les scores des prochains matchs"""
    try:
        print("Chargement des données...")
        # Charger le modèle
        model = joblib.load(MODEL_PATH)
        print("Chargement du modèle...")
        
        # Charger et préparer les données
        matches = get_matches()
        upcoming_matches = matches[matches['home_score'].isnull()].copy()
        
        if upcoming_matches.empty:
            return []
        
        print("Préparation des features...")
        # Préparer les features
        upcoming_matches = prepare_features(upcoming_matches)
        
        # Sélectionner les features dans le même ordre que l'entraînement
        X = upcoming_matches[FEATURES].copy()
        
        print("Prédiction des scores...")
        # Normaliser les features
        X_scaled = model['scaler'].transform(X)
        
        # Prédire les scores
        home_predictions = model['home'].predict(X_scaled)
        away_predictions = model['away'].predict(X_scaled)
        
        # Ajuster les scores pour qu'ils soient positifs et réalistes
        home_predictions = np.maximum(0, home_predictions + 1)
        away_predictions = np.maximum(0, away_predictions + 1)
        
        # Arrondir les prédictions à 2 décimales
        predictions = []
        for idx, (i, match) in enumerate(upcoming_matches.iterrows()):
            home_score = round(float(home_predictions[idx]), 2)
            away_score = round(float(away_predictions[idx]), 2)
            
            # Calculer la confiance
            confidence = 0.6  # Confiance de base
            
            # Ajuster la confiance en fonction de la différence de score
            score_diff = abs(home_score - away_score)
            confidence += min(0.15, score_diff * 0.05)
            
            predictions.append({
                'id': int(match.id),
                'home_team': match.home_team,
                'away_team': match.away_team,
                'date': match.date,
                'predicted_home_score': home_score,
                'predicted_away_score': away_score,
                'confidence': round(min(0.85, confidence), 2)
            })
        
        # Trier par date
        predictions.sort(key=lambda x: x['date'])
        
        return predictions
        
    except Exception as e:
        print(f"Erreur lors de la prédiction : {str(e)}", file=sys.stderr)
        return {"error": str(e)}

if __name__ == "__main__":
    predictions = predict_scores()
    print(json.dumps(predictions, indent=2))
