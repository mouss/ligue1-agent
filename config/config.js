require('dotenv').config();
const path = require('path');

module.exports = {
    PORT: 3000,
    LIGUE1_ID: 61,
    SEASON: 2025,
    PATHS: {
        ROOT: path.resolve(__dirname, '..'),
        PYTHON_SCRIPT: path.resolve(__dirname, '../python/train_model.py'),
        MODEL: path.resolve(__dirname, '../python/ligue1_model.pkl'),
        VIEWS: path.resolve(__dirname, '../views'),
        DB: path.resolve(__dirname, '../db/ligue1.db')
    },
    API: {
        KEY: process.env.RAPIDAPI_KEY,
        HOST: process.env.RAPIDAPI_HOST
    },
    WEATHER_API: {
        URL: 'https://api.weatherapi.com/v1',
        KEY: process.env.WEATHER_API_KEY,
        HEADERS: {
            'key': process.env.WEATHER_API_KEY
        }
    },
    FEATURE_ENGINEERING: {
        KEY_PLAYERS_THRESHOLD: 0.8,
        FATIGUE_WINDOW_DAYS: 30,
        WEATHER_IMPACT_THRESHOLD: {
            RAIN: 10,    // mm de pluie
            WIND: 30,    // km/h
            TEMPERATURE: {
                LOW: 5,  // °C
                HIGH: 30 // °C
            }
        },
        FORM_WEIGHTS: {
            LAST_MATCH: 1.0,
            LAST_3_MATCHES: 0.8,
            LAST_5_MATCHES: 0.6
        }
    },
    MODEL_CONFIG: {
        FEATURES: [
            'home_team_form',
            'away_team_form',
            'home_goals_scored_avg',
            'away_goals_scored_avg',
            'home_goals_conceded_avg',
            'away_goals_conceded_avg',
            'weather_temp',
            'weather_rain',
            'weather_wind',
            'home_missing_key_players',
            'away_missing_key_players'
        ]
    }
};