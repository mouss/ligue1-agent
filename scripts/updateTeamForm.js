const sqlite3 = require('sqlite3').verbose();
const config = require('../config/config');

async function updateTeamForm() {
    const db = new sqlite3.Database(config.PATHS.DB);
    
    try {
        // Activer les foreign keys
        await new Promise((resolve, reject) => {
            db.run('PRAGMA foreign_keys = ON', (err) => {
                if (err) reject(err);
                else resolve();
            });
        });

        // Récupérer tous les matches
        const matches = await new Promise((resolve, reject) => {
            db.all(`SELECT * FROM matches ORDER BY date`, (err, rows) => {
                if (err) reject(err);
                else resolve(rows);
            });
        });

        // Pour chaque match, mettre à jour la forme des équipes
        for (const match of matches) {
            const date = match.date;
            
            // Calculer la forme de l'équipe à domicile
            await updateTeamFormForDate(db, match.home_team, date);
            
            // Calculer la forme de l'équipe à l'extérieur
            await updateTeamFormForDate(db, match.away_team, date);
        }

        console.log('Mise à jour de la forme des équipes terminée');
        
    } catch (error) {
        console.error('Erreur lors de la mise à jour de la forme des équipes:', error);
        process.exit(1);
    } finally {
        db.close();
    }
}

async function updateTeamFormForDate(db, team, date) {
    try {
        // Récupérer les 5 derniers matches de l'équipe avant cette date
        const last5Matches = await new Promise((resolve, reject) => {
            db.all(`
                SELECT 
                    date,
                    CASE 
                        WHEN home_team = ? THEN 
                            CASE 
                                WHEN home_score > away_score THEN 3
                                WHEN home_score = away_score THEN 1
                                ELSE 0
                            END
                        ELSE 
                            CASE 
                                WHEN away_score > home_score THEN 3
                                WHEN home_score = away_score THEN 1
                                ELSE 0
                            END
                    END as points,
                    CASE 
                        WHEN home_team = ? THEN home_score
                        ELSE away_score
                    END as goals_scored,
                    CASE 
                        WHEN home_team = ? THEN away_score
                        ELSE home_score
                    END as goals_conceded
                FROM matches 
                WHERE (home_team = ? OR away_team = ?)
                AND date < ?
                ORDER BY date DESC
                LIMIT 5
            `, [team, team, team, team, team, date], (err, rows) => {
                if (err) reject(err);
                else resolve(rows);
            });
        });

        if (last5Matches.length > 0) {
            // Calculer la forme avec pondération
            const weights = last5Matches.map((_, i) => Math.exp(-i * 0.4));
            const totalWeight = weights.reduce((a, b) => a + b, 0);
            
            const form = last5Matches.reduce((acc, match, i) => {
                return acc + (match.points / 3) * (weights[i] / totalWeight);
            }, 0);

            const totalGoalsScored = last5Matches.reduce((sum, m) => sum + m.goals_scored, 0);
            const totalGoalsConceded = last5Matches.reduce((sum, m) => sum + m.goals_conceded, 0);
            
            // Sauvegarder la forme
            await new Promise((resolve, reject) => {
                db.run(`
                    INSERT OR REPLACE INTO team_form 
                    (team, date, form, last_5_matches, goals_scored, goals_conceded)
                    VALUES (?, ?, ?, ?, ?, ?)
                `, [
                    team,
                    date,
                    form,
                    JSON.stringify(last5Matches.map(m => m.points)),
                    totalGoalsScored,
                    totalGoalsConceded
                ], (err) => {
                    if (err) reject(err);
                    else resolve();
                });
            });
        }
    } catch (error) {
        console.error(`Erreur lors de la mise à jour de la forme de ${team}:`, error);
        throw error;
    }
}

// Exécuter la mise à jour
updateTeamForm();