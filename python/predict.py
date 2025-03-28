import sqlite3
import pandas as pd
import numpy as np
import joblib
import os
import sys
import json
import warnings
from datetime import datetime

# Filtrer tous les warnings de dépreciation
warnings.filterwarnings('ignore', category=FutureWarning)

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'ligue1.db')
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'ligue1_model.pkl')

def get_historical_matches():
    """Récupère les matchs historiques pour calculer les stats"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT * FROM matches WHERE home_score IS NOT NULL ORDER BY date",
        conn
    )
    conn.close()
    return df

def calculate_form(recent_scored, recent_conceded):
    """Calcule un score de forme basé sur les buts récents"""
    if recent_scored is None or recent_conceded is None:
        return 50  # Valeur par défaut si pas de données
    
    # Calcul du ratio buts marqués/encaissés
    total = recent_scored + recent_conceded
    if total == 0:
        return 50  # Valeur par défaut si pas de buts
        
    # Score basé sur le ratio de buts, normalisé entre 0 et 100
    form = (recent_scored / total) * 100
    return max(min(form, 100), 0)  # Garantit une valeur entre 0 et 100

def prepare_features(upcoming_matches, historical_matches, team_stats):
    """Prépare les features pour les matchs à venir"""
    # Encodage des équipes
    all_teams = pd.concat([
        historical_matches['home_team'],
        historical_matches['away_team']
    ]).unique()
    team_to_id = {team: idx for idx, team in enumerate(all_teams)}
    
    # Features de base
    features = []
    warnings = []
    for _, match in upcoming_matches.iterrows():
        home_team = match['home_team']
        away_team = match['away_team']
        
        if home_team not in team_stats:
            warnings.append(f"Pas de statistiques pour l'équipe à domicile {home_team}")
        if away_team not in team_stats:
            warnings.append(f"Pas de statistiques pour l'équipe à l'extérieur {away_team}")
        
        # Récupération des stats H2H
        h2h_key = f"{home_team}_vs_{away_team}"
        
        # Construction du dictionnaire avec le même ordre que dans train_model.py
        feature_dict = {
            'home_team_id': team_to_id.get(home_team, -1),
            'away_team_id': team_to_id.get(away_team, -1),
            'id': match.get('id', 0),
            'fixture_id': match.get('fixture_id', 0),
            'home_key_players_missing': 0,
            'away_key_players_missing': 0,
            'home_fatigue': 50,
            'away_fatigue': 50,
            'home_total_players_missing': 0,
            'away_total_players_missing': 0,
            'home_avg_scored': team_stats.get(home_team, {}).get('avg_goals_scored_home', 0),
            'home_avg_conceded': team_stats.get(home_team, {}).get('avg_goals_conceded_home', 0),
            'away_avg_scored': team_stats.get(away_team, {}).get('avg_goals_scored_away', 0),
            'away_avg_conceded': team_stats.get(away_team, {}).get('avg_goals_conceded_away', 0),
            'home_recent_scored': team_stats.get(home_team, {}).get('recent_goals_scored_home', 0),
            'home_recent_conceded': team_stats.get(home_team, {}).get('recent_goals_conceded_home', 0),
            'away_recent_scored': team_stats.get(away_team, {}).get('recent_goals_scored_away', 0),
            'away_recent_conceded': team_stats.get(away_team, {}).get('recent_goals_conceded_away', 0),
            'home_form': team_stats.get(home_team, {}).get('form_home', 0),
            'away_form': team_stats.get(away_team, {}).get('form_away', 0),
            'h2h_home_wins': team_stats.get(h2h_key, {}).get('home_wins', 0),
            'h2h_away_wins': team_stats.get(h2h_key, {}).get('away_wins', 0),
            'h2h_draws': team_stats.get(h2h_key, {}).get('draws', 0),
            'h2h_home_goals': team_stats.get(h2h_key, {}).get('home_goals', 0),
            'h2h_away_goals': team_stats.get(h2h_key, {}).get('away_goals', 0)
        }
        
        features.append(feature_dict)
    
    df = pd.DataFrame(features)
    
    # S'assurer que toutes les colonnes sont présentes et dans le bon ordre
    expected_columns = [
        'home_team_id', 'away_team_id', 'id', 'fixture_id',
        'home_key_players_missing', 'away_key_players_missing',
        'home_fatigue', 'away_fatigue',
        'home_total_players_missing', 'away_total_players_missing',
        'home_avg_scored', 'home_avg_conceded',
        'away_avg_scored', 'away_avg_conceded',
        'home_recent_scored', 'home_recent_conceded',
        'away_recent_scored', 'away_recent_conceded',
        'home_form', 'away_form',
        'h2h_home_wins', 'h2h_away_wins', 'h2h_draws',
        'h2h_home_goals', 'h2h_away_goals'
    ]
    
    # Réorganiser les colonnes dans le bon ordre
    df = df.reindex(columns=expected_columns)
    
    # Convertir les colonnes en types appropriés
    for col in df.columns:
        if not is_valid_dtype(df[col].dtype):
            df[col] = pd.to_numeric(df[col], errors='coerce')
            if df[col].isna().any():
                warnings.append(f"Valeurs non numériques dans la colonne {col}")
    
    return df, warnings

def save_predictions_to_db(predictions):
    """Sauvegarde les prédictions dans la base de données"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Mise à jour des prédictions existantes
    for pred in predictions:
        cursor.execute("""
            INSERT OR REPLACE INTO predictions (
                fixture_id, date, round, home_team, away_team,
                home_score_pred, away_score_pred,
                home_win_prob, draw_prob, away_win_prob,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pred['fixture_id'],
            pred['date'],
            pred['round'],
            pred['home_team'],
            pred['away_team'],
            pred['predictions']['home_score']['raw'],
            pred['predictions']['away_score']['raw'],
            pred['probabilities']['home_win'],
            pred['probabilities']['draw'],
            pred['probabilities']['away_win'],
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))
    
    conn.commit()
    conn.close()

def predict_upcoming():
    """Fait des prédictions sur les matchs à venir"""
    try:
        # Structure de réponse
        response = {
            "status": "success",
            "predictions": [],
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "model_training_date": None,
                "total_matches": 0,
                "warnings": []
            }
        }

        # 1. Charger le modèle
        if not os.path.exists(MODEL_PATH):
            return {
                "status": "error",
                "error": f"Le modèle n'existe pas: {MODEL_PATH}",
                "type": "FileNotFoundError",
                "timestamp": datetime.now().isoformat()
            }
            
        model_data = joblib.load(MODEL_PATH)
        model_home = model_data['model_home']
        model_away = model_data['model_away']
        team_stats = model_data.get('team_stats', {})
        
        response["metadata"]["model_training_date"] = model_data.get('training_date', 'date inconnue')
        
        # 2. Récupérer les matchs à venir
        conn = sqlite3.connect(DB_PATH)
        upcoming_df = pd.read_sql_query(
            "SELECT DISTINCT fixture_id, date, round, home_team, away_team, home_score, away_score FROM matches WHERE home_score IS NULL ORDER BY date",
            conn
        )
        response["metadata"]["total_matches"] = len(upcoming_df)

        if len(upcoming_df) == 0:
            response["status"] = "success"
            response["message"] = "Aucun match à venir trouvé"
            return response

        # 3. Récupérer l'historique
        historical_df = get_historical_matches()
        
        # 4. Préparer les features
        X, warnings = prepare_features(upcoming_df, historical_df, team_stats)
        response["metadata"]["warnings"].extend(warnings)
        
        # 5. Faire les prédictions
        home_pred = model_home.predict(X)
        away_pred = model_away.predict(X)
        
        # 6. Formater les résultats
        for i, row in upcoming_df.iterrows():
            try:
                raw_home = max(0, float(home_pred[i]))
                raw_away = max(0, float(away_pred[i]))
                round_home = round(raw_home)
                round_away = round(raw_away)
                
                # Calcul des probabilités
                total_goals = raw_home + raw_away
                if total_goals > 0:
                    win_prob = min(max(raw_home / total_goals * 100, 0), 100)
                    draw_prob = 25
                    lose_prob = min(max(raw_away / total_goals * 100, 0), 100)
                    
                    # Normaliser les probabilités
                    total_prob = win_prob + draw_prob + lose_prob
                    if total_prob > 0:
                        win_prob = (win_prob / total_prob) * 100
                        draw_prob = (draw_prob / total_prob) * 100
                        lose_prob = (lose_prob / total_prob) * 100
                else:
                    win_prob = draw_prob = lose_prob = 33.33

                match_result = {
                    "fixture_id": int(row['fixture_id']),
                    "date": str(row['date']),
                    "round": str(row.get('round', 'N/A')),
                    "home_team": str(row['home_team']),
                    "away_team": str(row['away_team']),
                    "predictions": {
                        "home_score": {
                            "raw": float(round(raw_home, 2)),
                            "rounded": int(round_home)
                        },
                        "away_score": {
                            "raw": float(round(raw_away, 2)),
                            "rounded": int(round_away)
                        }
                    },
                    "probabilities": {
                        "home_win": float(round(win_prob, 2)),
                        "draw": float(round(draw_prob, 2)),
                        "away_win": float(round(lose_prob, 2))
                    }
                }
                
                response["predictions"].append(match_result)
            except Exception as e:
                response["metadata"]["warnings"].append({
                    "match": f"{row['home_team']} vs {row['away_team']}",
                    "error": str(e)
                })
                continue
        
        # Sauvegarder les prédictions dans la base de données
        try:
            save_predictions_to_db(response["predictions"])
        except Exception as e:
            response["metadata"]["warnings"].append({
                "type": "database",
                "error": str(e)
            })
        
        return response
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "type": type(e).__name__,
            "timestamp": datetime.now().isoformat()
        }

def predict_historical(start_date=None, end_date=None):
    """Fait des prédictions sur les matchs historiques pour évaluation"""
    try:
        response = {
            "status": "success",
            "predictions": [],
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "total_matches": 0,
                "warnings": []
            }
        }
        
        # 1. Charger le modèle
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"Le modèle n'existe pas: {MODEL_PATH}")
            
        model_data = joblib.load(MODEL_PATH)
        model_home = model_data['model_home']
        model_away = model_data['model_away']
        team_stats = model_data.get('team_stats', {})
        
        # 2. Récupérer les matchs historiques
        conn = sqlite3.connect(DB_PATH)
        query = """
            SELECT DISTINCT fixture_id, date, round, home_team, away_team, 
                   home_score, away_score 
            FROM matches 
            WHERE home_score IS NOT NULL
        """
        params = []
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
            
        query += " ORDER BY date"
        
        historical_df = pd.read_sql_query(query, conn, params=params)
        response["metadata"]["total_matches"] = len(historical_df)
        
        if len(historical_df) == 0:
            response["status"] = "success"
            response["message"] = "Aucun match historique trouvé"
            return response
            
        # 3. Préparer les features
        X, warnings = prepare_features(historical_df, historical_df, team_stats)
        response["metadata"]["warnings"].extend(warnings)
        
        # 4. Faire les prédictions
        home_pred = model_home.predict(X)
        away_pred = model_away.predict(X)
        
        # 5. Formater les résultats
        for i, row in historical_df.iterrows():
            try:
                raw_home = max(0, float(home_pred[i]))
                raw_away = max(0, float(away_pred[i]))
                round_home = round(raw_home)
                round_away = round(raw_away)
                
                actual_home = int(row['home_score'])
                actual_away = int(row['away_score'])
                
                match_result = {
                    "fixture_id": int(row['fixture_id']),
                    "date": str(row['date']),
                    "round": str(row.get('round', 'N/A')),
                    "home_team": str(row['home_team']),
                    "away_team": str(row['away_team']),
                    "predictions": {
                        "home_score": {
                            "raw": float(round(raw_home, 2)),
                            "rounded": int(round_home)
                        },
                        "away_score": {
                            "raw": float(round(raw_away, 2)),
                            "rounded": int(round_away)
                        }
                    },
                    "actual": {
                        "home_score": actual_home,
                        "away_score": actual_away
                    }
                }
                
                response["predictions"].append(match_result)
            except Exception as e:
                response["metadata"]["warnings"].append({
                    "match": f"{row['home_team']} vs {row['away_team']}",
                    "error": str(e)
                })
                continue
        
        # Sauvegarder les prédictions dans la base de données
        try:
            save_predictions_to_db(response["predictions"])
        except Exception as e:
            response["metadata"]["warnings"].append({
                "type": "database",
                "error": str(e)
            })
        
        return response
        
    except Exception as e:
        error_response = {
            "status": "error",
            "error": str(e),
            "type": type(e).__name__,
            "timestamp": datetime.now().isoformat()
        }
        return error_response

def is_valid_dtype(dtype):
    return dtype in ['int64', 'float64']

if __name__ == "__main__":
    response = predict_upcoming()
    print("DEBUG - Response structure:", file=sys.stderr)
    print(json.dumps(response, indent=2, ensure_ascii=False, default=str), file=sys.stderr)
    print("DEBUG - First prediction:", file=sys.stderr)
    if response.get("predictions"):
        print(json.dumps(response["predictions"][0], indent=2, ensure_ascii=False, default=str), file=sys.stderr)
    print("DEBUG - End debug", file=sys.stderr)
    print(json.dumps(response, ensure_ascii=False, default=str))
