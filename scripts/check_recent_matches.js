const sqlite3 = require('sqlite3').verbose();
const config = require('../config/config');

async function checkRecentMatches() {
    const db = new sqlite3.Database(config.PATHS.DB);
    
    const query = `
        SELECT 
            date,
            home_team,
            away_team,
            home_score,
            away_score
        FROM matches 
        WHERE date < datetime('now')
        AND (home_team IN ('Monaco', 'Marseille') OR away_team IN ('Monaco', 'Marseille'))
        ORDER BY date DESC
        LIMIT 5
    `;

    db.all(query, [], (err, rows) => {
        if (err) {
            console.error('Erreur:', err);
            return;
        }
        
        console.log('Derniers matchs de Monaco et Marseille:');
        rows.forEach(match => {
            console.log(`${match.date}: ${match.home_team} ${match.home_score} - ${match.away_score} ${match.away_team}`);
        });
        
        db.close();
    });
}

checkRecentMatches();
