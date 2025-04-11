import joblib
import os

MODEL_HOME_PATH = os.path.join(os.path.dirname(__file__), 'model_new_home')
MODEL_AWAY_PATH = os.path.join(os.path.dirname(__file__), 'model_new_away')

try:
    print("Tentative de chargement du modèle home...")
    with open(MODEL_HOME_PATH, 'rb') as f:
        content = f.read(100)  # Lire les 100 premiers octets
        print(f"Premiers octets du fichier home: {content[:20]}")
    
    model_home = joblib.load(MODEL_HOME_PATH)
    print("Modèle home chargé avec succès!")
    print(f"Type du modèle: {type(model_home)}")
    
    print("\nTentative de chargement du modèle away...")
    model_away = joblib.load(MODEL_AWAY_PATH)
    print("Modèle away chargé avec succès!")
    print(f"Type du modèle: {type(model_away)}")
    
except Exception as e:
    print(f"Erreur détaillée: {str(e)}")
