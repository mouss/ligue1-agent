const sqlite3 = require('sqlite3').verbose();
const config = require('../config/config');

async function updateHeadToHeadStats() {
    const db = new sqlite3.Database(config.PATHS.DB);
    
    try {
        // Récupérer toutes les équipes
        const teams = await new Promise((resolve, reject) => {
            db.all('SELECT DISTINCT name FROM teams', (err, rows) => {
                if (err) reject(err);
                else resolve(rows.map(row => row.name));
            });
        });

        console.log(`Mise à jour des statistiques pour ${teams.length} équipes...`);

        // Commencer la transaction
        await new Promise((resolve, reject) => {
            db.run('BEGIN TRANSACTION', (err) => {
                if (err) reject(err);
                else resolve();
            });
        });

        // Pour chaque paire d'équipes
        for (let i = 0; i < teams.length; i++) {
            for (let j = i + 1; j < teams.length; j++) {
                const team1 = teams[i];
                const team2 = teams[j];

                // Calculer les statistiques des confrontations directes
                const stats = await new Promise((resolve, reject) => {
                    const sql = `
                        WITH recent_matches AS (
                            SELECT 
                                date,
                                CASE 
                                    WHEN home_team = ? THEN home_score
                                    ELSE away_score
                                END as team1_score,
                                CASE 
                                    WHEN home_team = ? THEN away_score
                                    ELSE home_score
                                END as team2_score
                            FROM matches 
                            WHERE (home_team IN (?, ?) AND away_team IN (?, ?))
                            AND date <= datetime('now')
                            ORDER BY date DESC
                            LIMIT 5
                        )
                        SELECT 
                            COUNT(*) as total_matches,
                            SUM(CASE WHEN team1_score > team2_score THEN 1 ELSE 0 END) as team1_wins,
                            SUM(CASE WHEN team1_score = team2_score THEN 1 ELSE 0 END) as draws,
                            SUM(CASE WHEN team1_score < team2_score THEN 1 ELSE 0 END) as team2_wins,
                            ROUND(AVG(team1_score), 2) as team1_goals_avg,
                            ROUND(AVG(team2_score), 2) as team2_goals_avg,
                            GROUP_CONCAT(
                                CASE 
                                    WHEN team1_score > team2_score THEN '1'
                                    WHEN team1_score = team2_score THEN 'D'
                                    ELSE '2'
                                END
                            ) as last_5_matches
                        FROM recent_matches
                    `;
                    
                    db.get(sql, [team1, team2, team1, team2, team1, team2], (err, row) => {
                        if (err) reject(err);
                        else resolve(row);
                    });
                });

                if (stats.total_matches > 0) {
                    // Insérer ou mettre à jour les statistiques
                    await new Promise((resolve, reject) => {
                        const updateSql = `
                            INSERT OR REPLACE INTO head_to_head_stats (
                                team1, team2,
                                last_5_matches,
                                team1_goals_avg,
                                team2_goals_avg,
                                team1_wins,
                                team2_wins,
                                draws
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        `;
                        
                        db.run(updateSql, [
                            team1,
                            team2,
                            stats.last_5_matches || '',
                            stats.team1_goals_avg || 0,
                            stats.team2_goals_avg || 0,
                            stats.team1_wins || 0,
                            stats.team2_wins || 0,
                            stats.draws || 0
                        ], (err) => {
                            if (err) reject(err);
                            else resolve();
                        });
                    });

                    console.log(`Statistiques mises à jour pour ${team1} vs ${team2}`);
                }
            }
        }

        // Valider la transaction
        await new Promise((resolve, reject) => {
            db.run('COMMIT', (err) => {
                if (err) reject(err);
                else resolve();
            });
        });

        console.log('Mise à jour des statistiques terminée avec succès');

    } catch (error) {
        // Annuler la transaction en cas d'erreur
        await new Promise((resolve) => {
            db.run('ROLLBACK', () => resolve());
        });
        console.error('Erreur lors de la mise à jour des statistiques:', error);
        process.exit(1);
    } finally {
        // Fermer la connexion
        db.close();
    }
}

// Exécuter la mise à jour
updateHeadToHeadStats();
