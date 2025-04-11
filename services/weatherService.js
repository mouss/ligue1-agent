const axios = require('axios');
const db = require('./database');
const config = require('../config/config');

class WeatherService {
    constructor() {
        this.apiKey = config.WEATHER_API.KEY;
        this.baseUrl = config.WEATHER_API.URL;
    }

    async getWeatherForMatch(stadium, matchDate) {
        try {
            // Vérifier si on a déjà les données en base
            const existingData = await this.getStoredWeatherData(stadium, matchDate);
            if (existingData) return existingData;

            // Sinon, récupérer depuis l'API
            const response = await axios.get(`${this.baseUrl}/forecast`, {
                params: {
                    key: this.apiKey,
                    q: stadium,
                    dt: matchDate
                }
            });

            const weatherData = {
                stadium,
                match_date: matchDate,
                temperature: response.data.forecast.forecastday[0].day.avgtemp_c,
                precipitation: response.data.forecast.forecastday[0].day.totalprecip_mm,
                wind_speed: response.data.forecast.forecastday[0].day.maxwind_kph,
                weather_condition: response.data.forecast.forecastday[0].day.condition.text
            };

            // Sauvegarder en base
            await this.saveWeatherData(weatherData);
            return weatherData;
        } catch (error) {
            console.error('Erreur lors de la récupération des données météo:', error);
            throw error;
        }
    }

    async getStoredWeatherData(stadium, matchDate) {
        const sql = `
            SELECT * FROM stadium_conditions 
            WHERE stadium = ? AND match_date = ?
        `;
        const result = await db.query(sql, [stadium, matchDate]);
        return result[0];
    }

    async saveWeatherData(data) {
        const sql = `
            INSERT INTO stadium_conditions 
            (stadium, match_date, temperature, precipitation, wind_speed, weather_condition)
            VALUES (?, ?, ?, ?, ?, ?)
        `;
        await db.run(sql, [
            data.stadium,
            data.match_date,
            data.temperature,
            data.precipitation,
            data.wind_speed,
            data.weather_condition
        ]);
    }
}

module.exports = new WeatherService();