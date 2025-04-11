const db = require('./database');
const config = require('../config/config');

class PlayerService {
    async addPlayerAvailability(playerData) {
        const sql = `
            INSERT INTO player_availability 
            (player_name, team, type, start_date, expected_return_date, is_key_player)
            VALUES (?, ?, ?, ?, ?, ?)
        `;
        await db.run(sql, [
            playerData.player_name,
            playerData.team,
            playerData.type,
            playerData.start_date,
            playerData.expected_return_date,
            playerData.is_key_player
        ]);
    }

    async getTeamAvailability(team, matchDate) {
        const sql = `
            SELECT * FROM player_availability
            WHERE team = ?
            AND start_date <= ?
            AND (expected_return_date >= ? OR expected_return_date IS NULL)
        `;
        return await db.query(sql, [team, matchDate, matchDate]);
    }

    async getKeyPlayersStatus(team, matchDate) {
        const sql = `
            SELECT 
                COUNT(*) as missing_key_players,
                GROUP_CONCAT(player_name) as players_list
            FROM player_availability
            WHERE team = ?
            AND start_date <= ?
            AND (expected_return_date >= ? OR expected_return_date IS NULL)
            AND is_key_player = 1
        `;
        const result = await db.query(sql, [team, matchDate, matchDate]);
        return {
            missingKeyPlayers: result[0].missing_key_players,
            playersList: result[0].players_list ? result[0].players_list.split(',') : []
        };
    }

    async updatePlayerStatus(playerId, returnDate) {
        const sql = `
            UPDATE player_availability
            SET expected_return_date = ?
            WHERE id = ?
        `;
        await db.run(sql, [returnDate, playerId]);
    }
}

module.exports = new PlayerService();