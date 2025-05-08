const sqlite3 = require('sqlite3').verbose();
const config = require('../config/config');

async function addRecentMatch() {
    const db = new sqlite3.Database(config.PATHS.DB);
    
    const match = {
        date: '2025-04-12 20:00:00', // Match d'aujourd'hui
        home_team: 'Monaco',
        away_team: 'Marseille',
        home_score: 3,
        away_score: 0
    };

    try {
        await new Promise((resolve, reject) => {
            const sql = `
                INSERT INTO matches (
                    date,
                    home_team,
                    away_team,
                    home_score,
                    away_score
                ) VALUES (?, ?, ?, ?, ?)
            `;
            
            db.run(sql, [
                match.date,
                match.home_team,
                match.away_team,
                match.home_score,
                match.away_score
            ], (err) => {
                if (err) reject(err);
                else resolve();
            });
        });

        console.log('Match ajouté avec succès');

    } catch (error) {
        console.error('Erreur lors de l\'ajout du match:', error);
    } finally {
        db.close();
    }
}

addRecentMatch();
