const { spawn } = require('child_process');
const config = require('../config/config');
const WebSocketManager = require('../services/websocket');
const { PythonShell } = require('python-shell');
const path = require('path');
const fs = require('fs');

function normalizeTeamName(name) {
    if (!name) return '';

    // Table de correspondance pour les cas spéciaux
    const replacements = {
        'LE Havre': 'le_havre',
        'Le Havre': 'le_havre',
        'Paris Saint Germain': 'paris_saint_germain',
        'Paris Saint-Germain': 'paris_saint_germain',
        'PSG': 'paris_saint_germain',
        'Saint Etienne': 'saint_etienne',
        'Saint-Etienne': 'saint_etienne',
        'Stade Brestois 29': 'stade_brestois_29',
        'Stade Brestois': 'stade_brestois_29'
    };

    // Log du nom original
    console.log('Normalisation de:', name);

    // Si le nom existe dans la table de correspondance, l'utiliser
    if (replacements[name]) {
        console.log('Trouvé dans la table de correspondance:', replacements[name]);
        return replacements[name];
    }

    // Sinon, normaliser le nom
    const normalized = name
        .toLowerCase()
        .replace(/[\s-]+/g, '_')        // Remplace les espaces et tirets par des underscores
        .replace(/[^a-z0-9_]/g, '')     // Supprime tous les caractères spéciaux sauf les underscores
        .replace(/^le_/, '')            // Supprime le préfixe "le_"
        .replace(/^stade_/, '')         // Supprime le préfixe "stade_"
        .replace(/^as_/, '');           // Supprime le préfixe "as_"

    console.log('Normalisé en:', normalized);
    return normalized;
}

exports.trainModel = async (req, res) => {
    try {
        const pythonProcess = spawn('python3', [config.PATHS.PYTHON_SCRIPT]);
        
        pythonProcess.stdout.on('data', (data) => {
            WebSocketManager.broadcast({
                type: 'log',
                message: data.toString()
            });
        });

        pythonProcess.stderr.on('data', (data) => {
            WebSocketManager.broadcast({
                type: 'error',
                message: data.toString()
            });
        });

        pythonProcess.on('close', (code) => {
            if (code === 0) {
                res.render('operation-status', {
                    status: 'success',
                    title: 'Entraînement du modèle',
                    message: 'Le modèle a été entraîné avec succès',
                    details: ['Le modèle est prêt à être utilisé']
                });
            } else {
                res.render('operation-status', {
                    status: 'error',
                    title: 'Erreur',
                    message: 'Erreur lors de l\'entraînement du modèle',
                    details: [`Code de sortie : ${code}`]
                });
            }
        });
    } catch (error) {
        res.render('operation-status', {
            status: 'error',
            title: 'Erreur',
            message: 'Erreur lors de l\'entraînement du modèle',
            details: [error.message]
        });
    }
};

exports.getPredictions = async (req, res) => {
    try {
        const pythonScriptPath = path.join(__dirname, '..', 'python', 'predict.py');
        console.log('Démarrage des prédictions...');
        console.log('Chemin du script Python:', pythonScriptPath);

        const options = {
            mode: 'json',  
            pythonPath: '/Library/Developer/CommandLineTools/usr/bin/python3',
            scriptPath: path.join(__dirname, '..', 'python'),
            pythonOptions: ['-u']
        };

        console.log('Options Python:', JSON.stringify(options, null, 2));

        let pythonLogs = [];
        const pyshell = new PythonShell('predict.py', options);

        pyshell.stderr.on('data', (stderr) => {
            console.log('Log Python:', stderr);
            pythonLogs.push(stderr);
        });

        pyshell.on('message', (predictions) => {
            try {
                if (predictions.error) {
                    console.error('Erreur Python:', predictions.error);
                    return res.status(500).json({ 
                        error: predictions.error,
                        logs: pythonLogs
                    });
                }

                console.log('Données brutes reçues du script Python:', JSON.stringify(predictions, null, 2));

                const uniquePredictions = {};
                predictions.forEach(pred => {
                    const key = `${pred.date}_${pred.home_team}_${pred.away_team}`;
                    if (!uniquePredictions[key] || pred.match_id < uniquePredictions[key].match_id) {
                        uniquePredictions[key] = pred;
                    }
                });

                console.log('Prédictions uniques:', JSON.stringify(uniquePredictions, null, 2));

                const sortedPredictions = Object.values(uniquePredictions)
                    .sort((a, b) => new Date(a.date) - new Date(b.date))
                    .map(pred => {
                        // Log des données brutes
                        console.log('=== Traitement de la prédiction ===');
                        console.log('Équipe domicile:', pred.home_team);
                        console.log('Équipe extérieur:', pred.away_team);

                        // Normaliser les noms d'équipes pour l'affichage
                        const normalizedHomeTeam = normalizeTeamName(pred.home_team);
                        const normalizedAwayTeam = normalizeTeamName(pred.away_team);

                        // Debug des scores
                        console.log('Scores bruts:', {
                            home: pred.predicted_home_score,
                            away: pred.predicted_away_score
                        });

                        // Retourner le résultat final
                        const result = {
                            ...pred,
                            home_team: pred.home_team,
                            away_team: pred.away_team,
                            predicted_home_score: pred.predicted_home_score,
                            predicted_away_score: pred.predicted_away_score,
                            home_score_rounded: Math.round(pred.predicted_home_score),
                            away_score_rounded: Math.round(pred.predicted_away_score),
                            // Calcul de l'indice de confiance basé sur plusieurs facteurs
                            confidence: Math.round(
                                // Base de 70% pour toute prédiction
                                70 +
                                // Bonus/Malus basé sur la forme des équipes (max ±15%)
                                (((pred.home_team_form || 0) + (pred.away_team_form || 0)) / 2) * 15 +
                                // Bonus/Malus basé sur la précision historique (max ±15%)
                                (Math.random() * 15)  // À remplacer par une vraie métrique de précision historique
                            )
                        };

                        console.log('Résultat final:', JSON.stringify(result, null, 2));
                        console.log('===========================');

                        return result;
                    });

                console.log('Envoi à la vue:', {
                    predictions: sortedPredictions.slice(0, 2),  // Affiche seulement les 2 premières prédictions pour la lisibilité
                    title: 'Prédictions Ligue 1'
                });

                res.render('predictions', { 
                    predictions: sortedPredictions,
                    title: 'Prédictions Ligue 1',
                    logs: pythonLogs
                });
            } catch (error) {
                console.error('Erreur de traitement:', error);
                res.status(500).json({ 
                    error: 'Erreur lors du traitement des prédictions',
                    details: error.message,
                    logs: pythonLogs
                });
            }
        });

        pyshell.on('error', (error) => {
            console.error('Erreur d\'exécution Python:', error);
            res.status(500).json({ 
                error: 'Erreur lors de l\'exécution du script Python',
                details: error.message,
                logs: pythonLogs
            });
        });

        pyshell.end((err) => {
            if (err) {
                console.error('Erreur de fin d\'exécution Python:', err);
                res.status(500).json({ 
                    error: 'Erreur lors de la finalisation du script Python',
                    details: err.message,
                    logs: pythonLogs
                });
            }
        });

    } catch (error) {
        console.error('Erreur générale:', error);
        res.status(500).json({ 
            error: error.message,
            logs: []
        });
    }
};