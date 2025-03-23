import sqlite3
import pandas as pd
import numpy as np
import joblib
import os
import sys
import json
from datetime import datetime

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
    print("Préparation des features...")
    
    # Encodage des équipes
    all_teams = pd.concat([
        historical_matches['home_team'],
        historical_matches['away_team']
    ]).unique()
    team_to_id = {team: idx for idx, team in enumerate(all_teams)}
    
    # Features de base
    features = []
    for _, match in upcoming_matches.iterrows():
        home_team = match['home_team']
        away_team = match['away_team']
        
        if home_team not in team_stats:
            print(f"Attention: Pas de statistiques pour l'équipe à domicile {home_team}")
        if away_team not in team_stats:
            print(f"Attention: Pas de statistiques pour l'équipe à l'extérieur {away_team}")
        
        # Récupération des stats H2H
        h2h_key = f"{home_team}_vs_{away_team}"
        
        # Construction du dictionnaire avec le même ordre que dans train_model.py
        feature_dict = {
            # Statistiques générales
            'home_avg_scored': team_stats.get(home_team, {}).get('avg_goals_scored_home', 0),
            'home_avg_conceded': team_stats.get(home_team, {}).get('avg_goals_conceded_home', 0),
            'away_avg_scored': team_stats.get(away_team, {}).get('avg_goals_scored_away', 0),
            'away_avg_conceded': team_stats.get(away_team, {}).get('avg_goals_conceded_away', 0),
            
            # Statistiques récentes
            'home_recent_scored': team_stats.get(home_team, {}).get('recent_goals_scored_home', 0),
            'home_recent_conceded': team_stats.get(home_team, {}).get('recent_goals_conceded_home', 0),
            'away_recent_scored': team_stats.get(away_team, {}).get('recent_goals_scored_away', 0),
            'away_recent_conceded': team_stats.get(away_team, {}).get('recent_goals_conceded_away', 0),
            
            # Forme
            'home_form': team_stats.get(home_team, {}).get('form_home', 0),
            'away_form': team_stats.get(away_team, {}).get('form_away', 0),
            
            # H2H dans le même ordre que train_model.py
            'h2h_home_wins': team_stats.get(h2h_key, {}).get('home_wins', 0),
            'h2h_away_wins': team_stats.get(h2h_key, {}).get('away_wins', 0),
            'h2h_draws': team_stats.get(h2h_key, {}).get('draws', 0),
            'h2h_home_goals': team_stats.get(h2h_key, {}).get('home_goals', 0),
            'h2h_away_goals': team_stats.get(h2h_key, {}).get('away_goals', 0)
        }
        
        # Ajout des IDs d'équipe au début
        feature_dict = {
            'home_team_id': team_to_id.get(home_team, -1),
            'away_team_id': team_to_id.get(away_team, -1),
            **feature_dict
        }
        
        features.append(feature_dict)
    
    df = pd.DataFrame(features)
    print(f"Features générées: {list(df.columns)}")
    return df

def predict_upcoming():
    try:
        print("\n=== Début des prédictions ===")
        
        # 1. Charger le modèle
        print("\nChargement du modèle...")
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"Le modèle n'existe pas: {MODEL_PATH}. Veuillez d'abord entraîner le modèle.")
            
        model_data = joblib.load(MODEL_PATH)
        model_home = model_data['model_home']
        model_away = model_data['model_away']
        team_stats = model_data.get('team_stats', {})
        
        print(f"Modèle chargé, entraîné le: {model_data.get('training_date', 'date inconnue')}")
        
        # 2. Récupérer les matchs à venir
        print("\nRécupération des matchs à venir...")
        conn = sqlite3.connect(DB_PATH)
        upcoming_df = pd.read_sql_query(
            "SELECT DISTINCT fixture_id, date, round, home_team, away_team, home_score, away_score FROM matches WHERE home_score IS NULL ORDER BY date",
            conn
        )
        print(f"Nombre de matchs à prédire: {len(upcoming_df)}")

        if len(upcoming_df) == 0:
            print("Aucun match à venir trouvé.")
            print(json.dumps([]))
            return

        # 3. Récupérer l'historique
        print("\nRécupération de l'historique...")
        historical_df = get_historical_matches()
        print(f"Nombre de matchs historiques: {len(historical_df)}")
        
        # 4. Préparer les features
        X = prepare_features(upcoming_df, historical_df, team_stats)
        
        # 5. Faire les prédictions
        print("\nCalcul des prédictions...")
        home_pred = model_home.predict(X)
        away_pred = model_away.predict(X)
        
        # 6. Formater les résultats
        results = []
        for i, row in upcoming_df.iterrows():
            raw_home = float(home_pred[i])
            raw_away = float(away_pred[i])
            round_home = round(raw_home)
            round_away = round(raw_away)
            
            # Calcul des probabilités
            total_goals = raw_home + raw_away
            if total_goals > 0:
                win_prob = min(max(raw_home / total_goals * 100, 0), 100)
                draw_prob = 25  # Valeur arbitraire pour les matchs nuls
                lose_prob = min(max(raw_away / total_goals * 100, 0), 100)
            else:
                win_prob = draw_prob = lose_prob = 33.33

            # Calcul des valeurs de forme
            home_form = calculate_form(
                float(X['home_recent_scored'].iloc[i]),
                float(X['home_recent_conceded'].iloc[i])
            )
            away_form = calculate_form(
                float(X['away_recent_scored'].iloc[i]),
                float(X['away_recent_conceded'].iloc[i])
            )
            
            print(f"\n=== Debug match {row['home_team']} vs {row['away_team']} ===")
            print(f"Home recent scored: {X['home_recent_scored'].iloc[i]}")
            print(f"Home recent conceded: {X['home_recent_conceded'].iloc[i]}")
            print(f"Away recent scored: {X['away_recent_scored'].iloc[i]}")
            print(f"Away recent conceded: {X['away_recent_conceded'].iloc[i]}")
            print(f"Home form calculée: {home_form}")
            print(f"Away form calculée: {away_form}")

            match_result = {
                "fixture_id": int(row['fixture_id']),
                "date": row['date'],
                "round": row.get('round', 'N/A'),
                "home_team": row['home_team'],
                "away_team": row['away_team'],
                "predictions": {
                    "home_score": {
                        "raw": round(raw_home, 2),
                        "rounded": round_home
                    },
                    "away_score": {
                        "raw": round(raw_away, 2),
                        "rounded": round_away
                    }
                },
                "probabilities": {
                    "home_win": round(win_prob, 2),
                    "draw": round(draw_prob, 2),
                    "away_win": round(lose_prob, 2)
                },
                "confidence": {
                    "home_form": round(home_form, 2),
                    "away_form": round(away_form, 2)
                }
            }
            results.append(match_result)

        print(f"\nPrédictions générées pour {len(results)} matchs")
        print(json.dumps(results))

    except Exception as e:
        error_msg = {
            "error": str(e),
            "type": type(e).__name__,
            "timestamp": datetime.now().isoformat()
        }
        print(json.dumps(error_msg), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    predict_upcoming()
