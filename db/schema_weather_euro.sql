-- Table pour les conditions météo des stades
CREATE TABLE IF NOT EXISTS stadium_conditions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_date DATETIME NOT NULL,
    temperature FLOAT,
    precipitation FLOAT,
    wind_speed FLOAT,
    weather_condition TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table pour les matchs européens
CREATE TABLE IF NOT EXISTS european_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team TEXT NOT NULL,
    match_date DATETIME NOT NULL,
    competition TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index pour optimiser les requêtes
CREATE INDEX IF NOT EXISTS idx_stadium_conditions_date ON stadium_conditions(match_date);
CREATE INDEX IF NOT EXISTS idx_european_matches_team_date ON european_matches(team, match_date);
