
const sqlite3 = require('sqlite3').verbose();
const path = require('path');
const dbPath = path.join(__dirname, 'ligue1.db');

function initDB() {
  const db = new sqlite3.Database(dbPath);

  db.serialize(() => {
    // Créer une table "matches" pour stocker les infos de match
    db.run(`
      CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fixture_id INTEGER,
        date TEXT,
        home_team TEXT,
        away_team TEXT,
        home_score INTEGER,
        away_score INTEGER
      )
    `);

    // On pourrait créer d’autres tables si on veut, ex. table "teams", "predictions", etc.
  });

  db.close();
  console.log("DB initialized.");
}

initDB();
