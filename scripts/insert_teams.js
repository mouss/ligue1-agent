const sqlite3 = require('sqlite3').verbose();
const config = require('../config/config');

async function insertTeams() {
    const db = new sqlite3.Database(config.PATHS.DB);
    
    // Liste des équipes de Ligue 1 (2024-2025)
    const teams = [
        "Paris Saint Germain",
        "Marseille",
        "Lyon",
        "Monaco",
        "Lens",
        "Rennes",
        "Nice",
        "Lille",
        "Strasbourg",
        "Montpellier",
        "Reims",
        "Toulouse",
        "Nantes",
        "Stade Brestois 29",
        "LE Havre",
        "Lorient",
        "Clermont",
        "Metz",
        "Auxerre",
        "Angers"
    ];

    try {
        // Commencer la transaction
        await new Promise((resolve, reject) => {
            db.run('BEGIN TRANSACTION', (err) => {
                if (err) reject(err);
                else resolve();
            });
        });

        // Insérer chaque équipe
        for (const team of teams) {
            await new Promise((resolve, reject) => {
                const sql = 'INSERT OR IGNORE INTO teams (name) VALUES (?)';
                db.run(sql, [team], (err) => {
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

        console.log(`${teams.length} équipes insérées avec succès`);

    } catch (error) {
        // Annuler la transaction en cas d'erreur
        await new Promise((resolve) => {
            db.run('ROLLBACK', () => resolve());
        });
        console.error('Erreur lors de l\'insertion des équipes:', error);
        process.exit(1);
    } finally {
        // Fermer la connexion
        db.close();
    }
}

// Exécuter l'insertion
insertTeams();
