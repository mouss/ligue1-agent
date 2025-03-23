import os
import requests
from dotenv import load_dotenv

load_dotenv()

class FootballAPIClient:
    def __init__(self):
        self.api_key = os.getenv('RAPIDAPI_KEY')
        self.api_host = os.getenv('RAPIDAPI_HOST')
        self.base_url = f"https://{self.api_host}"
        
    def _make_request(self, endpoint, params=None):
        headers = {
            'x-rapidapi-host': self.api_host,
            'x-rapidapi-key': self.api_key
        }
        response = requests.get(
            f"{self.base_url}/{endpoint}",
            headers=headers,
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    def get_team_injuries(self, team_id, date):
        """Récupère les blessures/suspensions d'une équipe"""
        try:
            return self._make_request('injuries', {
                'team': team_id,
                'date': date.strftime('%Y-%m-%d')
            })
        except Exception as e:
            print(f"Erreur lors de la récupération des blessures : {e}")
            return {'response': []}
            
    def get_team_fixtures(self, team_id, last=10):
        """Récupère les derniers matchs d'une équipe"""
        try:
            return self._make_request('fixtures', {
                'team': team_id,
                'last': last
            })
        except Exception as e:
            print(f"Erreur lors de la récupération des matchs : {e}")
            return {'response': []}