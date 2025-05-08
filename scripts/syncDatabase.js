const sqlite3 = require('sqlite3').verbose();
const config = require('../config/config');
const apiService = require('../services/api');

async function syncDatabase() {
    const db = new sqlite3.Database(config.PATHS.DB);
    console.log('\nDémarrage de la synchronisation...');
    console.log(`Base de données : ${config.PATHS.DB}`);
    console.log(`Saison : ${config.SEASON}`);

    try {
        // Récupérer les derniers matchs via l'API
        console.log('\nRécupération des données depuis l\'API...');
        const fixtures = await apiService.fetchFixtures();
        console.log(`${fixtures.length} matchs trouvés`);
        
        // Commencer la transaction
        await new Promise((resolve, reject) => {
            db.run('BEGIN TRANSACTION', (err) => {
                if (err) reject(err);
                else resolve();
            });
        });

        // Insérer ou mettre à jour les matchs
        console.log('\nMise à jour de la base de données...');
        let updated = 0;
        let inserted = 0;

        for (const fixture of fixtures) {
            await new Promise((resolve, reject) => {
                // Vérifier si le match existe déjà
                db.get('SELECT match_id FROM matches WHERE match_id = ?', [fixture.fixture.id], (err, row) => {
                    if (err) {
                        reject(err);
                        return;
                    }

                    const sql = `
                        INSERT OR REPLACE INTO matches (
                            match_id,
                            home_team,
                            away_team,
                            home_goals,
                            away_goals,
                            date,
                            status,
                            season
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    `;
                    
                    db.run(sql, [
                        fixture.fixture.id,
                        fixture.teams.home.name,
                        fixture.teams.away.name,
                        fixture.goals.home,
                        fixture.goals.away,
                        fixture.fixture.date,
                        fixture.fixture.status.short,
                        config.SEASON
                    ], (err) => {
                        if (err) {
                            reject(err);
                            return;
                        }
                        row ? updated++ : inserted++;
                        resolve();
                    });
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

        console.log('\nRésumé de la synchronisation :');
        console.log(`- Matchs mis à jour : ${updated}`);
        console.log(`- Nouveaux matchs : ${inserted}`);
        console.log(`- Total traité : ${fixtures.length}`);

    } catch (error) {
        // Annuler la transaction en cas d'erreur
        await new Promise((resolve) => {
            db.run('ROLLBACK', () => resolve());
        });
        console.error('\nErreur lors de la synchronisation:', error);
        process.exit(1);
    } finally {
        // Fermer la connexion
        db.close();
    }
}

// Si exécuté directement
if (require.main === module) {
    syncDatabase();
}

module.exports = syncDatabase;
