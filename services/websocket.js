const WebSocket = require('ws');

class WebSocketManager {
    constructor(server) {
        this.wss = new WebSocket.Server({ server });
        this.setupHandlers();
    }

    setupHandlers() {
        this.wss.on('connection', (ws) => {
            console.log('Nouveau client WebSocket connecté');
            ws.on('message', this.handleMessage.bind(this));
        });
    }

    handleMessage(message) {
        const data = JSON.parse(message);
        console.log('Message reçu:', data);
    }

    broadcast(data) {
        this.wss.clients.forEach(client => {
            if (client.readyState === WebSocket.OPEN) {
                client.send(JSON.stringify(data));
            }
        });
    }
}

module.exports = WebSocketManager;