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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept-Language': 'pl-PL,pl;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    }
    
    url = 'https://www.filmweb.pl/vod/new/films'
    
    try:
        print(f"Scraping: {url}")
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        movies = []
        
        film_elements = soup.find_all(['div', 'article', 'li'])
        print(f"  Znaleziono {len(film_elements)} elementow")
        
        for item in film_elements[:100]:
            try:
                title = None
                year = None
                platforms = []
                filmweb_url = None
                
                title_elem = item.find('h2') or item.find('h3') or item.find('a', attrs={'title': True})
                
                if title_elem:
                    title = title_elem.get_text(strip=True) or title_elem.get('title')
                
                if not title:
                    link = item.find('a', href=lambda x: x and '/film/' in str(x))
                    if link:
                        title = link.get_text(strip=True) or link.get('title')
                
                if not title or len(title) < 2:
                    continue
                
                title = title.split('(')[0].strip()
                
                year_text = item.find(text=lambda x: x and any(str(y) in str(x) for y in range(2020, 2027)))
                if year_text:
                    for y in range(2020, 2027):
                        if str(y) in str(year_text):
                            year = y
                            break
                
                platform_links = item.find_all('a', href=lambda x: x and 'vod' in str(x).lower())
                for p in platform_links:
                    platform_name = p.get_text(strip=True) or p.get('title') or p.get('alt')
                    if platform_name and len(platform_name) < 40:
                        platforms.append(platform_name)
                
                link = item.find('a', href=lambda x: x and '/film/' in str(x))
                if link:
                    href = link.get('href')
                    if href:
                        if href.startswith('/'):
                            filmweb_url = 'https://www.filmweb.pl' + href
                        elif href.startswith('http'):
                            filmweb_url = href
                
                if title and len(title) > 2:
                    movies.append({
                        'title': title,
                        'year': year,
                        'platforms': list(set(platforms)),
                        'filmweb_url': filmweb_url
                    })
                    platform_str = ', '.join(platforms[:2]) if platforms else 'brak'
                    print(f"  + {title} ({year}) - {platform_str}")
            
            except:
                continue
        
        unique_movies = {}
        for m in movies:
            key = m['title'].lower()
            if key not in unique_movies:
                unique_movies[key] = m
            else:
                if m['platforms']:
                    unique_movies[key]['platforms'].extend(m['platforms'])
                    unique_movies[key]['platforms'] = list(set(unique_movies[key]['platforms']))
        
        return list(unique_movies.values())
    
    except Exception as e:
        print(f"  Blad scraping: {e}")
        return []

def search_tmdb_for_imdb(title, year=None):
    if not TMDB_API_KEY:
        return None
    
    params = {
        'api_key': TMDB_API_KEY,
        'query': title,
        'language': 'pl-PL'
    }
    
    if year:
        params['year'] = year
    
    try:
        response = requests.get(f'{TMDB_BASE_URL}/search/movie', params=params, timeout=10)
        results = response.json().get('results', [])
        
        if results:
            movie = results[0]
            return {
                'tmdb_id': movie['id'],
                'imdb_rating': round(movie.get('vote_average', 0), 1),
                'poster_url': f"{TMDB_IMAGE_BASE}{movie['poster_path']}" if movie.get('poster_path') else None,
                'overview': movie.get('overview'),
                'original_title': movie.get('original_title')
            }
        
        return None
    
    except:
        return None

def enrich_with_tmdb(movies):
    print(f"\nWzbogacanie {len(movies)} filmow danymi z TMDB...")
    enriched = []
    
    for idx, movie in enumerate(movies):
        print(f"  [{idx+1}/{len(movies)}] {movie['title']}...", end=' ')
        
        tmdb_data = search_tmdb_for_imdb(movie['title'], movie.get('year'))
        
        if tmdb_data:
            movie['imdb_rating'] = tmdb_data['imdb_rating']
            movie['poster_url'] = tmdb_data['poster_url']
            movie['overview'] = tmdb_data['overview']
            movie['tmdb_id'] = tmdb_data['tmdb_id']
            movie['original_title'] = tmdb_data['original_title']
            print(f"OK IMDb: {tmdb_data['imdb_rating']}/10")
        else:
            movie['imdb_rating'] = 0
            movie['poster_url'] = None
            movie['overview'] = None
            movie['tmdb_id'] = None
            movie['original_title'] = None
            print("BRAK")
        
        enriched.append(movie)
        
        if (idx + 1) % 10 == 0:
            time.sleep(1)
        else:
            time.sleep(0.2)
    
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
    
    print(f"\nZapisano {len(movies)} filmow do data/streaming.json")

def main():
    print("=" * 70)
    print("Filmweb VOD Scraper + TMDB IMDb Ratings")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    try:
        print("\n1. Scraping Filmwebu VOD...")
        movies = scrape_filmweb_vod()
        
        if len(movies) == 0:
            print("\nBrak filmow ze scrapingu")
            print("Tworze pusty plik jako fallback")
            save_streaming_data([])
            return
        
        print(f"\nZescrapowano {len(movies)} filmow")
        
        print(f"\n2. Pobieranie ocen IMDb z TMDB...")
        enriched = enrich_with_tmdb(movies)
        
        with_ratings = [m for m in enriched if m['imdb_rating'] > 0]
        with_platforms = [m for m in enriched if m['platforms']]
        
        print(f"\nStatystyki:")
        print(f"  Filmow ogolem: {len(enriched)}")
        print(f"  Z ocena IMDb: {len(with_ratings)}")
        print(f"  Z platformami: {len(with_platforms)}")
        
        save_streaming_data(enriched)
        
        print(f"\nTop 10 najlepszych:")
        top_movies = sorted(with_ratings, key=lambda x: x['imdb_rating'], reverse=True)[:10]
        for idx, m in enumerate(top_movies, 1):
            platforms_str = ', '.join(m['platforms'][:2]) if m['platforms'] else 'Brak'
            print(f"  {idx}. {m['title']} ({m.get('year', '?')}) - {m['imdb_rating']}/10 - {platforms_str}")
        
        print("\n" + "=" * 70)
        print("Gotowe!")
        print("=" * 70)
    
    except Exception as e:
        print(f"\nBlad: {e}")
        print("Tworze pusty plik jako fallback")
        save_streaming_data([])

if __name__ == '__main__':
    main()
