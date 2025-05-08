const sqlite3 = require('sqlite3').verbose();
const config = require('../config/config');

async function insertTestMatches() {
    const db = new sqlite3.Database(config.PATHS.DB);
    
    // Matchs de test à venir
    const matches = [
        {
            home_team: "Paris Saint Germain",
            away_team: "Marseille",
            date: "2025-04-14 21:00:00" // Dans 2 jours
        },
        {
            home_team: "Lyon",
            away_team: "Monaco",
            date: "2025-04-14 19:00:00" // Dans 2 jours
        },
        {
            home_team: "Lens",
            away_team: "Nice",
            date: "2025-04-15 21:00:00" // Dans 3 jours
        },
        {
            home_team: "Lille",
            away_team: "Rennes",
            date: "2025-04-15 19:00:00" // Dans 3 jours
        }
    ];

    try {
        // Commencer la transaction
        await new Promise((resolve, reject) => {
            db.run('BEGIN TRANSACTION', (err) => {
                if (err) reject(err);
                else resolve();
            });
        });

        // Insérer chaque match
        for (const match of matches) {
            await new Promise((resolve, reject) => {
                const sql = `
                    INSERT INTO matches (
                        home_team,
                        away_team,
                        date
                    ) VALUES (?, ?, ?)
                `;
                
                db.run(sql, [
                    match.home_team,
                    match.away_team,
                    match.date
                ], (err) => {
                    if (err) reject(err);
                    else resolve();
                });
            });
        }

        // Valider la transaction
        await new Promise((resolve, reject) => {
            db.run('COMMIT', (err) => {
                if (err) reject(err);
                else resolve();
            });
        });

        console.log(`${matches.length} matchs de test insérés avec succès`);

    } catch (error) {
        // Annuler la transaction en cas d'erreur
        await new Promise((resolve) => {
            db.run('ROLLBACK', () => resolve());
        });
        console.error('Erreur lors de l\'insertion des matchs:', error);
        process.exit(1);
    } finally {
        // Fermer la connexion
        db.close();
    }
}

// Exécuter l'insertion
insertTestMatches();
