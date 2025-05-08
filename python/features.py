"""
Définition des features communes pour l'entraînement et la prédiction
"""

FEATURES = [
    'home_team_form', 'away_team_form',
    'home_goals_scored_avg', 'away_goals_scored_avg',
    'home_goals_conceded_avg', 'away_goals_conceded_avg',
    'weather_temp', 'weather_rain', 'weather_wind',
    'home_missing_key_players', 'away_missing_key_players',
    'form_difference', 'goals_scored_diff', 'goals_conceded_diff',
    'h2h_goal_diff', 'h2h_experience', 'home_high_form', 'away_high_form',
    'home_european_match', 'away_european_match'
]

# Features simplifiées si nécessaire
SIMPLE_FEATURES = [
    'home_team_form', 'away_team_form',
    'home_goals_scored_avg', 'away_goals_scored_avg',
    'home_goals_conceded_avg', 'away_goals_conceded_avg'
]
