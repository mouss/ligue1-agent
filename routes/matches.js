const express = require('express');
const router = express.Router();
const matchesController = require('../controllers/matches');

router.get('/fetch-matches', matchesController.fetchMatches);
router.get('/predict-upcoming', matchesController.predictUpcoming);

module.exports = router;