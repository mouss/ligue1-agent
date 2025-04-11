// index.js
require('dotenv').config();
const express = require('express');
const axios = require('axios');
const sqlite3 = require('sqlite3').verbose();
const app = express();
const path = require('path');
const { PythonShell } = require('python-shell');
const fs = require('fs');
const WebSocket = require('ws');
const server = require('http').createServer(app);
const wss = new WebSocket.Server({ server });
const { spawn } = require('child_process');

// Constantes
const PORT = 3000;
const PYTHON_SCRIPT_PATH = path.join(__dirname, 'python', 'train_model.py');
const MODEL_PATH = path.join(__dirname, 'python', 'ligue1_model.pkl');
const RAPIDAPI_KEY = process.env.RAPIDAPI_KEY;
const RAPIDAPI_HOST = process.env.RAPIDAPI_HOST;
const LIGUE1_ID = 61;
const SEASON = 2024;

// Configuration d'Express
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));
app.use('/images', express.static(path.join(__dirname, 'public', 'images')));
app.use(express.static(path.join(__dirname, 'public')));

// Middleware pour logger les requêtes
app.use((req, res, next) => {
    console.log(`${req.method} ${req.url}`);
    next();
});

// Stocker les connexions WebSocket actives
const clients = new Set();
let currentProgress = 0;

wss.on('connection', (ws) => {
    clients.add(ws);
    
    // Envoyer le progrès actuel au nouveau client
    ws.send(JSON.stringify({
        type: 'progress',
        percent: currentProgress
    }));
    
    ws.on('close', () => {
        clients.delete(ws);
    });
});

// Fonction pour envoyer des mises à jour à tous les clients
function broadcastUpdate(data) {
    clients.forEach(client => {
        if (client.readyState === WebSocket.OPEN) {
            client.send(JSON.stringify(data));
        }
    });
}

function updateProgress(step, totalSteps = 10) {
    currentProgress = Math.min(Math.round((step / totalSteps) * 100), 100);
    broadcastUpdate({
        type: 'progress',
        percent: currentProgress
    });
}

// Fonction pour démarrer l'entraînement
function startTraining() {
    currentProgress = 0;
    updateProgress(0);
    
    const pythonProcess = new PythonShell(PYTHON_SCRIPT_PATH, { mode: 'text' });
    
    pythonProcess.on('message', (message) => {
        broadcastUpdate({
            type: 'log',
            message: message
        });
        
        // Mise à jour de la progression basée sur les étapes
        if (message.includes('Chargement des données')) {
            updateProgress(1);
        } else if (message.includes('Statistiques calculées')) {
            updateProgress(2);
        } else if (message.includes('Features générées')) {
            updateProgress(3);
        } else if (message.includes('Split des données')) {
            updateProgress(4);
        } else if (message.includes('Optimisation pour le modèle Domicile')) {
            updateProgress(5);
        } else if (message.includes('Optimisation pour le modèle Extérieur')) {
            updateProgress(6);
        } else if (message.includes('Entraînement des modèles finaux')) {
            updateProgress(7);
        } else if (message.includes('Résultats d\'évaluation')) {
            updateProgress(8);
        } else if (message.includes('Features les plus importantes')) {
            updateProgress(9);
        } else if (message.includes('Modèle sauvegardé')) {
            updateProgress(10);
        }
    });
    
    pythonProcess.on('error', (err) => {
        broadcastUpdate({
            type: 'error',
            message: `Erreur: ${err.message}`
        });
    });
    
    pythonProcess.on('close', () => {
        broadcastUpdate({
            type: 'log',
            message: 'Processus terminé'
        });
    });
}

// Configuration des chemins
const ROOT_DIR = __dirname;
const PYTHON_DIR = path.join(ROOT_DIR, 'python');
const DB_DIR = path.join(ROOT_DIR, 'db');
const VIEWS_DIR = path.join(ROOT_DIR, 'views');

// Création du dossier db s'il n'existe pas
if (!fs.existsSync(DB_DIR)) {
    fs.mkdirSync(DB_DIR);
}

const dbPath = path.join(DB_DIR, 'ligue1.db');

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

        res.render('operation-status', {
            title: 'Récupération des Matchs',
            status: 'success',
            message: 'Les matchs ont été récupérés et sauvegardés avec succès',
            details: [
                `${fixtures.length} matchs récupérés`,
                'Base de données mise à jour',
                'Opération terminée avec succès'
            ]
        });

    } catch (error) {
        console.error('Erreur lors de la récupération des matchs:', error);
        res.render('operation-status', {
            title: 'Erreur - Récupération des Matchs',
            status: 'error',
            message: 'Une erreur est survenue lors de la récupération des matchs',
            details: [error.message]
        });
    } finally {
        if (db) {
            db.close();
        }
    }
});

app.get('/train', async (req, res) => {
    try {
        // Lancer le script d'entraînement
        const scriptPath = path.join(__dirname, 'python', 'train_model.py');
        const process = spawn('python3', [scriptPath]);
        
        let output = [];
        let error = null;

        process.stdout.on('data', (data) => {
            console.log(`[PYTHON OUTPUT] ${data}`);
            output.push(data.toString());
        });

        process.stderr.on('data', (data) => {
            console.error(`[PYTHON ERROR] ${data}`);
            if (!error) error = '';
            error += data.toString();
        });

        process.on('close', (code) => {
            if (code === 0) {
                res.render('operation-status', {
                    title: 'Entraînement du Modèle',
                    status: 'success',
                    message: 'Le modèle a été entraîné avec succès',
                    details: output
                });
            } else {
                res.render('operation-status', {
                    title: 'Erreur - Entraînement du Modèle',
                    status: 'error',
                    message: 'Une erreur est survenue lors de l\'entraînement du modèle',
                    details: error ? [error] : ['Code d\'erreur: ' + code]
                });
            }
        });
    } catch (error) {
        console.error('Erreur lors de l\'entraînement:', error);
        res.render('operation-status', {
            title: 'Erreur - Entraînement du Modèle',
            status: 'error',
            message: 'Une erreur est survenue lors de l\'entraînement du modèle',
            details: [error.message]
        });
    }
});

app.get('/predictions', (req, res) => {
    console.log('Démarrage des prédictions...');
    
    const scriptPath = path.join(__dirname, 'python', 'predict.py');
    console.log('Chemin du script Python:', scriptPath);
    
    const options = {
        mode: 'text',
        pythonPath: '/Library/Developer/CommandLineTools/usr/bin/python3',
        scriptPath: path.dirname(scriptPath),
        pythonOptions: ['-u']  // Mode unbuffered
    };

    console.log('Options Python:', options);

    let pyshell = new PythonShell(path.basename(scriptPath), options);
    let output = '';

    pyshell.on('message', function (message) {
        console.log('Message reçu du script Python:', message);
        output += message;
    });

    pyshell.on('stderr', function (stderr) {
        console.error('Stderr Python:', stderr);
    });

    pyshell.on('error', function(err) {
        console.error('Erreur Python Shell:', err);
    });

    pyshell.end(function (err) {
        if (err) {
            console.error('Erreur de prédiction:', err);
            return res.render('operation-status', {
                status: 'error',
                title: 'Erreur de prédiction',
                message: 'Une erreur est survenue lors de la prédiction',
                details: [err.message]
            });
        }

        try {
            console.log('Sortie brute reçue:', output);
            
            // S'assurer que la sortie n'est pas vide
            if (!output || !output.trim()) {
                throw new Error('Aucune donnée reçue du script Python');
            }

            const predictions = JSON.parse(output.trim());
            console.log('Prédictions parsées:', predictions);
            
            if (!Array.isArray(predictions)) {
                throw new Error('Format de prédictions invalide');
            }

            // Dédupliquer les prédictions
            const uniquePredictions = predictions.filter((pred, index) => {
                return predictions.findIndex(p => 
                    p.home_team === pred.home_team && 
                    p.away_team === pred.away_team && 
                    p.date === pred.date
                ) === index;
            });

            // Trier par date
            uniquePredictions.sort((a, b) => new Date(a.date) - new Date(b.date));

            console.log('Nombre de prédictions uniques:', uniquePredictions.length);

            // Rendu du template avec les données
            return res.render('predictions', {
                title: 'Prédictions Ligue 1',
                message: uniquePredictions.length > 0 ? `${uniquePredictions.length} matchs prédits` : 'Aucune prédiction disponible',
                predictions: uniquePredictions || []
            });

        } catch (parseError) {
            console.error('Erreur lors du parsing JSON:', parseError);
            console.error('Sortie brute:', output);
            return res.render('operation-status', {
                status: 'error',
                title: 'Erreur de parsing',
                message: 'Erreur lors du parsing des résultats',
                details: [parseError.message, 'Voir les logs pour plus de détails']
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

app.get('/update-status', (req, res) => {
    res.render('update-status');
});

app.post('/train', (req, res) => {
    startTraining();
    res.json({ status: 'started' });
});

// Route d'accueil
app.get('/', (req, res) => {
    // Rendu du template "index" (views/index.ejs)
    res.render('index');
});

app.listen(PORT, () => {
    console.log(`Server running at http://localhost:${PORT}`);
});
