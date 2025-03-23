-- Création de la table des équipes si elle n'existe pas
CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    api_team_id INTEGER UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table pour les blessures et suspensions
CREATE TABLE IF NOT EXISTS player_availability (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER,
    player_name TEXT NOT NULL,
    reason TEXT,
    start_date DATE,
    end_date DATE,
    is_key_player BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (team_id) REFERENCES teams(id)
);

-- Table pour la charge des compétitions
CREATE TABLE IF NOT EXISTS team_competitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER,
    competition TEXT NOT NULL,
    season TEXT NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    last_updated DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (team_id) REFERENCES teams(id)
);

-- Table pour les statistiques de forme
CREATE TABLE IF NOT EXISTS team_form (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER,
    date DATE NOT NULL,
    form_index FLOAT,
    fatigue_index FLOAT,
    goals_scored_last5 INTEGER,
    goals_conceded_last5 INTEGER,
    matches_played_30days INTEGER,
    away_matches_30days INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (team_id) REFERENCES teams(id)
);

-- Création d'une nouvelle table matches avec les colonnes supplémentaires
CREATE TABLE IF NOT EXISTS matches_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id INTEGER,
    date DATE,
    home_team TEXT,
    away_team TEXT,
    home_score INTEGER,
    away_score INTEGER,
    round TEXT,
    home_form_index FLOAT,
    away_form_index FLOAT,
    home_fatigue_index FLOAT,
    away_fatigue_index FLOAT,
    home_key_players_missing INTEGER DEFAULT 0,
    away_key_players_missing INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Copier les données de l'ancienne table vers la nouvelle
INSERT OR IGNORE INTO matches_new (fixture_id, date, home_team, away_team, home_score, away_score, round)
SELECT fixture_id, date, home_team, away_team, home_score, away_score, round
FROM matches;