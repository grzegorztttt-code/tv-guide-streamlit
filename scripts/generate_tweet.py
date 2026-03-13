#!/usr/bin/env python3
import json
import os
from datetime import datetime, time

def load_epg_data():
    with open('data/movies.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def get_evening_movies(data):
    today = datetime.now().date()
    evening_start = time(20, 0)
    evening_end = time(23, 0)
    
    evening_movies = []
    
    for movie in data['movies']:
        start_dt = datetime.fromisoformat(movie['start_time'])
        
        if start_dt.date() != today:
            continue
        
        start_time = start_dt.time()
        
        if evening_start <= start_time <= evening_end:
            tmdb = movie.get('tmdb', {})
            rating = tmdb.get('rating', 0)
            
            if rating >= 6.5:
                evening_movies.append({
                    'title': tmdb.get('title', movie['title']),
                    'channel': movie['channel_name'],
                    'time': start_dt.strftime('%H:%M'),
                    'rating': rating,
                    'overview': tmdb.get('overview', '')
                })
    
    evening_movies.sort(key=lambda x: x['rating'], reverse=True)
    return evening_movies[:3]

def create_tweet_text(movies):
    if not movies:
        return "📺 Brak ciekawych filmów dziś wieczorem. Sprawdź program na kolejne dni!"
    
    date_str = datetime.now().strftime('%d.%m.%Y')
    tweet = f"📺 Wieczorny program TV ({date_str}):\n\n"
    
    for movie in movies:
        rating_emoji = "🟢" if movie['rating'] >= 7.5 else "🟡"
        
        tweet += f"🎬 {movie['title']}\n"
        tweet += f"{rating_emoji} {movie['rating']}/10 | {movie['channel']}, {movie['time']}\n"
        
        overview = movie['overview'][:80]
        if len(movie['overview']) > 80:
            overview += "..."
        tweet += f"{overview}\n\n"
    
    tweet += "#FilmyWieczorem #ProgramTV #FilmyNaDzis"
    
    return tweet

def save_tweet_file(text):
    os.makedirs('data', exist_ok=True)
    
    filename = f"data/tweet_{datetime.now().strftime('%Y-%m-%d')}.txt"
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(text)
    
    print(f"\nZapisano do: {filename}")
    return filename

def main():
    print("=" * 60)
    print("Generator Tweeta - Wieczorny Program TV")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    try:
        print("\n1. Ladowanie danych EPG...")
        data = load_epg_data()
        
        print("2. Wyszukiwanie wieczornych filmow (20:00-23:00)...")
        movies = get_evening_movies(data)
        print(f"   Znaleziono {len(movies)} filmow")
        
        print("\n3. Tworzenie tweeta...")
        tweet_text = create_tweet_text(movies)
        
        print("\n" + "=" * 60)
        print("TWEET:")
        print("=" * 60)
        print(tweet_text)
        print("=" * 60)
        
        print(f"\nDlugosc: {len(tweet_text)} znakow")
        
        print("\n4. Zapisywanie do pliku...")
        filename = save_tweet_file(tweet_text)
        
        print("\n✅ Gotowe!")
        print(f"\nSkopiuj tresc z pliku: {filename}")
        print("I wklej na X (Twitter)!")
        
    except Exception as e:
        print(f"❌ Blad: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
