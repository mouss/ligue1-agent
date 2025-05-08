const path = require('path');
const db = require('../services/database');
const api = require('../services/api');
const syncDatabase = require('../services/syncDatabase');
const { spawn } = require('child_process');
const express = require('express');
const { PythonShell } = require('python-shell');

exports.fetchMatches = async (req, res) => {
    try {
        // Utiliser le nouveau script de synchronisation
        await syncDatabase();
        
        res.render('operation-status', {
            status: 'success',
            title: 'Mise à jour des données',
            message: 'Les données ont été synchronisées avec succès',
            details: ['Base de données mise à jour avec les derniers matchs']
        });
    } catch (error) {
        res.render('operation-status', {
            status: 'error',
            title: 'Erreur',
            message: 'Erreur lors de la synchronisation des données',
            details: [error.message]
        });
    }
};

exports.predictUpcoming = async (req, res) => {
    try {
        console.log("Démarrage des prédictions...");
        
        // Utiliser le script predict.py
        const scriptPath = path.join(__dirname, '..', 'python', 'predict.py');
        console.log("Chemin du script Python:", scriptPath);
        
        const pythonProcess = spawn('python3', [scriptPath]);
        let predictions = '';
        let errors = '';

        pythonProcess.stdout.on('data', (data) => {
            predictions += data.toString();
            console.log("Sortie Python:", data.toString());
        });

        pythonProcess.stderr.on('data', (data) => {
            const text = data.toString();
            if (text.includes('FutureWarning')) {
                return; // Ignorer les avertissements de dépréciation
            }
            errors += text;
            console.error("Erreur Python:", text);
        });

        const exitCode = await new Promise((resolve) => {
            pythonProcess.on('close', resolve);
        });

        if (exitCode !== 0) {
            throw new Error(errors || 'Erreur lors de la prédiction des matchs');
        }

        try {
            // Nettoyer la sortie JSON pour s'assurer qu'elle est valide
            const cleanedPredictions = predictions.trim();
            const predictedMatches = JSON.parse(cleanedPredictions);
            
            if (!Array.isArray(predictedMatches)) {
                throw new Error('Format de prédiction invalide');
            }

            // Formater les prédictions pour l'affichage
            const formattedPredictions = predictedMatches.map(match => ({
                ...match,
                date: new Date(match.date).toLocaleDateString('fr-FR', {
                    weekday: 'long',
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric'
                }),
                predicted_home_score: Math.round(match.predicted_home_score * 100) / 100,
                predicted_away_score: Math.round(match.predicted_away_score * 100) / 100,
                confidence_percent: Math.round(match.confidence * 100)
            }));

            // Trier les prédictions par date
            formattedPredictions.sort((a, b) => new Date(a.date) - new Date(b.date));

            res.render('predictions', {
                predictions: formattedPredictions,
                title: 'Prédictions des matchs',
                error: null
            });

        } catch (parseError) {
            console.error('Erreur de parsing JSON:', parseError);
            console.error('Contenu reçu:', predictions);
            res.render('predictions', {
                predictions: [],
                title: 'Erreur de prédiction',
                error: 'Erreur lors du traitement des prédictions: ' + parseError.message
            });
        }

    } catch (error) {
        console.error("Erreur de prédiction:", error);
        res.render('predictions', {
            predictions: [],
            title: 'Erreur de prédiction',
            error: error.message
        });
    }
};

exports.trainModel = async (req, res) => {
    try {
        console.log("Démarrage de l'entraînement...");
        
        const pythonProcess = spawn('python3', ['python/train_model.py']);
        let output = '';
        let errors = '';

        pythonProcess.stdout.on('data', (data) => {
            const text = data.toString();
            output += text;
            console.log("Sortie Python:", text);
        });

        pythonProcess.stderr.on('data', (data) => {
            const text = data.toString();
            if (text.includes('RuntimeWarning') || text.includes('FutureWarning')) {
                // Ignorer les avertissements connus
                return;
            }
            errors += text;
            console.error("Erreur Python:", text);
        });

        const exitCode = await new Promise((resolve) => {
            pythonProcess.on('close', resolve);
        });

        if (exitCode !== 0) {
            throw new Error(errors || "Erreur lors de l'entraînement du modèle");
        }

        // Extraire les métriques du modèle
        let metrics = null;
        try {
            const metricsMatch = output.match(/Métriques finales:\s*({[\s\S]*})/);
            if (metricsMatch) {
                metrics = JSON.parse(metricsMatch[1]);
            }
        } catch (e) {
            console.error("Erreur lors de l'extraction des métriques:", e);
        }

        res.render('training', {
            success: true,
            title: 'Entraînement du modèle',
            message: 'Le modèle a été entraîné avec succès',
            metrics: metrics,
            error: null,
            output: output
        });

    } catch (error) {
        console.error("Erreur d'entraînement:", error);
        res.render('training', {
            success: false,
            title: 'Erreur d\'entraînement',
            message: 'Une erreur est survenue lors de l\'entraînement du modèle',
            metrics: null,
            error: error.message,
            output: output
        });
    }
};