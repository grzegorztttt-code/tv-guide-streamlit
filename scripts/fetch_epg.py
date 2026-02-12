#!/usr/bin/env python3
"""
Skrypt do pobierania EPG z EPG.ovh i matchowania z TMDB.
Uruchamiany automatycznie przez GitHub Actions co 6h.
"""

import os
import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import asyncio
import aiohttp
import time

# Konfiguracja
TMDB_API_KEY = os.getenv('TMDB_API_KEY')
TMDB_BASE_URL = 'https://api.themoviedb.org/3'
TMDB_IMAGE_BASE = 'https://image.tmdb.org/t/p/w500'
EPG_URL = 'https://epg.ovh/pltv.xml'

# Kanały filmowe do śledzenia
MOVIE_CHANNELS = [
    'HBO', 'HBO2', 'HBO3', 'Cinemax', 'Cinemax2',
    'Filmbox', 'Filmbox Premium', 'Filmbox Extra HD',
    'Canal+ Premium', 'Canal+ Film', 'Canal+ Family',
    'AXN', 'AXN White', 'AXN Black', 
    'TVN', 'TVN7', 'Polsat', 'TVP1', 'TVP2',
    'Comedy Central', 'Ale Kino+', 'Kino Polska'
]

def download_epg():
    """Pobiera EPG XML z EPG.ovh"""
    print(f"📡 Pobieranie EPG z {EPG_URL}...")
    response = requests.get(EPG_URL, timeout=60)
    response.raise_for_status()
    print(f"✅ Pobrano {len(response.content) / 1024 / 1024:.1f} MB")
    return response.content

def parse_epg(xml_content):
    """Parsuje XML EPG"""
    print("🔍 Parsowanie XML...")
    root = ET.fromstring(xml_content)
    
    # Kanały
    channels = {}
    for channel in root.findall('.//channel'):
        channel_id = channel.get('id')
        display_name = channel.find('display-name')
        if display_name is not None:
            channels[channel_id] = display_name.text
    
    # Programy
    programs = []
    for programme in root.findall('.//programme'):
        channel_id = programme.get('channel')
        channel_name = channels.get(channel_id, channel_id)
        
        # Filtruj tylko wybrane kanały
        if channel_name not in MOVIE_CHANNELS:
            continue
        
        start = programme.get('start')
        stop = programme.get('stop')
        
        title_elem = programme.find('title')
        title = title_elem.text if title_elem is not None else None
        
        category_elem = programme.find('category')
        category = category_elem.text if category_elem is not None else None
        
        date_elem = programme.find('date')
        year = int(date_elem.text[:4]) if date_elem is not None and date_elem.text else None
        
        if not title:
            continue
        
        try:
            start_dt = datetime.strptime(start[:14], '%Y%m%d%H%M%S')
            stop_dt = datetime.strptime(stop[:14], '%Y%m%d%H%M%S')
        except:
            continue
        
        # Tylko filmy (heurystyka)
        if is_movie(title, category, year):
            programs.append({
                'channel_id': channel_id,
                'channel_name': channel_name,
                'title': title,
                'start_time': start_dt.isoformat(),
                'end_time': stop_dt.isoformat(),
                'category': category,
                'year': year
            })
    
    print(f"✅ Znaleziono {len(programs)} filmów")
    return programs

def is_movie(title, category, year):
    """Sprawdza czy program to film"""
    if not title:
        return False
    
    title_lower = title.lower()
    
    # Wykluczenia
    non_movie = ['wiadomości', 'news', 'pogoda', 'sport', 'serial', 
                 'telenovela', 'show', 'koncert', 'magazyn']
    
    for keyword in non_movie:
        if keyword in title_lower:
            return False
    
    # Pozytywne sygnały
    if category and 'film' in category.lower():
        return True
    
    if year and year < datetime.now().year:
        return True
    
    return False

async def search_tmdb_async(session, title, year=None):
    """Async szukanie w TMDB"""
    if not TMDB_API_KEY:
        return None
    
    clean_title = title.split('(')[0].strip()
    
    params = {
        'api_key': TMDB_API_KEY,
        'query': clean_title,
        'language': 'pl-PL'
    }
    if year:
        params['year'] = year
    
    try:
        async with session.get(f'{TMDB_BASE_URL}/search/movie', params=params, timeout=10) as response:
            data = await response.json()
            results = data.get('results', [])
            if results:
                movie = results[0]
                return {
                    'tmdb_id': movie['id'],
                    'title': movie.get('title'),
                    'year': movie.get('release_date', '')[:4] if movie.get('release_date') else None,
                    'poster': f"{TMDB_IMAGE_BASE}{movie['poster_path']}" if movie.get('poster_path') else None,
                    'rating': movie.get('vote_average'),
                    'overview': movie.get('overview')
                }
            return None
    except:
        return None

async def enrich_with_tmdb(programs):
    """Wzbogaca programy o dane z TMDB (async)"""
    print(f"🎬 Wzbogacanie {len(programs)} filmów danymi z TMDB...")
    
    enriched = []
    batch_size = 20
    
    async with aiohttp.ClientSession() as session:
        for i in range(0, len(programs), batch_size):
            batch = programs[i:i + batch_size]
            
            print(f"  Batch {i//batch_size + 1}/{(len(programs)-1)//batch_size + 1}...")
            
            tasks = [search_tmdb_async(session, p['title'], p['year']) for p in batch]
            results = await asyncio.gather(*tasks)
            
            for program, tmdb_data in zip(batch, results):
                if tmdb_data:
                    program['tmdb'] = tmdb_data
                enriched.append(program)
            
            # Opóźnienie żeby nie przekroczyć rate limit
            await asyncio.sleep(0.5)
    
    # Statystyki
    matched = sum(1 for p in enriched if 'tmdb' in p)
    print(f"✅ Dopasowano {matched}/{len(programs)} filmów z TMDB")
    
    return enriched

def save_to_json(programs):
    """Zapisuje dane do JSON"""
    output_file = 'data/movies.json'
    
    data = {
        'updated_at': datetime.now().isoformat(),
        'count': len(programs),
        'movies': programs
    }
    
    os.makedirs('data', exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"💾 Zapisano {len(programs)} filmów do {output_file}")

def main():
    """Główna funkcja"""
    print("=" * 60)
    print("🤖 EPG Auto-Update Script")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    if not TMDB_API_KEY:
        print("❌ Brak TMDB_API_KEY w secrets!")
        return
    
    try:
        # Pobierz EPG
        xml_content = download_epg()
        
        # Parsuj
        programs = parse_epg(xml_content)
        
        # Ogranicz do 1000 najnowszych filmów (żeby nie było za dużo)
        programs = programs[:1000]
        
        # Wzbogać o TMDB
        enriched = asyncio.run(enrich_with_tmdb(programs))
        
        # Zapisz
        save_to_json(enriched)
        
        print("=" * 60)
        print("✅ Gotowe!")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Błąd: {e}")
        raise

if __name__ == '__main__':
    main()
