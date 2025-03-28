import sqlite3
import pandas as pd
import numpy as np
import joblib
import os
import sys
import json
import warnings
from datetime import datetime

# Filtrer tous les warnings de dépreciation
warnings.filterwarnings('ignore', category=FutureWarning)

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'ligue1.db')
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'ligue1_model.pkl')