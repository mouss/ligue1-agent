const cron = require('node-cron');
const syncDatabase = require('./syncDatabase');

// Synchroniser toutes les 6 heures
console.log('Planification des synchronisations toutes les 6 heures...');
cron.schedule('0 */6 * * *', async () => {
    console.log(`\nDémarrage de la synchronisation planifiée [${new Date().toISOString()}]...`);
    try {
        await syncDatabase();
        console.log('Synchronisation planifiée terminée avec succès');
    } catch (error) {
        console.error('Erreur lors de la synchronisation planifiée:', error);
    }
});

console.log('Service de synchronisation démarré et en attente des prochaines exécutions planifiées.');
