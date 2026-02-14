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

def scrape_filmweb_premieres():
    """Scrapuje nowości z Filmwebu"""
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
    }
    
    movies = []
    urls = [
        'https://www.filmweb.pl/premiery-online',
        'https://www.filmweb.pl/film/nowosci'
    ]
    
    for url in urls:
        try:
            print(f"📡 Scraping: {url}")
            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            film_items = soup.find_all(['div', 'article'], class_=lambda x: x and ('film' in x.lower() or 'preview' in x.lower()))
            
            print(f"  Znaleziono {len(film_items)} elementów")
            
            for item in film_items[:50]:
                try:
                    title = None
                    year = None
                    platforms = []
                    filmweb_url = None
                    
                    title_elem = (
                        item.find('h2') or 
                        item.find('h3') or 
                        item.find('a', class_=lambda x: x and 'title' in x.lower()) or
                        item.find('a', attrs={'data-title': True})
                    )
                    
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        if not title:
                            title = title_elem.get('data-title')
                    
                    if not title:
                        link = item.find('a', href=lambda x: x and '/film/' in x)
                        if link:
                            title = link.get_text(strip=True)
                    
                    if not title or len(title) < 2:
                        continue
                    
                    year_elem = item.find(['span', 'div'], class_=lambda x: x and 'year' in x.lower())
                    if year_elem:
                        year_text = year_elem.get_text(strip=True)
                        try:
                            year = int(''.join(filter(str.isdigit, year_text))[:4])
                        except:
                            pass
                    
                    platform_section = item.find(['div', 'section'], class_=lambda x: x and ('platform' in x.lower() or 'watch' in x.lower() or 'online' in x.lower()))
                    
                    if platform_section:
                        platform_links = platform_section.find_all(['a', 'span', 'div'])
                        for p in platform_links:
                            platform_text = p.get_text(strip=True)
                            if platform_text and len(platform_text) < 30:
                                if any(keyword in platform_text.lower() for keyword in ['netflix', 'hbo', 'disney', 'prime', 'canal', 'apple', 'sky', 'vod']):
                                    platforms.append(platform_text)
                    
                    link = item.find('a', href=lambda x: x and '/film/' in x)
                    if link:
                        href = link.get('href')
                        if href.startswith('/'):
                            filmweb_url = 'https://www.filmweb.pl' + href
                        else:
                            filmweb_url = href
                    
                    if title:
                        movies.append({
                            'title': title,
                            'year': year,
                            'platforms': list(set(platforms)),
                            'filmweb_url': filmweb_url,
                            'source': 'filmweb'
                        })
                        print(f"  ✅ {title} ({year}) - {', '.join(platforms) if platforms else 'brak platform'}")
                
                except Exception as e:
                    continue
            
            print(f"  ✅ Znaleziono {len(movies)} filmów z tego URL")
            time.sleep(2)
        
        except Exception as e:
            print(f"  ❌ Błąd scraping {url}: {e}")
    
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

def search_tmdb_for_imdb(title, year=None):
    """Szuka filmu w TMDB i pobiera ocenę IMDb"""
    
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
    
    except Exception as e:
        print(f"  ⚠️ Błąd TMDB dla {title}: {e}")
        return None

def enrich_with_tmdb(movies):
    """Wzbogaca filmy z Filmwebu o dane z TMDB (oceny IMDb)"""
    
    print("\n🎬 Wzbogacanie o oceny IMDb z TMDB...")
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
            print(f"✅ IMDb: {tmdb_data['imdb_rating']}/10")
        else:
            movie['imdb_rating'] = 0
            movie['poster_url'] = None
            movie['overview'] = None
            movie['tmdb_id'] = None
            movie['original_title'] = None
            print("❌ Nie znaleziono")
        
        enriched.append(movie)
        time.sleep(0.3)
    
    enriched.sort(key=lambda x: (len(x['platforms']) > 0, x['imdb_rating']), reverse=True)
    
    return enriched

def save_streaming_data(movies):
    """Zapisuje dane do JSON"""
    os.makedirs('data', exist_ok=True)
    
    data = {
        'updated_at': datetime.now().isoformat(),
        'count': len(movies),
        'movies': movies
    }
    
    with open('data/streaming.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Zapisano {len(movies)} filmów do data/streaming.json")

def main():
    print("=" * 70)
    print("🎬 Filmweb Scraper + TMDB IMDb Ratings")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    try:
        print("\n1️⃣ Scraping Filmwebu...")
        movies = scrape_filmweb_premieres()
        print(f"\n✅ Zescrapowano {len(movies)} filmów z Filmwebu")
        
        if len(movies) == 0:
            print("⚠️ Brak filmów - możliwe że Filmweb zmienił strukturę")
            print("💡 Spróbuj zaktualizować selektory w skrypcie")
            return
        
        print(f"\n2️⃣ Pobieranie ocen IMDb z TMDB...")
        enriched = enrich_with_tmdb(movies)
        
        with_ratings = [m for m in enriched if m['imdb_rating'] > 0]
        with_platforms = [m for m in enriched if m['platforms']]
        
        print(f"\n📊 Statystyki:")
        print(f"  • Filmów ogółem: {len(enriched)}")
        print(f"  • Z oceną IMDb: {len(with_ratings)}")
        print(f"  • Z platformami: {len(with_platforms)}")
        
        save_streaming_data(enriched)
        
        print(f"\n🏆 Top 10 najlepszych:")
        top_movies = sorted(with_ratings, key=lambda x: x['imdb_rating'], reverse=True)[:10]
        for idx, m in enumerate(top_movies, 1):
            platforms_str = ', '.join(m['platforms'][:2]) if m['platforms'] else 'Brak info'
            print(f"  {idx}. {m['title']} ({m.get('year', '?')}) - ⭐ {m['imdb_rating']}/10 - {platforms_str}")
        
        print("\n" + "=" * 70)
        print("✅ Gotowe!")
        print("=" * 70)
    
    except Exception as e:
        print(f"\n❌ Błąd krytyczny: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == '__main__':
    main()
