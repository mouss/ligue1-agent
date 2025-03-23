// index.js
require('dotenv').config();
const express = require('express');
const axios = require('axios');
const sqlite3 = require('sqlite3').verbose();
const app = express();
const path = require('path');
const { PythonShell } = require('python-shell');
const fs = require('fs');

// Constantes
const PORT = 3000;

// Configuration des chemins
const ROOT_DIR = __dirname;
const PYTHON_DIR = path.join(ROOT_DIR, 'python');
const DB_DIR = path.join(ROOT_DIR, 'db');
const VIEWS_DIR = path.join(ROOT_DIR, 'views');

// Configuration EJS
app.set('view engine', 'ejs');
app.set('views', VIEWS_DIR);

// Création du dossier db s'il n'existe pas
if (!fs.existsSync(DB_DIR)) {
    fs.mkdirSync(DB_DIR);
}

const dbPath = path.join(DB_DIR, 'ligue1.db');

// Configurer vos clés
const RAPIDAPI_KEY = "c16a3bd85cmsh57c4e77612f35fep1b54b0jsnc50c626d3ff5";
const RAPIDAPI_HOST = "api-football-v1.p.rapidapi.com";
const LIGUE1_ID = 61;
const SEASON = 2024;

// Configuration Python
const PYTHON_OPTIONS = {
    mode: 'text',
    pythonPath: '/Library/Developer/CommandLineTools/usr/bin/python3',
    scriptPath: PYTHON_DIR,
    pythonOptions: ['-u']  // Mode unbuffered pour les logs en temps réel
};

// Initialisation de la base de données
const initDatabase = () => {
    return new Promise((resolve, reject) => {
        const db = new sqlite3.Database(dbPath, (err) => {
            if (err) {
                reject(err);
                return;
            }

            db.run(`
                CREATE TABLE IF NOT EXISTS matches (
                    fixture_id INTEGER PRIMARY KEY,
                    date TEXT,
                    home_team TEXT,
                    away_team TEXT,
                    home_score INTEGER,
                    away_score INTEGER,
                    round TEXT
                )
            `, (err) => {
                if (err) {
                    reject(err);
                } else {
                    resolve(db);
                }
            });
        });
    });
};

app.get('/fetch-matches', async (req, res) => {
    let db = null;
    try {
        // 1. Initialiser la base de données
        db = await initDatabase();
        console.log('Base de données initialisée');

        // 2. Récupérer les données de l'API
        console.log('Récupération des données de l\'API...');
        const options = {
            method: 'GET',
            url: `https://${RAPIDAPI_HOST}/v3/fixtures`,
            params: {
                league: LIGUE1_ID,
                season: SEASON
            },
            headers: {
                'x-rapidapi-key': RAPIDAPI_KEY,
                'x-rapidapi-host': RAPIDAPI_HOST
            }
        };

        const response = await axios.request(options);
        const fixtures = response.data.response;

        if (!fixtures || !Array.isArray(fixtures)) {
            throw new Error('Format de réponse API invalide');
        }

        console.log(`Récupération de ${fixtures.length} matchs depuis l'API`);

        // 3. Préparer la requête d'insertion
        const stmt = db.prepare(`
            REPLACE INTO matches (fixture_id, date, home_team, away_team, home_score, away_score, round)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        `);

        // 4. Insérer les données
        let insertCount = 0;
        for (const fix of fixtures) {
            try {
                stmt.run(
                    fix.fixture.id,
                    fix.fixture.date,
                    fix.teams.home.name,
                    fix.teams.away.name,
                    fix.goals.home,
                    fix.goals.away,
                    fix.league.round
                );
                insertCount++;
            } catch (err) {
                console.error('Erreur lors de l\'insertion du match:', fix.fixture.id, err);
            }
        }

        stmt.finalize();
        console.log(`${insertCount} matchs insérés avec succès`);

        res.json({
            success: true,
            message: `${insertCount} matchs ont été insérés/mis à jour dans la base de données`,
            totalMatches: fixtures.length
        });

    } catch (error) {
        console.error('Erreur complète:', error);
        res.status(500).json({
            success: false,
            error: error.message,
            details: error.response?.data || 'Pas de détails supplémentaires'
        });
    } finally {
        if (db) {
            db.close((err) => {
                if (err) console.error('Erreur lors de la fermeture de la DB:', err);
            });
        }
    }
});

app.get('/train', (req, res) => {
    console.log('Démarrage de l\'entraînement du modèle...');
    
    const pyshell = new PythonShell('train_model.py', PYTHON_OPTIONS);
    let output = [];

    pyshell.on('message', (message) => {
        console.log("[PYTHON]", message);
        output.push(message);
    });

    pyshell.on('error', (err) => {
        console.error('Erreur Python:', err);
        res.status(500).json({
            success: false,
            error: err.message,
            output: output
        });
    });

    pyshell.end((err, code, signal) => {
        if (err) {
            console.error('Erreur lors de l\'entraînement:', err);
            return res.status(500).json({
                success: false,
                error: err.message,
                code: code,
                signal: signal,
                output: output
            });
        }
        
        res.json({
            success: true,
            message: "Entraînement terminé avec succès",
            output: output
        });
    });
});

app.get('/predict-upcoming', (req, res) => {
  const scriptPath = path.join(__dirname, 'python', 'predict.py');
  let pyshell = new PythonShell(scriptPath);

  let output = "";
  pyshell.on('message', (message) => {
    output += message;
  });

  pyshell.end((err) => {
    if (err) {
      console.error(err);
      return res.status(500).send("Erreur lors de la prédiction");
    }
    // output devrait être du JSON
    try {
      const data = JSON.parse(output);
      res.json(data);
    } catch(e) {
      console.error("Parse JSON error:", e);
      res.status(500).send("Erreur parsing JSON");
    }
  });
});

// prediction 2.0
app.get('/predictions', (req, res) => {
    console.log('Démarrage des prédictions...');
    
    const pyshell = new PythonShell('predict.py', PYTHON_OPTIONS);

    let output = "";
    pyshell.on('message', (message) => {
        console.log("[PYTHON]", message);
        output += message + "\n";
    });

    pyshell.on('stderr', (stderr) => {
        console.error('[PYTHON ERROR]', stderr);
    });

    pyshell.on('error', (err) => {
        console.error('Erreur lors de l\'exécution du script Python:', err);
        return res.render('predictions', {
            error: {
                message: err.message,
                details: output
            },
            groupedArray: [],
            roundIndex: 0,
            currentRoundData: null,
            totalRounds: 0
        });
    });

    pyshell.end((err, code, signal) => {
        if (err) {
            console.error('Erreur lors des prédictions:', err);
            return res.render('predictions', {
                error: {
                    message: err.message,
                    details: output
                },
                groupedArray: [],
                roundIndex: 0,
                currentRoundData: null,
                totalRounds: 0
            });
        }

        try {
            // Prendre la dernière ligne non vide comme résultat JSON
            const jsonOutput = output.split('\n')
                .filter(line => line.trim())
                .pop();
            
            const predictions = JSON.parse(jsonOutput);
            
            if (predictions.error) {
                return res.status(500).render('predictions', {
                    error: predictions.error,
                    groupedArray: [],
                    roundIndex: 0,
                    currentRoundData: null,
                    totalRounds: 0
                });
            }

            // Grouper par "round" (journée)
            const grouped = {};
            predictions.forEach(match => {
                const journee = match.round || "N/A";
                if (!grouped[journee]) grouped[journee] = [];
                grouped[journee].push(match);
            });

            // Transformer en tableau [{ round: "...", matches: [...]}, ...]
            const groupedArray = Object.keys(grouped).map(r => ({
                round: r,
                matches: grouped[r]
            }));

            // Navigation par roundIndex
            let roundIndex = parseInt(req.query.roundIndex, 10) || 0;
            if (roundIndex < 0) roundIndex = 0;
            if (roundIndex >= groupedArray.length) roundIndex = groupedArray.length - 1;

            // Récupérer l'objet { round, matches } pour la journée courante
            let currentRoundData = groupedArray.length > 0 ? groupedArray[roundIndex] : null;

            res.render('predictions', {
                error: null, // Toujours définir error, même si null
                groupedArray,
                roundIndex,
                currentRoundData,
                totalRounds: groupedArray.length,
                timestamp: new Date().toISOString()
            });
            
            console.log("Nombre de journées distinctes:", groupedArray.length);

        } catch (parseError) {
            console.error('Erreur lors du parsing JSON:', parseError);
            res.status(500).render('predictions', {
                error: {
                    message: 'Erreur lors du parsing des résultats',
                    details: output
                },
                groupedArray: [],
                roundIndex: 0,
                currentRoundData: null,
                totalRounds: 0
            });
        }
    });
});

app.get('/train-model', (req, res) => {
    console.log('Démarrage de l\'entraînement du modèle...');
    
    const options = {
        mode: 'text',
        pythonPath: 'python',
        scriptPath: './python'
    };

    PythonShell.run('train_model.py', options).then(messages => {
        console.log('Résultats de l\'entraînement:', messages);
        res.json({
            success: true,
            results: messages
        });
    }).catch(err => {
        console.error('Erreur lors de l\'entraînement:', err);
        res.status(500).json({
            success: false,
            error: err.message
        });
    });
});

app.get('/results', (req, res) => {
  const db = new sqlite3.Database(dbPath);
  // On prend par ex. les 10 derniers matchs joués
  db.all(`SELECT * FROM matches WHERE home_score IS NOT NULL ORDER BY date DESC LIMIT 10`, [], (err, rows) => {
    if (err) {
      return res.status(500).send("DB error");
    }
    db.close();
    res.render('results', { data: rows });
  });
});
// Route d'accueil
app.get('/', (req, res) => {
  // Rendu du template "index" (views/index.ejs)
  res.render('index');
});
app.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}`);
});
