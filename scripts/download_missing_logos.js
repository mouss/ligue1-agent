const axios = require('axios');
const fs = require('fs').promises;
const path = require('path');

const LOGOS_DIR = path.join(__dirname, '..', 'public', 'images', 'teams');

// Liste des équipes et leurs URLs de logo
const teams = {
    'auxerre': 'https://upload.wikimedia.org/wikipedia/commons/thumb/e/e9/AJ_Auxerre_Logo.svg/1200px-AJ_Auxerre_Logo.svg.png'
};

async function downloadLogo(team, url) {
    try {
        const response = await axios({
            method: 'get',
            url: url,
            responseType: 'arraybuffer',
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        });

        const logoPath = path.join(LOGOS_DIR, `${team}.png`);
        await fs.writeFile(logoPath, response.data);
        console.log(`✓ Logo téléchargé pour ${team}`);
    } catch (error) {
        console.error(`✗ Erreur lors du téléchargement du logo pour ${team}:`, error.message);
    }
}

async function downloadAllLogos() {
    console.log('Début du téléchargement des logos manquants...');
    
    for (const [team, url] of Object.entries(teams)) {
        await downloadLogo(team, url);
    }
    
    console.log('Téléchargement terminé.');
}

downloadAllLogos();
