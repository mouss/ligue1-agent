/************************************************
 * index.js (vraiment en Node.js / Express)
 ************************************************/
const express = require('express');
const sqlite3 = require('sqlite3').verbose();
const axios = require('axios');
const path = require('path');
const { PythonShell } = require('python-shell');
const app = express();
const PORT = 3000;


// EJS setup
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// Middlewares
app.use(express.json());

// Config API-Football (v3) - la plupart des gens utilisent : api-football-v1.p.rapidapi.com/v3
const RAPIDAPI_KEY = "c16a3bd85cmsh57c4e77612f35fep1b54b0jsnc50c626d3ff5";  // <-- Remplacez
const RAPIDAPI_HOST = "api-football-v1.p.rapidapi.com"; // ou v3.football.api-sports.io
const LIGUE1_ID = 61;
const SEASON_YEAR = 2024;
const BASE_URL = `https://${RAPIDAPI_HOST}/v3/fixtures`;

// SQLite
const DB_PATH = path.join(__dirname, 'ligue1.db');

/************************************************
 * ROUTE 1 : Accueil
 ************************************************/
app.get('/', (req, res) => {
  res.render('index');
});

/************************************************
 * ROUTE 2 : /fetch-rounds
 * Récupère la liste des journées (rounds) via
 * l'endpoint /v3/fixtures/rounds
 * Param ?current=true|false (optionnel)
 ************************************************/
 app.get('/fetch-rounds', async (req, res) => {
   try {
     const currentParam = req.query.current === 'true' ? 'true' : 'false';

     const options = {
       method: 'GET',
       url: `${BASE_URL}/rounds`,
       params: {
         league: LIGUE1_ID,
         season: SEASON_YEAR,
         current: currentParam
       },
       headers: {
         'x-rapidapi-key': RAPIDAPI_KEY,
         'x-rapidapi-host': RAPIDAPI_HOST
       }
     };

     const response = await axios.request(options);

     if (response.status === 200) {
       const data = response.data;
       const rounds = data.response || [];
       console.log(rounds);
       // Rendu du template fetch_rounds.ejs en passant le tableau rounds
       return res.render('fetch_rounds', { rounds: rounds });
     } else {
       return res.status(500).json({
         error: `Erreur API-Football /rounds status ${response.status}`
       });
     }
   } catch (error) {
     console.error(error);
     return res.status(500).json({ error: String(error) });
   }
 });


/************************************************
 * ROUTE 3 : /fetch-matches-by-round
 * Récupère les matchs d'une journée (ex: "Regular Season - 2")
 * Param ?round=... & insère dans la DB table `matches`
 ************************************************/
app.get('/fetch-matches-by-round', async (req, res) => {
  const roundName = req.query.round;

  if (!roundName) {
    return res.status(400).json({
      error: "Param ?round=... manquant (ex: 'Regular Season - 2')"
    });
  }

  try {
    const options = {
      method: 'GET',
      url: `${BASE_URL}`,
      params: {
        league: LIGUE1_ID,
        season: SEASON_YEAR,
        round: roundName
      },
      headers: {
        'x-rapidapi-key': RAPIDAPI_KEY,
        'x-rapidapi-host': RAPIDAPI_HOST
      }
    };

    const response = await axios.request(options);
    if (response.status === 200) {
      const fixtures = response.data.response || [];

      // Insertion en base
      const db = new sqlite3.Database(DB_PATH);
      // Créer la table matches si pas encore
      db.run(`
        CREATE TABLE IF NOT EXISTS matches (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          fixture_id INTEGER,
          date TEXT,
          round TEXT,
          home_team TEXT,
          away_team TEXT,
          home_score INTEGER,
          away_score INTEGER
        )
      `);

      const stmt = db.prepare(`
        INSERT INTO matches
        (fixture_id, date, round, home_team, away_team, home_score, away_score)
        VALUES (?, ?, ?, ?, ?, ?, ?)
      `);

      fixtures.forEach(fix => {
        const fixtureId = fix.fixture.id;
        const dateMatch = fix.fixture.date;
        const leagueRound = fix.league.round; // ex: "Regular Season - 2"
        const homeTeam = fix.teams.home.name;
        const awayTeam = fix.teams.away.name;
        const homeScore = fix.goals.home;
        const awayScore = fix.goals.away;

        stmt.run([
          fixtureId,
          dateMatch,
          leagueRound,
          homeTeam,
          awayTeam,
          homeScore,
          awayScore
        ]);
      });

      stmt.finalize();
      db.close();

      res.json({
        message: `Inserted ${fixtures.length} fixture(s) for round=${roundName}`,
        nb_fixtures: fixtures.length
      });
    } else {
      res.status(500).json({
        error: `Erreur API-Football status ${response.status}`
      });
    }
  } catch (error) {
    console.error(error);
    res.status(500).json({ error: String(error) });
  }
});

/************************************************
 * ROUTE 4 : /train
 * (Exemple) - Pour entraîner ou réentraîner le modèle
 ************************************************/
 app.get('/train', (req, res) => {
   const scriptPath = path.join(__dirname, 'python', 'train_model.py');
   let pyshell = new PythonShell(scriptPath);

   pyshell.on('message', (message) => {
     console.log("[PYTHON]", message);
   });

   pyshell.end((err, code, signal) => {
     if (err) {
       console.error(err);
       return res.status(500).send("Erreur lors de l'entraînement");
   }
   res.send("Entraînement terminé. Consultez la console pour les logs.");
 });
 });

/************************************************
 * ROUTE 5 : /predict
 * (Exemple) - Pour prédire
 ************************************************/
 app.get('/predictions', (req, res) => {
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
     try {
       const predictions = JSON.parse(output);

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

       // -- Navigation par roundIndex --
       // On récupère le param ?roundIndex=... (ou 0 par défaut)
       let roundIndex = parseInt(req.query.roundIndex, 10) || 0;

       // Limiter roundIndex si trop grand ou trop petit
       if (roundIndex < 0) roundIndex = 0;
       if (roundIndex >= groupedArray.length) roundIndex = groupedArray.length - 1;

       // Récupérer l'objet { round, matches } pour la journée courante
       let currentRoundData = null;
       if (groupedArray.length > 0) {
         currentRoundData = groupedArray[roundIndex];
       }

       // On passe tout ça au template EJS
       res.render('predictions', {
         groupedArray,   // la liste complète (si vous voulez s'en servir)
         roundIndex,     // l'indice courant
         currentRoundData,
         totalRounds: groupedArray.length
       });



     } catch (e) {
       console.error("JSON parse error:", e);
       res.status(500).send("Erreur parsing JSON");
     }
   });
 });

 app.get('/display-matches-by-round', (req, res) => {
   const round = req.query.round; // Ex: "Regular Season - 2"
   if (!round) {
     return res.status(400).send("Paramètre ?round=... manquant");
   }

   // Exemple : récupérer les matchs depuis la base SQLite
   const sqlite3 = require('sqlite3').verbose();
   const path = require('path');
   const DB_PATH = path.join(__dirname, 'ligue1.db');

   let db = new sqlite3.Database(DB_PATH);
   db.all("SELECT fixture_id, date, home_team, away_team, home_score, away_score FROM matches WHERE round = ?", [round], (err, rows) => {
     if (err) {
       db.close();
       return res.status(500).json({ error: err.message });
     }
     db.close();
     res.render('matches_by_round', { round: round, matches: rows });
   });
 });




/************************************************
 * Lancement du serveur
 ************************************************/
app.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}`);
});
