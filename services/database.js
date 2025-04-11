const sqlite3 = require('sqlite3').verbose();
const config = require('../config/config');

class Database {
    constructor() {
        this.dbPath = config.PATHS.DB;
    }

    async connect() {
        return new Promise((resolve, reject) => {
            this.db = new sqlite3.Database(this.dbPath, (err) => {
                if (err) reject(err);
                else resolve(this.db);
            });
        });
    }

    async query(sql, params = []) {
        const db = await this.connect();
        return new Promise((resolve, reject) => {
            db.all(sql, params, (err, rows) => {
                if (err) reject(err);
                else resolve(rows);
            });
        });
    }

    async run(sql, params = []) {
        const db = await this.connect();
        return new Promise((resolve, reject) => {
            db.run(sql, params, function(err) {
                if (err) reject(err);
                else resolve(this);
            });
        });
    }

    async close() {
        if (this.db) {
            return new Promise((resolve, reject) => {
                this.db.close(err => {
                    if (err) reject(err);
                    else resolve();
                });
            });
        }
    }
}

module.exports = new Database();