import os
import sqlite3
from datetime import datetime

# Chemin de la base de données
DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
DB_PATH = os.path.join(DB_DIR, 'database.sqlite')

def init_database():
    """Initialise la base de données avec les tables nécessaires"""
    
    # Créer le dossier data s'il n'existe pas
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)
    
    # Connexion à la base de données
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Création de la table des matchs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        home_team TEXT NOT NULL,
        away_team TEXT NOT NULL,
        home_score INTEGER,
        away_score INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Insertion de quelques données de test
    test_data = [
        ('2024-03-01', 'PSG', 'Marseille', 3, 0),
        ('2024-03-01', 'Lyon', 'Monaco', 2, 1),
        ('2024-03-08', 'Marseille', 'Lyon', 1, 1),
        ('2024-03-08', 'Monaco', 'PSG', 0, 2),
        ('2024-03-15', 'PSG', 'Lyon', 2, 0),
        ('2024-03-15', 'Monaco', 'Marseille', 1, 2),
        ('2024-03-22', 'Lyon', 'Marseille', 2, 2),
        ('2024-03-22', 'PSG', 'Monaco', 3, 1),
        ('2024-03-29', 'PSG', 'Lyon', None, None),
        ('2024-03-29', 'Marseille', 'Monaco', None, None)
    ]
    
    cursor.executemany(
        "INSERT OR IGNORE INTO matches (date, home_team, away_team, home_score, away_score) VALUES (?, ?, ?, ?, ?)",
        test_data
    )
    
    conn.commit()
    conn.close()
    
    print(f"Base de données initialisée avec succès dans {DB_PATH}")
    print(f"Données de test insérées : {len(test_data)} matchs")

if __name__ == "__main__":
    init_database()
