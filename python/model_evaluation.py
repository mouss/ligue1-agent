import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.graph_objects as go
from sklearn.metrics import mean_absolute_error, mean_squared_error
import os
import json

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'ligue1.db')

class ModelEvaluator:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self._init_db()
        
    def _init_db(self):
        """Initialise la base de données si nécessaire"""
        cursor = self.conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            fixture_id INTEGER PRIMARY KEY,
            date TEXT,
            home_team TEXT,
            away_team TEXT,
            home_score_pred REAL,
            away_score_pred REAL,
            home_win_prob REAL,
            draw_prob REAL,
            away_win_prob REAL,
            prediction_date TEXT
        )
        """)
        self.conn.commit()
        
    def get_predictions_vs_actual(self, start_date=None, end_date=None):
        """Récupère les prédictions et les résultats réels"""
        # Vérifions d'abord les tables disponibles
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print("\nTables disponibles dans la base de données:")
        for table in tables:
            print(f"- {table[0]}")
            
        # Comptons les entrées dans chaque table
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
            count = cursor.fetchone()[0]
            print(f"Nombre d'entrées dans {table[0]}: {count}")

        # Vérifions les prédictions existantes
        print("\nExemple de prédictions existantes:")
        cursor.execute("""
        SELECT fixture_id, date, home_team, away_team, home_score_pred, away_score_pred 
        FROM predictions 
        LIMIT 5
        """)
        predictions = cursor.fetchall()
        for pred in predictions:
            print(f"Match {pred[2]} vs {pred[3]} le {pred[1]}: {pred[4]}-{pred[5]}")
        
        query = """
        SELECT 
            m.fixture_id,
            m.date,
            m.home_team,
            m.away_team,
            m.home_score,
            m.away_score,
            p.home_score_pred,
            p.away_score_pred,
            p.home_win_prob,
            p.draw_prob,
            p.away_win_prob
        FROM matches m
        INNER JOIN predictions p ON m.fixture_id = p.fixture_id
        WHERE m.home_score IS NOT NULL
        """
        
        if start_date:
            query += f" AND m.date >= '{start_date}'"
        if end_date:
            query += f" AND m.date <= '{end_date}'"
            
        query += " ORDER BY m.date"
        
        print("\nExécution de la requête SQL:")
        print(query)
        
        df = pd.read_sql_query(query, self.conn)
        print(f"\nNombre de lignes récupérées: {len(df)}")
        print("Colonnes avec des valeurs non-null:")
        print(df.count())
        
        if len(df) == 0:
            print("\nAucune correspondance entre les prédictions et les résultats réels.")
            print("Vérifions les IDs des matchs:")
            cursor.execute("SELECT DISTINCT fixture_id FROM matches WHERE home_score IS NOT NULL")
            match_ids = set([r[0] for r in cursor.fetchall()])
            cursor.execute("SELECT DISTINCT fixture_id FROM predictions")
            pred_ids = set([r[0] for r in cursor.fetchall()])
            print(f"\nNombre de matchs avec résultats: {len(match_ids)}")
            print(f"Nombre de matchs avec prédictions: {len(pred_ids)}")
            print(f"Matchs en commun: {len(match_ids.intersection(pred_ids))}")
        
        return df
    
    def _prepare_data(self, df):
        """Prépare les données pour l'évaluation"""
        df_clean = df.dropna(subset=['home_score', 'away_score', 'home_score_pred', 'away_score_pred'])
        
        if len(df_clean) == 0:
            return None
            
        # Calculer les résultats réels et prédits
        df_clean['actual_result'] = df_clean.apply(
            lambda x: 'H' if x['home_score'] > x['away_score'] else 
                     'D' if x['home_score'] == x['away_score'] else 'A', 
            axis=1
        )
        df_clean['predicted_result'] = df_clean.apply(
            lambda x: 'H' if x['home_score_pred'] > x['away_score_pred'] else 
                     'D' if abs(x['home_score_pred'] - x['away_score_pred']) < 0.5 else 'A', 
            axis=1
        )
        
        return df_clean
    
    def calculate_metrics(self, df):
        """Calcule les métriques de performance"""
        df_clean = self._prepare_data(df)
        
        if df_clean is None:
            print("Attention: Aucune donnée valide pour calculer les métriques")
            return {
                'mae_home': None,
                'mae_away': None,
                'rmse_home': None,
                'rmse_away': None,
                'accuracy': None
            }
        
        # Calculer les métriques
        mae_home = mean_absolute_error(df_clean['home_score'], df_clean['home_score_pred'])
        mae_away = mean_absolute_error(df_clean['away_score'], df_clean['away_score_pred'])
        rmse_home = np.sqrt(mean_squared_error(df_clean['home_score'], df_clean['home_score_pred']))
        rmse_away = np.sqrt(mean_squared_error(df_clean['away_score'], df_clean['away_score_pred']))
        accuracy = (df_clean['actual_result'] == df_clean['predicted_result']).mean()
        
        return {
            'mae_home': mae_home,
            'mae_away': mae_away,
            'rmse_home': rmse_home,
            'rmse_away': rmse_away,
            'accuracy': accuracy
        }
    
    def plot_score_distribution(self, df, save_path=None):
        """Crée un graphique de distribution des scores prédits vs réels"""
        # Filtrer les valeurs NaN
        df_clean = df.dropna(subset=['home_score', 'away_score', 'home_score_pred', 'away_score_pred'])
        
        if len(df_clean) == 0:
            print("Attention: Pas assez de données pour générer les distributions")
            return
            
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        # Distribution des scores à domicile
        sns.kdeplot(data=df_clean, x='home_score', label='Réel', ax=ax1)
        sns.kdeplot(data=df_clean, x='home_score_pred', label='Prédit', ax=ax1)
        ax1.set_title('Distribution des scores à domicile')
        ax1.legend()
        
        # Distribution des scores à l'extérieur
        sns.kdeplot(data=df_clean, x='away_score', label='Réel', ax=ax2)
        sns.kdeplot(data=df_clean, x='away_score_pred', label='Prédit', ax=ax2)
        ax2.set_title("Distribution des scores à l'extérieur")
        ax2.legend()
        
        if save_path:
            plt.savefig(save_path)
        plt.close()
    
    def plot_prediction_accuracy(self, df, save_path=None):
        """Génère un graphique montrant l'évolution de la précision des prédictions"""
        df_clean = self._prepare_data(df)
        
        if df_clean is None or len(df_clean) < 5:
            print("Attention: Pas assez de données pour générer le graphique de précision")
            return
        
        df_clean['correct'] = df_clean['actual_result'] == df_clean['predicted_result']
        df_clean['date'] = pd.to_datetime(df_clean['date'])
        df_clean = df_clean.sort_values('date')
        
        # Calculer la précision mobile
        window_size = min(10, len(df_clean))
        rolling_accuracy = df_clean['correct'].rolling(window=window_size, min_periods=1).mean()
        
        plt.figure(figsize=(12, 6))
        plt.plot(df_clean['date'], rolling_accuracy, label=f'Précision mobile (fenêtre de {window_size} matchs)')
        plt.axhline(y=rolling_accuracy.mean(), color='r', linestyle='--', label='Précision moyenne')
        
        plt.title('Évolution de la précision des prédictions')
        plt.xlabel('Date')
        plt.ylabel('Précision')
        plt.legend()
        plt.grid(True)
        
        if save_path:
            plt.savefig(save_path)
            plt.close()
        else:
            plt.show()
    
    def create_confusion_matrix(self, df, save_path=None):
        """Crée une matrice de confusion pour les résultats des matchs"""
        df_clean = self._prepare_data(df)
        
        if df_clean is None:
            print("Attention: Pas assez de données pour générer la matrice de confusion")
            return
        
        # Créer la matrice de confusion
        confusion = pd.crosstab(
            df_clean['actual_result'], 
            df_clean['predicted_result'],
            normalize='index'
        )
        
        plt.figure(figsize=(10, 8))
        sns.heatmap(confusion, annot=True, fmt='.2%', cmap='Blues')
        plt.title('Matrice de confusion des prédictions')
        plt.xlabel('Prédiction')
        plt.ylabel('Réalité')
        
        if save_path:
            plt.savefig(save_path)
            plt.close()
        else:
            plt.show()
    
    def evaluate_and_save_report(self, output_dir, start_date=None, end_date=None):
        """Génère et sauvegarde un rapport complet d'évaluation"""
        os.makedirs(output_dir, exist_ok=True)
        
        # Récupération des données
        df = self.get_predictions_vs_actual(start_date, end_date)
        
        # Calcul des métriques
        metrics = self.calculate_metrics(df)
        
        # Génération des visualisations
        self.plot_score_distribution(df, os.path.join(output_dir, 'score_distribution.png'))
        self.plot_prediction_accuracy(df, os.path.join(output_dir, 'prediction_accuracy.png'))
        self.create_confusion_matrix(df, os.path.join(output_dir, 'confusion_matrix.png'))
        
        # Sauvegarde des métriques dans un fichier JSON
        with open(os.path.join(output_dir, 'metrics.json'), 'w') as f:
            json.dump(metrics, f, indent=4)
        
        return metrics

if __name__ == "__main__":
    evaluator = ModelEvaluator()
    
    # Exemple d'utilisation
    output_dir = os.path.join(os.path.dirname(__file__), '..', 'evaluation_reports')
    metrics = evaluator.evaluate_and_save_report(output_dir)
    
    print("\nMétriques de performance:")
    for metric, value in metrics.items():
        if value is None:
            print(f"{metric}: Pas de données")
        elif isinstance(value, float):
            print(f"{metric}: {value:.3f}")
        else:
            print(f"{metric}: {value}")