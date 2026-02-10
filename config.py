import os
from dotenv import load_dotenv

load_dotenv()

TMDB_API_KEY = os.getenv('TMDB_API_KEY')
TMDB_BASE_URL = 'https://api.themoviedb.org/3'
TMDB_IMAGE_BASE = 'https://image.tmdb.org/t/p/w500'

# Kanały TV (hardcoded na start)
CHANNELS = [
    {'id': 1, 'name': 'TVN', 'category': 'Ogólne'},
    {'id': 2, 'name': 'Polsat', 'category': 'Ogólne'},
    {'id': 3, 'name': 'TVP1', 'category': 'Publiczne'},
    {'id': 4, 'name': 'HBO', 'category': 'Filmowe'},
    {'id': 5, 'name': 'Ale Kino+', 'category': 'Filmowe'},
]
