const axios = require('axios');
const config = require('../config/config');

class ApiService {
    constructor() {
        this.baseURL = `https://${config.API.HOST}`;
        this.headers = {
            'x-rapidapi-key': config.API.KEY,
            'x-rapidapi-host': config.API.HOST
        };
    }

    async fetchFixtures() {
        try {
            const response = await axios.get(`${this.baseURL}/v3/fixtures`, {
                params: {
                    league: config.LIGUE1_ID,
                    season: config.SEASON
                },
                headers: this.headers
            });
            return response.data.response;
        } catch (error) {
            throw new Error(`Erreur API: ${error.message}`);
        }
    }
}

module.exports = new ApiService();