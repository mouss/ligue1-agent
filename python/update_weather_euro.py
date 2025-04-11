import os
import sqlite3
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv

load_dotenv()

# Configuration
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'ligue1.db')
WEATHER_API_KEY = os.getenv('WEATHER_API_KEY')
FOOTBALL_API_KEY = os.getenv('RAPIDAPI_KEY')
FOOTBALL_API_HOST = os.getenv('RAPIDAPI_HOST')

def update_database_schema():
    """Met à jour le schéma de la base de données pour les tables météo et matchs européens"""
    with open(os.path.join(os.path.dirname(__file__), '..', 'db', 'schema_weather_euro.sql'), 'r') as f:
        sql_script = f.read()
    
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(sql_script)
        conn.commit()
        print("Schéma de la base de données mis à jour avec succès!")
    except sqlite3.Error as e:
        print(f"Erreur lors de la mise à jour du schéma : {e}")
        conn.rollback()
    finally:
        conn.close()

def get_stadium_coordinates():
    """Récupère les coordonnées des stades pour chaque équipe"""
    # Coordonnées des stades de Ligue 1 (à compléter avec les vraies coordonnées)
    return {
        'Paris Saint Germain': {'lat': 48.8414, 'lon': 2.2530},
        'Marseille': {'lat': 43.2696, 'lon': 5.3956},
        'Lyon': {'lat': 45.7234, 'lon': 4.8520},
        'Monaco': {'lat': 43.7308, 'lon': 7.4159},
        'Lille': {'lat': 50.6127, 'lon': 3.1302},
        # Ajouter les autres équipes...
    }

def fetch_weather_data(lat, lon, date):
    """Récupère les prévisions météo pour un stade"""
    url = f"http://api.weatherapi.com/v1/forecast.json"
    params = {
        'key': WEATHER_API_KEY,
        'q': f"{lat},{lon}",
        'days': 7,
        'aqi': 'no'
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        # Convertir la date au format ISO en datetime
        if '+' in date:
            target_date = datetime.strptime(date.split('+')[0], '%Y-%m-%dT%H:%M:%S')
        else:
            target_date = datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
            
        target_date_str = target_date.strftime('%Y-%m-%d')
        
        for day in data['forecast']['forecastday']:
            if day['date'] == target_date_str:
                # Trouver l'heure la plus proche
                hour = min(day['hour'], 
                         key=lambda x: abs(datetime.strptime(x['time'], '%Y-%m-%d %H:%M') - target_date))
                
                return {
                    'temperature': hour['temp_c'],
                    'precipitation': hour['chance_of_rain'],
                    'wind_speed': hour['wind_kph'],
                    'weather_condition': hour['condition']['text']
                }
        
        return None
    except Exception as e:
        print(f"Erreur lors de la récupération des données météo : {e}")
        return None

def fetch_european_matches():
    """Récupère les matchs européens des équipes de Ligue 1"""
    url = f"https://{FOOTBALL_API_HOST}/v3/fixtures"
    headers = {
        'X-RapidAPI-Key': FOOTBALL_API_KEY,
        'X-RapidAPI-Host': FOOTBALL_API_HOST
    }
    
    # IDs des compétitions européennes dans l'API
    competitions = [2, 3]  # 2: Champions League, 3: Europa League
    
    european_matches = []
    for competition in competitions:
        try:
            params = {
                'league': competition,
                'season': '2024-2025',  # Format correct pour la saison
                'from': datetime.now().strftime('%Y-%m-%d'),
                'to': (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            }
            
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            if 'response' in data:
                for match in data['response']:
                    # Vérifier si une équipe est de Ligue 1
                    if match['league']['country'] == 'France':
                        european_matches.append({
                            'team': match['teams']['home']['name'] if match['teams']['home']['country'] == 'France' else match['teams']['away']['name'],
                            'date': datetime.strptime(match['fixture']['date'], '%Y-%m-%dT%H:%M:%S%z'),
                            'competition': 'UEFA Champions League' if competition == 2 else 'UEFA Europa League'
                        })
        except Exception as e:
            print(f"Erreur lors de la récupération des matchs européens : {e}")
    
    return european_matches

def update_weather_data():
    """Met à jour les données météo pour les prochains matchs"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Récupérer les matchs à venir
        cursor.execute("""
            SELECT date, home_team
            FROM matches 
            WHERE date > datetime('now')
            AND date < datetime('now', '+7 days')
        """)
        upcoming_matches = cursor.fetchall()
        
        stadium_coords = get_stadium_coordinates()
        
        # Mettre à jour les conditions météo
        for match_date, home_team in upcoming_matches:
            if home_team in stadium_coords:
                coords = stadium_coords[home_team]
                weather = fetch_weather_data(coords['lat'], coords['lon'], match_date)
                
                if weather:
                    cursor.execute("""
                        INSERT OR REPLACE INTO stadium_conditions 
                        (match_date, temperature, precipitation, wind_speed, weather_condition)
                        VALUES (?, ?, ?, ?, ?)
                    """, (match_date, weather['temperature'], weather['precipitation'],
                          weather['wind_speed'], weather['weather_condition']))
        
        conn.commit()
        print("Données météo mises à jour avec succès!")
        
    except sqlite3.Error as e:
        print(f"Erreur lors de la mise à jour des données météo : {e}")
        conn.rollback()
    finally:
        conn.close()

def update_european_matches():
    """Met à jour les données des matchs européens"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Supprimer les anciens matchs
        cursor.execute("DELETE FROM european_matches WHERE match_date < datetime('now')")
        
        # Récupérer et insérer les nouveaux matchs
        european_matches = fetch_european_matches()
        for match in european_matches:
            cursor.execute("""
                INSERT OR REPLACE INTO european_matches (team, match_date, competition)
                VALUES (?, ?, ?)
            """, (match['team'], match['date'], match['competition']))
        
        conn.commit()
        print("Données des matchs européens mises à jour avec succès!")
        
    except sqlite3.Error as e:
        print(f"Erreur lors de la mise à jour des matchs européens : {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    update_database_schema()
    update_weather_data()
    update_european_matches()
