#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import time

TMDB_API_KEY = os.getenv('TMDB_API_KEY')
TMDB_BASE_URL = 'https://api.themoviedb.org/3'
TMDB_IMAGE_BASE = 'https://image.tmdb.org/t/p/w500'

def scrape_filmweb_vod():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'pl-PL,pl;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    }
    
    url = 'https://www.filmweb.pl/vod/new/films'
    
    try:
        print(f"📡 Scraping: {url}")
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        movies = []
        
        film_elements = soup.find_all(['div', 'article', 'li'], class_=lambda x: x and any(k in str(x).lower() for k in ['film', 'movie', 'preview', 'poster', 'tile']))
        
        print(f"  Znaleziono {len(film_elements)} potencjalnych elementów")
        
        for item in film_elements[:100]:
            try:
                title = None
                year = None
                platforms = []
                filmweb_url = None
                
                title_elem = (
                    item.find('h2') or 
                    item.find('h3') or
                    item.find(['a'
