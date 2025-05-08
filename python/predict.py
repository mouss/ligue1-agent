import sqlite3
import pandas as pd
import numpy as np
import joblib
import json
import os
import sys
from datetime import datetime
from features import FEATURES  # Import des features depuis le nouveau fichier

# Chemins des fichiers
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'db', 'ligue1.db')
MODEL_HOME_PATH = os.path.join(os.path.dirname(__file__), 'model_new_home')
MODEL_AWAY_PATH = os.path.join(os.path.dirname(__file__), 'model_new_away')

# Liste des features utilisées pour la prédiction (correspond au modèle entraîné)
# FEATURES = [
#     'home_team_form', 'away_team_form',
#     'home_goals_scored_avg', 'away_goals_scored_avg',
#     'home_goals_conceded_avg', 'away_goals_conceded_avg',
#     'weather_temp', 'weather_rain', 'weather_wind',
#     'home_european', 'away_european',
#     'home_fatigue', 'away_fatigue'
# ]

def log(message):
    """Écrit les logs sur stderr pour ne pas interférer avec la sortie JSON"""
    print(message, file=sys.stderr)

def get_matches():
    """Récupère les matchs de la base de données"""
    conn = sqlite3.connect(DB_PATH)
    query = """
    WITH unique_matches AS (
        -- Sélectionner d'abord un seul ID par match et par date exacte
        SELECT MIN(id) as id
        FROM matches
        WHERE datetime(date) >= datetime('now')
        GROUP BY home_team, away_team, datetime(date)
    )
    SELECT 
        m.id,
        m.home_team,
        m.away_team,
        m.home_score,
        m.away_score,
        datetime(m.date) as date,
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
    INNER JOIN unique_matches um ON m.id = um.id
    LEFT JOIN stadium_conditions sc ON datetime(m.date) = datetime(sc.match_date)
    LEFT JOIN european_matches em_home ON (
        m.home_team = em_home.team
        AND date(em_home.match_date) BETWEEN date(m.date, '-7 days') AND date(m.date)
    )
    LEFT JOIN european_matches em_away ON (
        m.away_team = em_away.team
        AND date(em_away.match_date) BETWEEN date(m.date, '-7 days') AND date(m.date)
    )
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

def get_team_stats(team):
    """Récupère les statistiques d'une équipe"""
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT 
            AVG(home_score) as goals_scored_avg,
            AVG(away_score) as goals_conceded_avg,
            COUNT(*) as total_matches
        FROM matches
        WHERE home_team = ? OR away_team = ?
    """
    cursor = conn.cursor()
    cursor.execute(query, [team, team])
    stats = cursor.fetchone()
    conn.close()
    return pd.DataFrame([stats], columns=['goals_scored_avg', 'goals_conceded_avg', 'total_matches'])

def prepare_features(upcoming_matches, historical_matches):
    """Prépare les features pour les matchs à venir"""
    df = pd.DataFrame()
    
    # Colonnes requises pour les matchs historiques
    required_columns = ['id', 'home_team', 'away_team', 'home_score', 'away_score', 'date']
    
    # Vérifier que toutes les colonnes requises sont présentes
    missing_columns = [col for col in required_columns if col not in historical_matches.columns]
    if missing_columns:
        raise ValueError(f"Colonnes manquantes dans historical_matches: {missing_columns}")
    
    # Convertir les dates en datetime si ce n'est pas déjà fait et gérer les fuseaux horaires
    historical_matches['date'] = pd.to_datetime(historical_matches['date'], format='mixed', utc=True)
    upcoming_matches['date'] = pd.to_datetime(upcoming_matches['date'], format='mixed', utc=True)
    
    # Pour chaque match à venir
    for _, match in upcoming_matches.iterrows():
        home_team = match['home_team']
        away_team = match['away_team']
        match_date = match['date']
        
        # Filtrer les matchs historiques avant la date du match
        past_matches = historical_matches[historical_matches['date'] < match_date].copy()
        
        if past_matches.empty:
            log(f"Attention: Aucun match historique trouvé avant {match_date}")
            continue
        
        # Calculer les statistiques pour l'équipe à domicile
        home_stats = calculate_weighted_stats(past_matches, home_team, True)
        
        # Calculer les statistiques pour l'équipe à l'extérieur
        away_stats = calculate_weighted_stats(past_matches, away_team, False)
        
        # Créer une ligne de données avec toutes les features
        row = {
            'home_team': home_team,
            'away_team': away_team,
            'home_team_form': home_stats['form'],
            'away_team_form': away_stats['form'],
            'home_goals_scored_avg': home_stats['goals_scored_avg'],
            'away_goals_scored_avg': away_stats['goals_scored_avg'],
            'home_goals_conceded_avg': home_stats['goals_conceded_avg'],
            'away_goals_conceded_avg': away_stats['goals_conceded_avg']
        }
        
        # Ajouter les features météo et européennes si disponibles
        if 'weather_temp' in match:
            row.update({
                'weather_temp': match['weather_temp'] if pd.notna(match['weather_temp']) else 0,
                'weather_rain': match['weather_rain'] if pd.notna(match['weather_rain']) else 0,
                'weather_wind': match['weather_wind'] if pd.notna(match['weather_wind']) else 0
            })
        
        if 'home_european_match' in match:
            row.update({
                'home_european': match['home_european_match'] if pd.notna(match['home_european_match']) else 0,
                'away_european': match['away_european_match'] if pd.notna(match['away_european_match']) else 0,
                'home_fatigue': match['home_team_fatigue'] if pd.notna(match['home_team_fatigue']) else 0,
                'away_fatigue': match['away_team_fatigue'] if pd.notna(match['away_team_fatigue']) else 0
            })
        
        # Ajouter la ligne au DataFrame
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    
    # Remplir les valeurs manquantes par 0
    df = df.fillna(0)
    
    # S'assurer que toutes les features nécessaires sont présentes
    for feature in FEATURES:
        if feature not in df.columns:
            log(f"Feature manquante: {feature}, ajout avec valeur 0")
            df[feature] = 0
    
    return df[['home_team', 'away_team'] + FEATURES]

def calculate_weighted_stats(matches, team, is_home):
    """Calcule les statistiques pondérées pour une équipe"""
    # Filtrer les matchs de l'équipe
    team_matches = matches[
        ((matches['home_team'] == team) & is_home) |
        ((matches['away_team'] == team) & ~is_home)
    ].copy()
    
    if team_matches.empty:
        return {
            'form': 0,
            'goals_scored_avg': 0,
            'goals_conceded_avg': 0
        }
    
    # Trier par date décroissante et limiter aux 10 derniers matchs
    team_matches = team_matches.sort_values('date', ascending=False).head(10)
    
    # Calculer les buts marqués et encaissés
    goals_scored = []
    goals_conceded = []
    goal_differences = []
    
    for _, match in team_matches.iterrows():
        if (match['home_team'] == team and is_home) or (match['away_team'] == team and not is_home):
            goals_for = match['home_score'] if match['home_team'] == team else match['away_score']
            goals_against = match['away_score'] if match['home_team'] == team else match['home_score']
            
            goals_scored.append(goals_for)
            goals_conceded.append(goals_against)
            goal_differences.append(goals_for - goals_against)
    
    # Calculer les moyennes pondérées (plus de poids aux matchs récents)
    # Augmenter le facteur de décroissance pour donner plus d'importance aux matchs récents
    weights = np.exp(-np.arange(len(team_matches)) * 0.5)  # Facteur de décroissance plus important
    weights = weights / weights.sum()  # Normalisation des poids
    
    goals_scored_avg = np.average(goals_scored, weights=weights) if goals_scored else 0
    goals_conceded_avg = np.average(goals_conceded, weights=weights) if goals_conceded else 0
    
    # Calculer la forme (basée sur la différence de buts pondérée)
    form = np.average(goal_differences, weights=weights) if goal_differences else 0
    
    # Ajuster la forme en fonction de la moyenne de buts marqués et encaissés
    form = form * (1 + goals_scored_avg / (goals_conceded_avg + 1))
    
    return {
        'form': form,
        'goals_scored_avg': goals_scored_avg,
        'goals_conceded_avg': goals_conceded_avg
    }

def normalize_score(score, match_id):
    """Convertit un score prédit en utilisant une distribution de Poisson"""
    from scipy.stats import poisson
    import numpy as np
    import random
    
    # Utiliser la prédiction comme lambda (moyenne) de la distribution
    lambda_param = max(0, min(5, float(score)))  # Limiter entre 0 et 5 pour plus de réalisme
    
    # Utiliser l'ID du match et un nombre aléatoire comme graine
    # pour avoir des scores cohérents mais pas trop de matchs nuls
    np.random.seed(match_id + random.randint(0, 1000))
    
    # Ajuster légèrement le lambda pour réduire les matchs nuls
    if random.random() < 0.7:  # 70% de chance d'ajuster
        lambda_param *= random.uniform(0.8, 1.2)
    
    return int(poisson.rvs(lambda_param))

def predict_scores():
    """Prédit les scores des matchs à venir"""
    try:
        # Chargement des données
        log("Chargement des données...")
        matches = get_matches()
        
        # Récupérer tous les matchs historiques, même ceux avant aujourd'hui
        conn = sqlite3.connect(DB_PATH)
        historical_query = """
        SELECT DISTINCT
            id, home_team, away_team, home_score, away_score, datetime(date) as date
        FROM matches 
        WHERE home_score IS NOT NULL 
        AND away_score IS NOT NULL
        ORDER BY date DESC
        """
        historical_matches = pd.read_sql_query(historical_query, conn)
        conn.close()
        
        # Filtrer les matchs à venir
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
        
        # Régularisation manuelle des scores
        home_scores = np.clip(home_scores, 0, 5)  # Augmenter la limite à 5 buts
        away_scores = np.clip(away_scores, 0, 5)
        
        # Préparation des résultats
        predictions = []
        for i, (_, match) in enumerate(upcoming_matches.iterrows()):
            # Normalisation des scores prédits avec l'ID du match
            pred_home = normalize_score(home_scores[i], int(match['id']))
            pred_away = normalize_score(away_scores[i], int(match['id']))
            
            prediction = {
                'match_id': int(match['id']),
                'home_team': str(match['home_team']),
                'away_team': str(match['away_team']),
                'predicted_home_score': pred_home,
                'predicted_away_score': pred_away,
                'date': str(match['date']),
                'weather': {
                    'temperature': float(match['weather_temp']) if pd.notna(match['weather_temp']) else None,
                    'precipitation': float(match['weather_rain']) if pd.notna(match['weather_rain']) else None,
                    'wind_speed': float(match['weather_wind']) if pd.notna(match['weather_wind']) else None,
                    'condition': str(match['weather_condition']) if pd.notna(match['weather_condition']) else None
                },
                'european_context': {
                    'home_team_european': bool(match['home_european_match']) if pd.notna(match['home_european_match']) else False,
                    'away_team_european': bool(match['away_european_match']) if pd.notna(match['away_european_match']) else False,
                    'home_team_fatigue': bool(match['home_team_fatigue']) if pd.notna(match['home_team_fatigue']) else False,
                    'away_team_fatigue': bool(match['away_team_fatigue']) if pd.notna(match['away_team_fatigue']) else False,
                    'home_competition': str(match['home_european_competition']) if pd.notna(match['home_european_competition']) else None,
                    'away_competition': str(match['away_european_competition']) if pd.notna(match['away_european_competition']) else None
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
