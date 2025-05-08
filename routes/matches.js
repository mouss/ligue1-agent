const express = require('express');
const router = express.Router();
const matchesController = require('../controllers/matches');

router.get('/fetch', matchesController.fetchMatches);
router.get('/predictions', matchesController.predictUpcoming);
router.get('/train', matchesController.trainModel);

module.exports = router;