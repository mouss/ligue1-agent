const sqlite3 = require('sqlite3').verbose();
const config = require('../config/config');

async function insertPlayerData() {
    const db = new sqlite3.Database(config.PATHS.DB);
    
    // Données des joueurs pour 2025
    const playerData = [
        // PSG
        {
            player_name: "Ousmane Dembélé",
            team: "Paris Saint Germain",
            status: "blessé",
            reason: "Douleur musculaire",
            start_date: "2025-04-10",
            expected_return: "2025-04-17",
            impact_level: 5,
            is_key_player: 1
        },
        {
            player_name: "Bradley Barcola",
            team: "Paris Saint Germain",
            status: "suspendu",
            reason: "Accumulation de cartons jaunes",
            start_date: "2025-04-12",
            expected_return: "2025-04-19",
            impact_level: 4,
            is_key_player: 1
        },

        // Marseille
        {
            player_name: "Mason Greenwood",
            team: "Marseille",
            status: "blessé",
            reason: "Entorse de la cheville",
            start_date: "2025-04-08",
            expected_return: "2025-04-22",
            impact_level: 5,
            is_key_player: 1
        },

        // Lille
        {
            player_name: "Jonathan David",
            team: "Lille",
            status: "incertain",
            reason: "Fatigue musculaire",
            start_date: "2025-04-11",
            expected_return: "2025-04-14",
            impact_level: 5,
            is_key_player: 1
        },

        // Lyon
        {
            player_name: "Rayan Cherki",
            team: "Lyon",
            status: "blessé",
            reason: "Lésion musculaire",
            start_date: "2025-04-09",
            expected_return: "2025-04-23",
            impact_level: 5,
            is_key_player: 1
        },

        // Monaco
        {
            player_name: "Maghnes Akliouche",
            team: "Monaco",
            status: "incertain",
            reason: "Problème au genou",
            start_date: "2025-04-11",
            expected_return: "2025-04-15",
            impact_level: 4,
            is_key_player: 1
        },

        // Rennes
        {
            player_name: "Arnaud Kalimuendo",
            team: "Rennes",
            status: "blessé",
            reason: "Blessure ligamentaire",
            start_date: "2025-04-06",
            expected_return: "2025-04-27",
            impact_level: 5,
            is_key_player: 1
        },

        // Nantes
        {
            player_name: "Moses Simon",
            team: "Nantes",
            status: "suspendu",
            reason: "Carton rouge direct",
            start_date: "2025-04-12",
            expected_return: "2025-04-26",
            impact_level: 4,
            is_key_player: 1
        },

        // Strasbourg
        {
            player_name: "Dilane Bakwa",
            team: "Strasbourg",
            status: "blessé",
            reason: "Claquage",
            start_date: "2025-04-11",
            expected_return: "2025-04-25",
            impact_level: 4,
            is_key_player: 1
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

        // Insérer les données
        for (const player of playerData) {
            await new Promise((resolve, reject) => {
                const sql = `
                    INSERT INTO player_availability (
                        player_name,
                        team,
                        status,
                        reason,
                        start_date,
                        expected_return,
                        impact_level,
                        is_key_player
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                `;
                
                db.run(sql, [
                    player.player_name,
                    player.team,
                    player.status,
                    player.reason,
                    player.start_date,
                    player.expected_return,
                    player.impact_level,
                    player.is_key_player
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

        console.log('Données des joueurs insérées avec succès');

    } catch (error) {
        // Annuler la transaction en cas d'erreur
        await new Promise((resolve) => {
            db.run('ROLLBACK', () => resolve());
        });
        console.error('Erreur lors de l\'insertion des données:', error);
        process.exit(1);
    } finally {
        // Fermer la connexion
        db.close();
    }
}

// Exécuter l'insertion des données
insertPlayerData();
