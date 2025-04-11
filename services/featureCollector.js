const weatherService = require('./weatherService');
const playerService = require('./playerService');

class FeatureCollector {
    async collectMatchFeatures(match) {
        const [weatherData, homeTeamPlayers, awayTeamPlayers] = await Promise.all([
            weatherService.getWeatherForMatch(match.stadium, match.date),
            playerService.getKeyPlayersStatus(match.home_team, match.date),
            playerService.getKeyPlayersStatus(match.away_team, match.date)
        ]);

        return {
            // Features météo
            weather_temp: weatherData.temperature,
            weather_rain: weatherData.precipitation,
            weather_wind: weatherData.wind_speed,
            
            // Features joueurs
            home_missing_key_players: homeTeamPlayers.missingKeyPlayers,
            away_missing_key_players: awayTeamPlayers.missingKeyPlayers,
            
            // Autres features existantes
            ...match
        };
    }
}

module.exports = new FeatureCollector();