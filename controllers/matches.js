const path = require('path');
const db = require('../services/database');
const api = require('../services/api');

exports.fetchMatches = async (req, res) => {
    try {
        // Récupérer les matchs depuis l'API
        const fixtures = await api.fetchFixtures();
        
        // Préparer la requête d'insertion
        for (const fix of fixtures) {
            await db.run(
                `REPLACE INTO matches (fixture_id, date, home_team, away_team, home_score, away_score, round)
                 VALUES (?, ?, ?, ?, ?, ?, ?)`,
                [
                    fix.fixture.id,
                    fix.fixture.date,
                    fix.teams.home.name,
                    fix.teams.away.name,
                    fix.goals.home,
                    fix.goals.away,
                    fix.league.round
                ]
            );
        }

        res.render('operation-status', {
            status: 'success',
            title: 'Récupération des matchs',
            message: 'Les matchs ont été mis à jour avec succès',
            details: [`${fixtures.length} matchs récupérés`]
        });
    } catch (error) {
        res.render('operation-status', {
            status: 'error',
            title: 'Erreur',
            message: 'Erreur lors de la récupération des matchs',
            details: [error.message]
        });
    }
};

exports.predictUpcoming = async (req, res) => {
    const { PythonShell } = require('python-shell');
    const config = require('../config/config');

    try {
        console.log("Démarrage des prédictions...");
        
        const options = {
            mode: 'json',
            pythonPath: 'python3',
            scriptPath: path.dirname(config.PATHS.PYTHON_SCRIPT)
        };

        PythonShell.run('predict.py', options, (err, results) => {
            if (err) {
                console.error('Erreur de prédiction:', err);
                res.render('operation-status', {
                    status: 'error',
                    title: 'Erreur de prédiction',
                    message: 'Une erreur est survenue lors de la prédiction',
                    details: [err.message]
                });
                return;
            }
            
            try {
                // Le script Python renvoie directement un tableau de prédictions
                const predictions = results;
                if (!Array.isArray(predictions) || predictions.length === 0) {
                    throw new Error('Format de prédictions invalide');
                }

                // Trier les prédictions par date
                predictions.sort((a, b) => new Date(a.date) - new Date(b.date));

                res.render('predictions', { 
                    predictions,
                    title: 'Prédictions des matchs',
                    message: `${predictions.length} prédictions générées`
                });
            } catch (parseError) {
                console.error('Erreur lors du parsing des résultats:', parseError);
                console.error('Résultats reçus:', results);
                res.render('operation-status', {
                    status: 'error',
                    title: 'Erreur de parsing',
                    message: 'Erreur lors du parsing des résultats',
                    details: [parseError.message, 'Voir les logs pour plus de détails']
                });
            }
        });
    } catch (error) {
        console.error('Erreur:', error);
        res.render('operation-status', {
            status: 'error',
            title: 'Erreur',
            message: 'Erreur lors de la prédiction',
            details: [error.message]
        });
    }
};