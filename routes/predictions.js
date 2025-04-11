const express = require('express');
const router = express.Router();
const predictionsController = require('../controllers/predictions');
const teamLogos = require('../config/team_logos');

// Route principale pour les prédictions
router.get('/', predictionsController.getPredictions);

// Route de test pour les logos
router.get('/test-logos', (req, res) => {
    const testTeams = [
        "Angers",
        "Auxerre",
        "Le Havre",
        "Lens",
        "Lille",
        "Lyon",
        "Marseille",
        "Monaco",
        "Montpellier",
        "Nantes",
        "Nice",
        "Paris Saint-Germain",
        "Reims",
        "Rennes",
        "Saint-Etienne",
        "Stade Brestois 29",
        "Strasbourg",
        "Toulouse"
    ];

    const logos = testTeams.map(team => ({
        team: team,
        logo: teamLogos[team]
    }));

    res.render('test-logos', { logos });
});

// Route pour l'entraînement du modèle
router.post('/train', predictionsController.trainModel);

module.exports = router;