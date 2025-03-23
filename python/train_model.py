import sqlite3
import pandas as pd
import numpy as np
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.metrics import mean_squared_error, mean_absolute_error
import joblib
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'ligue1.db')
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'ligue1_model.pkl')

def calculate_recent_form(matches, team, n_matches=5):
    """Calcule la forme récente d'une équipe sur les n derniers matchs"""
    team_home = matches[matches['home_team'] == team].sort_values('date', ascending=False)
    team_away = matches[matches['away_team'] == team].sort_values('date', ascending=False)
    
    recent_matches = pd.concat([team_home, team_away]).sort_values('date', ascending=False).head(n_matches)
    
    if len(recent_matches) == 0:
        return 0
    
    form = 0
    for _, match in recent_matches.iterrows():
        if match['home_team'] == team:
            if match['home_score'] > match['away_score']:
                form += 3
            elif match['home_score'] == match['away_score']:
                form += 1
        else:
            if match['away_score'] > match['home_score']:
                form += 3
            elif match['home_score'] == match['away_score']:
                form += 1
    
    return form / (n_matches * 3)  # Normalisation entre 0 et 1

def get_h2h_stats(matches, team1, team2, n_matches=5):
    """Calcule les statistiques des confrontations directes"""
    h2h_matches = matches[
        ((matches['home_team'] == team1) & (matches['away_team'] == team2)) |
        ((matches['home_team'] == team2) & (matches['away_team'] == team1))
    ].sort_values('date', ascending=False).head(n_matches)
    
    if len(h2h_matches) == 0:
        return {
            'team1_wins': 0,
            'team2_wins': 0,
            'draws': 0,
            'team1_goals_avg': 0,
            'team2_goals_avg': 0
        }
    
    team1_wins = team1_draws = team1_goals = team2_wins = team2_goals = 0
    
    for _, match in h2h_matches.iterrows():
        if match['home_team'] == team1:
            if match['home_score'] > match['away_score']:
                team1_wins += 1
            elif match['home_score'] == match['away_score']:
                team1_draws += 1
            team1_goals += match['home_score']
            team2_goals += match['away_score']
        else:
            if match['away_score'] > match['home_score']:
                team1_wins += 1
            elif match['home_score'] == match['away_score']:
                team1_draws += 1
            team1_goals += match['away_score']
            team2_goals += match['home_score']
    
    n = len(h2h_matches)
    return {
        'team1_wins': team1_wins / n,
        'team2_wins': (n - team1_wins - team1_draws) / n,
        'draws': team1_draws / n,
        'team1_goals_avg': team1_goals / n,
        'team2_goals_avg': team2_goals / n
    }

def calculate_team_stats(df):
    """Calcule les statistiques des équipes avec fenêtre glissante"""
    stats = {}
    
    for team in pd.concat([df['home_team'], df['away_team']]).unique():
        # Matchs récents (3 derniers mois)
        recent_date = df['date'].max() - timedelta(days=90)
        recent_matches = df[df['date'] >= recent_date]
        
        # Matchs à domicile
        home_matches = df[df['home_team'] == team]
        recent_home = recent_matches[recent_matches['home_team'] == team]
        
        # Matchs à l'extérieur
        away_matches = df[df['away_team'] == team]
        recent_away = recent_matches[recent_matches['away_team'] == team]
        
        if len(home_matches) > 0 and len(away_matches) > 0:
            stats[team] = {
                'avg_goals_scored_home': home_matches['home_score'].mean(),
                'avg_goals_conceded_home': home_matches['away_score'].mean(),
                'avg_goals_scored_away': away_matches['away_score'].mean(),
                'avg_goals_conceded_away': away_matches['home_score'].mean(),
                'recent_goals_scored_home': recent_home['home_score'].mean() if len(recent_home) > 0 else 0,
                'recent_goals_conceded_home': recent_home['away_score'].mean() if len(recent_home) > 0 else 0,
                'recent_goals_scored_away': recent_away['away_score'].mean() if len(recent_away) > 0 else 0,
                'recent_goals_conceded_away': recent_away['home_score'].mean() if len(recent_away) > 0 else 0,
                'form': calculate_recent_form(df, team)
            }
    
    return stats

def get_player_availability(team, date):
    """
    Récupère les informations sur les joueurs indisponibles
    À implémenter avec l'API RapidAPI Football
    """
    try:
        # Appel API RapidAPI pour obtenir les blessures/suspensions
        # À adapter selon votre clé API et endpoint
        return {
            'key_players_missing': 0,  # Nombre de joueurs clés absents
            'total_players_missing': 0  # Nombre total de joueurs absents
        }
    except Exception as e:
        print(f"Erreur lors de la récupération des disponibilités : {e}")
        return {'key_players_missing': 0, 'total_players_missing': 0}

def calculate_fatigue_index(matches, team, date, window_days=30):
    """
    Calcule un index de fatigue basé sur le nombre de matchs récents
    et les déplacements
    """
    recent_matches = matches[
        (matches['date'] >= date - timedelta(days=window_days)) &
        (matches['date'] < date) &
        ((matches['home_team'] == team) | (matches['away_team'] == team))
    ]
    
    # Nombre de matchs dans la période
    num_matches = len(recent_matches)
    
    # Nombre de déplacements (matchs à l'extérieur)
    away_matches = len(recent_matches[recent_matches['away_team'] == team])
    
    # Index de fatigue (0-1)
    fatigue_index = (num_matches / 10) * 0.7 + (away_matches / 5) * 0.3
    return min(fatigue_index, 1.0)

def get_competition_load(team, date):
    """
    Évalue la charge due aux différentes compétitions
    À implémenter avec l'API RapidAPI Football
    """
    try:
        # Appel API RapidAPI pour obtenir les compétitions en cours
        return {
            'in_champions_league': False,
            'in_europa_league': False,
            'in_conference_league': False,
            'in_coupe_france': False
        }
    except Exception as e:
        print(f"Erreur lors de la récupération des compétitions : {e}")
        return {
            'in_champions_league': False,
            'in_europa_league': False,
            'in_conference_league': False,
            'in_coupe_france': False
        }

def add_features(df, stats):
    """Ajoute toutes les features au DataFrame"""
    features = []
    
    for idx, row in df.iterrows():
        home_team = row['home_team']
        away_team = row['away_team']
        
        # Stats H2H
        h2h = get_h2h_stats(df[df['date'] < row['date']], home_team, away_team)
        
        if home_team in stats and away_team in stats:
            features.append({
                # Statistiques générales
                'home_avg_scored': stats[home_team]['avg_goals_scored_home'],
                'home_avg_conceded': stats[home_team]['avg_goals_conceded_home'],
                'away_avg_scored': stats[away_team]['avg_goals_scored_away'],
                'away_avg_conceded': stats[away_team]['avg_goals_conceded_away'],
                
                # Statistiques récentes
                'home_recent_scored': stats[home_team]['recent_goals_scored_home'],
                'home_recent_conceded': stats[home_team]['recent_goals_conceded_home'],
                'away_recent_scored': stats[away_team]['recent_goals_scored_away'],
                'away_recent_conceded': stats[away_team]['recent_goals_conceded_away'],
                
                # Forme
                'home_form': stats[home_team]['form'],
                'away_form': stats[away_team]['form'],
                
                # H2H
                'h2h_home_wins': h2h['team1_wins'],
                'h2h_away_wins': h2h['team2_wins'],
                'h2h_draws': h2h['draws'],
                'h2h_home_goals': h2h['team1_goals_avg'],
                'h2h_away_goals': h2h['team2_goals_avg']
            })
        else:
            features.append({
                'home_avg_scored': 0, 'home_avg_conceded': 0,
                'away_avg_scored': 0, 'away_avg_conceded': 0,
                'home_recent_scored': 0, 'home_recent_conceded': 0,
                'away_recent_scored': 0, 'away_recent_conceded': 0,
                'home_form': 0, 'away_form': 0,
                'h2h_home_wins': 0, 'h2h_away_wins': 0,
                'h2h_draws': 0, 'h2h_home_goals': 0, 'h2h_away_goals': 0
            })
    
    # Ajout des nouvelles features
    df['home_fatigue'] = df.apply(lambda row: calculate_fatigue_index(
        df, row['home_team'], row['date']), axis=1)
    df['away_fatigue'] = df.apply(lambda row: calculate_fatigue_index(
        df, row['away_team'], row['date']), axis=1)
    
    # Disponibilité des joueurs
    availability_features = df.apply(lambda row: {
        'home_' + k: v for k, v in get_player_availability(row['home_team'], row['date']).items()
    } | {
        'away_' + k: v for k, v in get_player_availability(row['away_team'], row['date']).items()
    }, axis=1)
    
    for feature in ['key_players_missing', 'total_players_missing']:
        df[f'home_{feature}'] = availability_features.apply(lambda x: x[f'home_{feature}'])
        df[f'away_{feature}'] = availability_features.apply(lambda x: x[f'away_{feature}'])
    
    # Charge des compétitions
    competition_features = df.apply(lambda row: {
        'home_' + k: v for k, v in get_competition_load(row['home_team'], row['date']).items()
    } | {
        'away_' + k: v for k, v in get_competition_load(row['away_team'], row['date']).items()
    }, axis=1)
    
    for comp in ['champions_league', 'europa_league', 'conference_league', 'coupe_france']:
        df[f'home_in_{comp}'] = competition_features.apply(lambda x: x[f'home_in_{comp}'])
        df[f'away_in_{comp}'] = competition_features.apply(lambda x: x[f'away_in_{comp}'])

    return pd.DataFrame(features)

def optimize_hyperparameters(X, y):
    """Optimise les hyperparamètres du modèle XGBoost"""
    print("\nDébut de l'optimisation des hyperparamètres...")
    
    # Réduire l'espace de recherche pour accélérer l'optimisation
    param_grid = {
        'n_estimators': [100, 200],
        'max_depth': [4, 6],
        'learning_rate': [0.05, 0.1],
        'min_child_weight': [1, 3],
        'subsample': [0.8, 1.0]
    }
    
    model = XGBRegressor(random_state=42)
    grid_search = GridSearchCV(
        estimator=model,
        param_grid=param_grid,
        cv=3,  # Réduit à 3 pour accélérer
        scoring='neg_mean_squared_error',
        n_jobs=-1,
        verbose=1  # Ajoute des logs
    )
    
    grid_search.fit(X, y)
    print(f"\nMeilleurs paramètres trouvés: {grid_search.best_params_}")
    print(f"Meilleur score: {-grid_search.best_score_:.4f} MSE")
    return grid_search.best_params_

def train_model():
    try:
        print("\n=== Début de l'entraînement du modèle ===")
        
        # 1) Connexion à la base SQLite
        print("\nChargement des données...")
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM matches ORDER BY date", conn)
        conn.close()
        print(f"Nombre total de matchs: {len(df)}")

        # 2) Nettoyage et préparation
        df['date'] = pd.to_datetime(df['date'])
        df = df.dropna(subset=['home_score', 'away_score'])
        print(f"Nombre de matchs après nettoyage: {len(df)}")

        if len(df) == 0:
            print("Aucun match terminé. Impossible d'entraîner le modèle.")
            return

        # 3) Feature engineering avancé
        print("\nCalcul des statistiques d'équipes...")
        team_stats = calculate_team_stats(df)
        print(f"Statistiques calculées pour {len(team_stats)} équipes")
        
        print("\nGénération des features avancées...")
        features_df = add_features(df, team_stats)
        
        # Ajout des encodages catégoriels
        df['home_team_id'] = df['home_team'].astype('category').cat.codes
        df['away_team_id'] = df['away_team'].astype('category').cat.codes
        
        # Combiner toutes les features
        X = pd.concat([
            df[['home_team_id', 'away_team_id']],
            features_df
        ], axis=1)
        
        print(f"\nFeatures générées ({X.shape[1]} au total):")
        for col in X.columns:
            print(f"- {col}")
        
        y_home = df['home_score'].values
        y_away = df['away_score'].values

        # 4) Split chronologique
        train_size = int(len(df) * 0.8)
        X_train, X_test = X[:train_size], X[train_size:]
        y_home_train, y_home_test = y_home[:train_size], y_home[train_size:]
        y_away_train, y_away_test = y_away[:train_size], y_away[train_size:]
        print(f"\nSplit des données: {train_size} matchs en train, {len(df) - train_size} en test")

        # 5) Optimisation des hyperparamètres
        print("\n=== Optimisation pour le modèle Domicile ===")
        best_params_home = optimize_hyperparameters(X_train, y_home_train)
        
        print("\n=== Optimisation pour le modèle Extérieur ===")
        best_params_away = optimize_hyperparameters(X_train, y_away_train)

        # 6) Entraînement avec les meilleurs paramètres
        print("\nEntraînement des modèles finaux...")
        xgb_home = XGBRegressor(**best_params_home, random_state=42)
        xgb_home.fit(X_train, y_home_train)

        xgb_away = XGBRegressor(**best_params_away, random_state=42)
        xgb_away.fit(X_train, y_away_train)

        # 7) Évaluation complète
        y_home_pred = xgb_home.predict(X_test)
        y_away_pred = xgb_away.predict(X_test)

        metrics = {
            'home': {
                'rmse': np.sqrt(mean_squared_error(y_home_test, y_home_pred)),
                'mae': mean_absolute_error(y_home_test, y_home_pred),
                'cv_score': np.mean(cross_val_score(xgb_home, X, y_home, cv=5))
            },
            'away': {
                'rmse': np.sqrt(mean_squared_error(y_away_test, y_away_pred)),
                'mae': mean_absolute_error(y_away_test, y_away_pred),
                'cv_score': np.mean(cross_val_score(xgb_away, X, y_away, cv=5))
            }
        }

        # 8) Feature importance
        feature_importance = {
            'home': dict(zip(X.columns, xgb_home.feature_importances_)),
            'away': dict(zip(X.columns, xgb_away.feature_importances_))
        }

        print("\n=== Résultats d'évaluation ===")
        print(f"Domicile - RMSE: {metrics['home']['rmse']:.2f}, MAE: {metrics['home']['mae']:.2f}, CV Score: {metrics['home']['cv_score']:.2f}")
        print(f"Extérieur - RMSE: {metrics['away']['rmse']:.2f}, MAE: {metrics['away']['mae']:.2f}, CV Score: {metrics['away']['cv_score']:.2f}")

        print("\n=== Features les plus importantes ===")
        print("\nDomicile:")
        home_importance = sorted(feature_importance['home'].items(), key=lambda x: x[1], reverse=True)[:5]
        for feature, importance in home_importance:
            print(f"- {feature}: {importance:.4f}")

        print("\nExtérieur:")
        away_importance = sorted(feature_importance['away'].items(), key=lambda x: x[1], reverse=True)[:5]
        for feature, importance in away_importance:
            print(f"- {feature}: {importance:.4f}")

        # 9) Sauvegarde du modèle avec métadonnées
        model = {
            'model_home': xgb_home,
            'model_away': xgb_away,
            'metrics': metrics,
            'feature_importance': feature_importance,
            'team_stats': team_stats,
            'training_date': datetime.now().isoformat(),
            'hyperparameters': {
                'home': best_params_home,
                'away': best_params_away
            }
        }
        joblib.dump(model, MODEL_PATH)
        print(f"\nModèle sauvegardé dans {MODEL_PATH}")

    except Exception as e:
        print(f"\nERREUR: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise

if __name__ == "__main__":
    train_model()
