// services/featureEngineering.js
const axios = require('axios');
const db = require('./database');

class FeatureEngineeringService {
    // Face-à-face historique
    async getHeadToHeadStats(homeTeam, awayTeam) {
        const sql = `
            SELECT 
                AVG(CASE WHEN home_team = ? THEN home_goals ELSE away_goals END) as avg_goals_scored,
                AVG(CASE WHEN home_team = ? THEN away_goals ELSE home_goals END) as avg_goals_conceded,
                COUNT(*) as total_matches
            FROM matches 
            WHERE (home_team = ? AND away_team = ?) 
               OR (home_team = ? AND away_team = ?)
            AND date >= date('now', '-2 years')
        `;
        return await db.query(sql, [homeTeam, homeTeam, homeTeam, awayTeam, awayTeam, homeTeam]);
    }

    // Données de blessures et suspensions
    async getTeamAvailability(team) {
        const endpoint = `${config.API.BASE_URL}/injuries`;
        const response = await axios.get(endpoint, {
            params: { team: team },
            headers: config.API.HEADERS
        });
        return {
            injured_players: response.data.injuries.length,
            suspended_players: response.data.suspensions.length,
            key_players_missing: this.analyzeKeyPlayersMissing(response.data)
        };
    }

    // Fatigue d'équipe
    async getTeamFatigue(team) {
        const sql = `
            SELECT 
                COUNT(*) as recent_matches,
                SUM(CASE WHEN competition_type = 'EUROPEAN' THEN 1 ELSE 0 END) as european_matches
            FROM matches 
            WHERE (home_team = ? OR away_team = ?)
            AND date >= date('now', '-30 days')
        `;
        const matchLoad = await db.query(sql, [team, team]);
        return {
            fatigue_index: this.calculateFatigueIndex(matchLoad),
            european_load: matchLoad.european_matches > 0
        };
    }

    // Performance domicile/extérieur
    async getHomeAwayPerformance(team, isHome) {
        const sql = `
            SELECT 
                AVG(goals_scored) as avg_goals,
                AVG(goals_conceded) as avg_conceded,
                COUNT(CASE WHEN is_win = 1 THEN 1 END) * 100.0 / COUNT(*) as win_percentage
            FROM (
                SELECT 
                    CASE 
                        WHEN home_team = ? THEN home_goals 
                        ELSE away_goals 
                    END as goals_scored,
                    CASE 
                        WHEN home_team = ? THEN away_goals 
                        ELSE home_goals 
                    END as goals_conceded,
                    CASE 
                        WHEN (home_team = ? AND home_goals > away_goals)
                        OR (away_team = ? AND away_goals > home_goals)
                        THEN 1 ELSE 0 
                    END as is_win
                FROM matches
                WHERE ${isHome ? 'home_team' : 'away_team'} = ?
                AND date >= date('now', '-1 year')
            )
        `;
        return await db.query(sql, [team, team, team, team, team]);
    }

    // Données météo
    async getWeatherData(matchDate, stadium) {
        const weatherApi = `${config.WEATHER_API.URL}/forecast`;
        const response = await axios.get(weatherApi, {
            params: {
                location: stadium,
                date: matchDate
            },
            headers: config.WEATHER_API.HEADERS
        });
        return {
            precipitation: response.data.precipitation,
            temperature: response.data.temperature,
            wind_speed: response.data.wind_speed,
            weather_condition: response.data.condition
        };
    }

    // Agrégation des features
    async generateEnhancedFeatures(match) {
        const {home_team, away_team, date, stadium} = match;
        
        const [
            h2h,
            homeAvailability,
            awayAvailability,
            homeFatigue,
            awayFatigue,
            homePerf,
            awayPerf,
            weather
        ] = await Promise.all([
            this.getHeadToHeadStats(home_team, away_team),
            this.getTeamAvailability(home_team),
            this.getTeamAvailability(away_team),
            this.getTeamFatigue(home_team),
            this.getTeamFatigue(away_team),
            this.getHomeAwayPerformance(home_team, true),
            this.getHomeAwayPerformance(away_team, false),
            this.getWeatherData(date, stadium)
        ]);

        return {
            // Features historiques
            h2h_home_goals_avg: h2h.avg_goals_scored,
            h2h_away_goals_avg: h2h.avg_goals_conceded,
            h2h_matches_count: h2h.total_matches,

            // Features de disponibilité
            home_injured_players: homeAvailability.injured_players,
            home_suspended_players: homeAvailability.suspended_players,
            home_key_players_missing: homeAvailability.key_players_missing,
            away_injured_players: awayAvailability.injured_players,
            away_suspended_players: awayAvailability.suspended_players,
            away_key_players_missing: awayAvailability.key_players_missing,

            // Features de fatigue
            home_fatigue_index: homeFatigue.fatigue_index,
            home_european_load: homeFatigue.european_load,
            away_fatigue_index: awayFatigue.fatigue_index,
            away_european_load: awayFatigue.european_load,

            // Features de performance
            home_goals_avg: homePerf.avg_goals,
            home_conceded_avg: homePerf.avg_conceded,
            home_win_percentage: homePerf.win_percentage,
            away_goals_avg: awayPerf.avg_goals,
            away_conceded_avg: awayPerf.avg_conceded,
            away_win_percentage: awayPerf.win_percentage,

            // Features météo
            weather_precipitation: weather.precipitation,
            weather_temperature: weather.temperature,
            weather_wind_speed: weather.wind_speed,
            weather_condition: weather.weather_condition
        };
    }
}

module.exports = new FeatureEngineeringService();