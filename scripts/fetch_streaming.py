#!/usr/bin/env python3
import requests
import json
import os
from datetime import datetime, timedelta

RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY')
TMDB_API_KEY = os.getenv('TMDB_API_KEY')
TMDB_BASE_URL = 'https://api.themoviedb.org/3'
TMDB_IMAGE_BASE = 'https://image.tmdb.org/t/p/w500'

STREAMING_API_URL = 'https://streaming-availability.p.rapidapi.com/changes'

PLATFORM_MAP = {
    'netflix': 'Netflix',
    'hbo': 'HBO Max',
    'disney': 'Disney+',
    'prime': 'Amazon Prime',
    'apple': 'Apple TV+',
    'canal': 'Canal+',
    'skyshowtime': 'SkyShowtime'
}

def fetch_new_releases_from_streaming_api():
    if not RAPIDAPI_KEY:
        print("Brak RAPIDAPI_KEY")
        return []
    
    headers = {
        'X-RapidAPI-Key': RAPIDAPI_KEY,
        'X-RapidAPI-Host': 'streaming-availability.p.rapidapi.com'
    }
    
    params = {
        'country': 'pl',
        'change_type': 'new',
        'item_type': 'movie',
        'catalogs': 'netflix.subscription,hbo.subscription,disney.subscription,prime.subscription,apple.subscription',
        'show_type': 'movie',
        'output_language': 'pl'
    }
    
    try:
        print("Pobieranie nowosci z Streaming Availability API...")
        response = requests.get(STREAMING_API_URL, headers=headers, params=params, timeout=20)
        response.raise_for_status()
        
        data = response.json()
        changes = data.get('changes', [])
        
        print(f"  Znaleziono {len(changes)} nowosci")
        
        movies = []
        for item in changes[:50]:
            try:
                show = item.get('show', {})
                streaming_info = item.get('streamingInfo', {})
                
                title = show.get('title')
                if not title:
                    continue
                
                platforms = []
                for country_data in streaming_info.values():
                    for service_data in country_data:
                        service = service_data.get('service', '')
                        if service in PLATFORM_MAP:
                            platforms.append(PLATFORM_MAP[service])
                
                year = show.get('year')
                imdb_id = show.get('imdbId')
                tmdb_id = show.get('tmdbId')
                
                movies.append({
                    'title': title,
                    'year': year,
                    'platforms': list(set(platforms)),
                    'imdb_id': imdb_id,
                    'tmdb_id': tmdb_id,
                    'overview': show.get('overview')
                })
                
                print(f"  + {title} ({year}) - {', '.join(platforms)}")
            
            except Exception as e:
                continue
        
        return movies
    
    except Exception as e:
        print(f"  Blad API: {e}")
        return []

def enrich_with_tmdb(movies):
    print(f"\nWzbogacanie {len(movies)} filmow danymi z TMDB...")
    enriched = []
    
    for idx, movie in enumerate(movies):
        print(f"  [{idx+1}/{len(movies)}] {movie['title']}...", end=' ')
        
        tmdb_id = movie.get('tmdb_id')
        
        if tmdb_id and TMDB_API_KEY:
            try:
                params = {'api_key': TMDB_API_KEY, 'language': 'pl-PL'}
                response = requests.get(f'{TMDB_BASE_URL}/movie/{tmdb_id}', params=params, timeout=10)
                tmdb_data = response.json()
                
                movie['imdb_rating'] = round(tmdb_data.get('vote_average', 0), 1)
                movie['poster_url'] = f"{TMDB_IMAGE_BASE}{tmdb_data['poster_path']}" if tmdb_data.get('poster_path') else None
                movie['overview'] = tmdb_data.get('overview') or movie.get('overview')
                movie['original_title'] = tmdb_data.get('original_title')
                
                print(f"OK - {movie['imdb_rating']}/10")
            except:
                movie['imdb_rating'] = 0
                movie['poster_url'] = None
                movie['original_title'] = None
                print("BRAK")
        else:
            movie['imdb_rating'] = 0
            movie['poster_url'] = None
            movie['original_title'] = None
            print("SKIP")
        
        movie['filmweb_url'] = None
        enriched.append(movie)
    
    enriched.sort(key=lambda x: (len(x['platforms']) > 0, x['imdb_rating']), reverse=True)
    
    return enriched

def save_streaming_data(movies):
    os.makedirs('data', exist_ok=True)
    
    data = {
        'updated_at': datetime.now().isoformat(),
        'count': len(movies),
        'movies': movies
    }
    
    with open('data/streaming.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\nZapisano {len(movies)} filmow")

def main():
    print("=" * 70)
    print("Streaming Availability API Fetcher")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    try:
        print("\n1. Pobieranie nowosci z Streaming Availability API...")
        movies = fetch_new_releases_from_streaming_api()
        
        if len(movies) == 0:
            print("\nBrak nowosci - tworze pusty plik")
            save_streaming_data([])
            return
        
        print(f"\nZnaleziono {len(movies)} filmow")
        
        print("\n2. Wzbogacanie o TMDB...")
        enriched = enrich_with_tmdb(movies)
        
        with_ratings = [m for m in enriched if m['imdb_rating'] > 0]
        with_platforms = [m for m in enriched if m['platforms']]
        
        print(f"\nStatystyki:")
        print(f"  Ogolem: {len(enriched)}")
        print(f"  Z ocena: {len(with_ratings)}")
        print(f"  Z platformami: {len(with_platforms)}")
        
        save_streaming_data(enriched)
        
        print("\nTop 10:")
        for idx, m in enumerate(with_platforms[:10], 1):
            platforms_str = ', '.join(m['platforms'][:2])
            print(f"  {idx}. {m['title']} ({m.get('year', '?')}) - {m['imdb_rating']}/10 - {platforms_str}")
        
        print("\n" + "=" * 70)
        print("Gotowe!")
        print("=" * 70)
    
    except Exception as e:
        print(f"\nBlad: {e}")
        save_streaming_data([])

if __name__ == '__main__':
    main()
