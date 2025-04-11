const axios = require('axios');
const fs = require('fs');
const path = require('path');

const teams = {
    'Paris Saint Germain': 'https://tmssl.akamaized.net/images/wappen/head/583.png',
    'Marseille': 'https://tmssl.akamaized.net/images/wappen/head/244.png',
    'Lyon': 'https://tmssl.akamaized.net/images/wappen/head/1041.png',
    'Monaco': 'https://tmssl.akamaized.net/images/wappen/head/162.png',
    'Lille': 'https://tmssl.akamaized.net/images/wappen/head/1082.png',
    'Rennes': 'https://tmssl.akamaized.net/images/wappen/head/273.png',
    'Lens': 'https://tmssl.akamaized.net/images/wappen/head/826.png',
    'Nice': 'https://tmssl.akamaized.net/images/wappen/head/417.png',
    'Strasbourg': 'https://tmssl.akamaized.net/images/wappen/head/667.png',
    'Nantes': 'https://tmssl.akamaized.net/images/wappen/head/995.png',
    'Montpellier': 'https://tmssl.akamaized.net/images/wappen/head/969.png',
    'Reims': 'https://tmssl.akamaized.net/images/wappen/head/1421.png',
    'Toulouse': 'https://tmssl.akamaized.net/images/wappen/head/415.png',
    'Stade Brestois 29': 'https://tmssl.akamaized.net/images/wappen/head/3911.png',
    'Clermont': 'https://tmssl.akamaized.net/images/wappen/head/3524.png',
    'Lorient': 'https://tmssl.akamaized.net/images/wappen/head/1158.png',
    'LE Havre': 'https://tmssl.akamaized.net/images/wappen/head/1106.png',
    'Metz': 'https://tmssl.akamaized.net/images/wappen/head/347.png',
    'Saint Etienne': 'https://tmssl.akamaized.net/images/wappen/head/618.png',
    'Angers': 'https://tmssl.akamaized.net/images/wappen/head/1420.png',
    'Auxerre': 'https://tmssl.akamaized.net/images/wappen/head/2904.png'
};

const downloadLogo = async (teamName, url) => {
    const fileName = teamName.toLowerCase().replace(/\s+/g, '_') + '.png';
    const filePath = path.join(__dirname, '..', 'public', 'images', 'teams', fileName);
    
    try {
        const response = await axios({
            url,
            method: 'GET',
            responseType: 'stream',
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://www.transfermarkt.com/',
                'Origin': 'https://www.transfermarkt.com'
            }
        });

        const writer = fs.createWriteStream(filePath);
        response.data.pipe(writer);

        return new Promise((resolve, reject) => {
            writer.on('finish', () => {
                console.log(`✓ Logo téléchargé pour ${teamName}`);
                resolve(fileName);
            });
            writer.on('error', reject);
        });
    } catch (error) {
        console.error(`✗ Erreur lors du téléchargement du logo pour ${teamName}:`, error.message);
        return null;
    }
};

const downloadAllLogos = async () => {
    console.log('Début du téléchargement des logos...\n');
    
    const logoMapping = {};
    for (const [teamName, url] of Object.entries(teams)) {
        const fileName = await downloadLogo(teamName, url);
        if (fileName) {
            logoMapping[teamName] = '/images/teams/' + fileName;
        }
    }
    
    // Mettre à jour le fichier de configuration des logos
    const configPath = path.join(__dirname, '..', 'config', 'team_logos.js');
    const configContent = `// Mapping des logos d'équipes
module.exports = ${JSON.stringify(logoMapping, null, 4)};`;
    
    fs.writeFileSync(configPath, configContent);
    console.log('\nTéléchargement des logos terminé !');
    console.log('Configuration des logos mise à jour.');
};

downloadAllLogos();
