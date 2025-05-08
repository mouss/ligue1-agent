const sqlite3 = require('sqlite3').verbose();
const config = require('../config/config');

async function initDatabase() {
    const db = new sqlite3.Database(config.PATHS.DB);
    
    try {
        // Activer les foreign keys et le mode WAL
        await new Promise((resolve, reject) => {
            db.run('PRAGMA foreign_keys = ON', (err) => {
                if (err) reject(err);
                else resolve();
            });
        });

        // Vérifier la structure des tables existantes
        console.log('Vérification de la structure des tables...');
        const tableInfo = await getTableInfo(db, 'player_availability');
        console.log('Structure de player_availability:', tableInfo);

        // Créer les tables
        await createTables(db);
        
        // Vérifier que les tables sont créées
        const tables = await checkTables(db);
        console.log('Tables créées:', tables);

        // Créer les index
        await createIndexes(db);
        console.log('Tables et index créés avec succès');
    } catch (error) {
        console.error('Erreur:', error);
        throw error;
    } finally {
        await new Promise((resolve, reject) => {
            db.close((err) => {
                if (err) reject(err);
                else resolve();
            });
        });
    }
}

async function getTableInfo(db, tableName) {
    return new Promise((resolve, reject) => {
        db.all(`PRAGMA table_info(${tableName})`, (err, rows) => {
            if (err) reject(err);
            else resolve(rows);
        });
    });
}

async function checkTables(db) {
    return new Promise((resolve, reject) => {
        db.all("SELECT name FROM sqlite_master WHERE type='table'", (err, tables) => {
            if (err) reject(err);
            else resolve(tables.map(t => t.name));
        });
    });
}

async function createTables(db) {
    // Supprimer les tables existantes si nécessaire
    const dropQueries = [
        `DROP TABLE IF EXISTS player_availability;`,
        `DROP TABLE IF EXISTS stadium_conditions;`,
        `DROP TABLE IF EXISTS european_matches;`,
        `DROP TABLE IF EXISTS team_form;`,
        `DROP TABLE IF EXISTS head_to_head_stats;`
    ];

    for (const query of dropQueries) {
        await new Promise((resolve, reject) => {
            db.run(query, function(err) {
                if (err) {
                    console.error('Erreur lors de la suppression de la table:', err);
                    reject(err);
                } else {
                    resolve();
                }
            });
        });
    }

    const tableQueries = [
        // Table pour les blessures et suspensions avec la nouvelle structure
        `CREATE TABLE IF NOT EXISTS player_availability (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_name TEXT NOT NULL,
            team TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('blessé', 'suspendu', 'incertain')),
            reason TEXT,
            start_date DATE NOT NULL,
            expected_return DATE,
            impact_level INTEGER CHECK (impact_level BETWEEN 1 AND 5),
            is_key_player BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(team) REFERENCES teams(name)
        )`,

        // Trigger pour mettre à jour le timestamp
        `CREATE TRIGGER IF NOT EXISTS update_player_availability_timestamp 
         AFTER UPDATE ON player_availability
         BEGIN
             UPDATE player_availability SET updated_at = CURRENT_TIMESTAMP
             WHERE id = NEW.id;
         END`,

        // Table pour les conditions météo
        `CREATE TABLE IF NOT EXISTS stadium_conditions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stadium TEXT NOT NULL,
            match_date DATE NOT NULL,
            temperature FLOAT,
            precipitation FLOAT,
            wind_speed FLOAT,
            weather_condition TEXT
        )`,

        // Table pour les statistiques des confrontations directes
        `CREATE TABLE IF NOT EXISTS head_to_head_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team1 TEXT NOT NULL,
            team2 TEXT NOT NULL,
            last_5_matches TEXT,
            team1_goals_avg FLOAT,
            team2_goals_avg FLOAT,
            team1_wins INTEGER,
            team2_wins INTEGER,
            draws INTEGER,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(team1, team2)
        )`,

        // Table pour les matchs européens
        `CREATE TABLE IF NOT EXISTS european_matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team TEXT NOT NULL,
            competition TEXT NOT NULL,
            match_date DATE NOT NULL,
            is_home BOOLEAN,
            opponent TEXT,
            score_for INTEGER,
            score_against INTEGER
        )`,

        // Table pour la forme des équipes
        `CREATE TABLE IF NOT EXISTS team_form (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team TEXT NOT NULL,
            date DATE NOT NULL,
            form FLOAT NOT NULL,
            last_5_matches TEXT,
            goals_scored INTEGER DEFAULT 0,
            goals_conceded INTEGER DEFAULT 0,
            UNIQUE(team, date)
        )`
    ];

    for (const query of tableQueries) {
        await new Promise((resolve, reject) => {
            db.run(query, function(err) {
                if (err) {
                    console.error('Erreur lors de la création de la table:', err);
                    reject(err);
                } else {
                    resolve();
                }
            });
        });
    }
}

async function createIndexes(db) {
    const indexQueries = [
        // Index pour la table player_availability
        `CREATE INDEX IF NOT EXISTS idx_player_availability_team ON player_availability(team);`,
        `CREATE INDEX IF NOT EXISTS idx_player_availability_status ON player_availability(status);`,
        `CREATE INDEX IF NOT EXISTS idx_player_availability_dates ON player_availability(start_date, expected_return);`,
        `CREATE INDEX IF NOT EXISTS idx_player_availability_impact ON player_availability(impact_level);`,
        
        // Index pour la table head_to_head_stats
        `CREATE INDEX IF NOT EXISTS idx_h2h_teams ON head_to_head_stats(team1, team2);`,
        `CREATE INDEX IF NOT EXISTS idx_h2h_last_updated ON head_to_head_stats(last_updated);`,
        
        // Index pour la table stadium_conditions
        `CREATE INDEX IF NOT EXISTS idx_stadium_conditions_date ON stadium_conditions(match_date);`,
        
        // Index pour la table european_matches
        `CREATE INDEX IF NOT EXISTS idx_european_matches_team_date ON european_matches(team, match_date);`,
        
        // Index pour la table team_form
        `CREATE INDEX IF NOT EXISTS idx_team_form_team_date ON team_form(team, date);`,
        
        // Index pour la table matches
        `CREATE INDEX IF NOT EXISTS idx_matches_teams ON matches(home_team, away_team);`,
        `CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(date);`,
        `CREATE INDEX IF NOT EXISTS idx_matches_scores ON matches(home_score, away_score);`
    ];

    for (const query of indexQueries) {
        await new Promise((resolve, reject) => {
            db.run(query, function(err) {
                if (err) {
                    console.error('Erreur lors de la création de l\'index:', err);
                    reject(err);
                } else {
                    resolve();
                }
            });
        });
    }
}

// Exécution du script
initDatabase()
    .then(() => {
        console.log('Base de données initialisée avec succès');
        process.exit(0);
    })
    .catch((error) => {
        console.error('Erreur lors de l\'initialisation de la base de données:', error);
        process.exit(1);
    });