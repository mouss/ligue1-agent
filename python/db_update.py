import sqlite3
import os

def update_database_schema():
    # Chemin vers la base de données
    db_path = os.path.join(os.path.dirname(__file__), '..', 'db', 'ligue1.db')
    
    # Lire le fichier SQL
    with open(os.path.join(os.path.dirname(__file__), '..', 'db', 'schema_update.sql'), 'r') as f:
        sql_script = f.read()
    
    # Connexion à la base de données
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Exécuter les commandes SQL
        cursor.executescript(sql_script)
        
        # Vérifier si la migration est nécessaire
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='matches_new'")
        if cursor.fetchone():
            # Renommer l'ancienne table
            cursor.execute("ALTER TABLE matches RENAME TO matches_old")
            # Renommer la nouvelle table
            cursor.execute("ALTER TABLE matches_new RENAME TO matches")
            # Supprimer l'ancienne table
            cursor.execute("DROP TABLE matches_old")
            print("Migration de la table matches réussie!")
        
        # Valider les changements
        conn.commit()
        print("Mise à jour du schéma de la base de données réussie!")
        
    except sqlite3.Error as e:
        print(f"Erreur lors de la mise à jour de la base de données : {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    update_database_schema()