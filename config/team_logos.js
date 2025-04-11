// Mapping des logos d'équipes
const defaultLogo = '/images/teams/default_team.png';

// Fonction pour normaliser le nom de fichier
function normalizeFilename(teamName) {
    return teamName
        .toLowerCase()
        .replace(/\s+/g, '_')
        .replace(/[^a-z0-9_]/g, '');
}

const logos = {
    "Angers": "/images/teams/angers.png",
    "Auxerre": "/images/teams/default_team.png",
    "Le Havre": "/images/teams/le_havre.png",
    "Lens": "/images/teams/lens.png",
    "Lille": "/images/teams/lille.png",
    "Lyon": "/images/teams/lyon.png",
    "Marseille": "/images/teams/marseille.png",
    "Monaco": "/images/teams/monaco.png",
    "Montpellier": "/images/teams/montpellier.png",
    "Nantes": "/images/teams/nantes.png",
    "Nice": "/images/teams/nice.png",
    "Paris Saint-Germain": "/images/teams/paris_saint_germain.png",
    "Reims": "/images/teams/reims.png",
    "Rennes": "/images/teams/rennes.png",
    "Saint-Etienne": "/images/teams/saint_etienne.png",
    "Stade Brestois": "/images/teams/stade_brestois_29.png",
    "Strasbourg": "/images/teams/strasbourg.png",
    "Toulouse": "/images/teams/toulouse.png",
    "Clermont": "/images/teams/clermont.png",
    "Lorient": "/images/teams/lorient.png",
    "Metz": "/images/teams/metz.png"
};

// Proxy pour gérer les noms d'équipes manquants et la normalisation des noms de fichiers
module.exports = new Proxy(logos, {
    get: function(target, prop) {
        console.log('Recherche du logo pour:', prop);
        
        // Si le logo existe directement, le retourner
        if (prop in target) {
            console.log('Logo trouvé directement:', target[prop]);
            return target[prop];
        }

        // Essayer de trouver un logo avec le nom normalisé
        const normalizedName = normalizeFilename(prop);
        console.log('Nom normalisé:', normalizedName);
        
        for (const [key, value] of Object.entries(target)) {
            const normalizedKey = normalizeFilename(key);
            console.log('Comparaison avec:', key, '(normalisé:', normalizedKey, ')');
            
            if (normalizedKey === normalizedName) {
                console.log('Logo trouvé par normalisation:', value);
                return value;
            }
        }

        // Si aucun logo n'est trouvé, retourner le logo par défaut
        console.log('Aucun logo trouvé, utilisation du logo par défaut');
        return defaultLogo;
    }
});