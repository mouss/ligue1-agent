# Ligue 1 Agent 🎯⚽

Application de prédiction des scores de matchs de Ligue 1 utilisant le Machine Learning.

## Fonctionnalités

- 🤖 Prédiction des scores avec Random Forest
- 📊 Interface utilisateur moderne et intuitive
- 🔄 Mise à jour automatique des données via RapidAPI Football
- 📱 Design responsive

## Technologies utilisées

- Backend : Node.js/Express
- Machine Learning : Python (Random Forest)
- Base de données : SQLite
- Frontend : EJS, Bootstrap
- API : RapidAPI Football

## Installation

1. Clonez le repository
```bash
git clone https://github.com/mouss/ligue1-agent.git
cd ligue1-agent
```

2. Installez les dépendances
```bash
npm install
pip install -r requirements.txt
```

3. Configurez vos variables d'environnement
```bash
cp .env.example .env
# Éditez .env avec vos clés API
```

4. Lancez l'application
```bash
npm start
```

## Structure du projet

- `/routes` - Routes Express
- `/models` - Modèles ML et logique métier
- `/views` - Templates EJS
- `/public` - Assets statiques
- `/db` - Base de données SQLite

## Licence

MIT