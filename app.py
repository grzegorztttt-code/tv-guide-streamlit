import streamlit as st
from datetime import datetime, timedelta
import sqlite3
import requests
import os
import pandas as pd
from bs4 import BeautifulSoup
import time

# === CONFIG ===
try:
    TMDB_API_KEY = st.secrets["TMDB_API_KEY"]
except:
    TMDB_API_KEY = os.getenv('TMDB_API_KEY', '')

TMDB_BASE_URL = 'https://api.themoviedb.org/3'
TMDB_IMAGE_BASE = 'https://image.tmdb.org/t/p/w500'

# Lista kanałów dostępnych do scrapowania
AVAILABLE_CHANNELS = [
    {'id': 'tvn', 'name': 'TVN', 'teleman_id': 'tvn'},
    {'id': 'polsat', 'name': 'Polsat', 'teleman_id': 'polsat'},
    {'id': 'tvp1', 'name': 'TVP1', 'teleman_id': 'tvp1'},
    {'id': 'tvp2', 'name': 'TVP2', 'teleman_id': 'tvp2'},
    {'id': 'hbo', 'name': 'HBO', 'teleman_id': 'hbo'},
    {'id': 'hbo2', 'name': 'HBO2', 'teleman_id': 'hbo2'},
    {'id': 'hbo3', 'name': 'HBO3', 'teleman_id': 'hbo3'},
    {'id': 'cinemax', 'name': 'Cinemax', 'teleman_id': 'cinemax'},
    {'id': 'cinemax2', 'name': 'Cinemax2', 'teleman_id': 'cinemax2'},
    {'id': 'axn', 'name': 'AXN', 'teleman_id': 'axn'},
    {'id': 'comedy-central', 'name': 'Comedy Central', 'teleman_id': 'comedy-central'},
    {'id': 'filmbox', 'name': 'Filmbox', 'teleman_id': 'filmbox'},
    {'id': 'canal-plus-premium', 'name': 'Canal+ Premium', 'teleman_id': 'canal-plus-premium'},
    {'id': 'canal-plus-film', 'name': 'Canal+ Film', 'teleman_id': 'canal-plus-film'},
]

# === DATABASE FUNCTIONS ===
def init_db():
    """Tworzy bazę danych"""
    if not os.path.exists('data'):
        os.makedirs('data')
    
    conn = sqlite3.connect('data/tv_guide.db')
    cursor = conn.cursor()
    
    # Movies
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tmdb_id INTEGER UNIQUE,
            title TEXT NOT NULL,
            original_title TEXT,
            year INTEGER,
            poster_url TEXT,
            description TEXT,
            runtime INTEGER,
            genres TEXT,
            imdb_rating REAL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # TV Programs (EPG)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tv_programs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT,
            channel_name TEXT,
            movie_id INTEGER,
            program_title TEXT,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            is_movie BOOLEAN DEFAULT 1,
            FOREIGN KEY (movie_id) REFERENCES movies(id)
        )
    ''')
    
    # Last update timestamp
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_programs_time ON tv_programs(start_time)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_programs_channel ON tv_programs(channel_id)')
    
    conn.commit()
    conn.close()

def get_connection():
    return sqlite3.connect('data/tv_guide.db', check_same_thread=False)

# === SCRAPING FUNCTIONS ===
def scrape_teleman_channel(channel_id, date_str):
    """
    Scrapuje program TV z teleman.pl
    date_str format: YYYY-MM-DD
    """
    url = f"https://www.teleman.pl/program-tv/{channel_id}/{date_str}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'lxml')
        programs = []
        
        # Znajdź wszystkie programy
        program_items = soup.find_all('div', class_='program-item')
        
        for item in program_items:
            try:
                time_elem = item.find('span', class_='time')
                title_elem = item.find('h3', class_='title') or item.find('a', class_='title')
                
                if time_elem and title_elem:
                    time_str = time_elem.text.strip()
                    title = title_elem.text.strip()
                    
                    # Parsuj czas
                    hour, minute = map(int, time_str.split(':'))
                    start_datetime = datetime.strptime(date_str, '%Y-%m-%d').replace(
                        hour=hour, minute=minute
                    )
                    
                    programs.append({
                        'title': title,
                        'start_time': start_datetime,
                        'channel_id': channel_id
                    })
            except:
                continue
        
        return programs
    
    except Exception as e:
        st.error(f"Błąd scrapowania {channel_id}: {e}")
        return []

def is_movie_title(title):
    """Sprawdza czy tytuł wygląda jak film"""
    non_movie_keywords = ['wiadomości', 'serial', 'program', 'talk-show', 'sport', 'news', 'pogoda']
    
    title_lower = title.lower()
    
    for keyword in non_movie_keywords:
        if keyword in title_lower:
            return False
    
    return True

# === TMDB FUNCTIONS ===
def search_movie_tmdb(title, year=None):
    """Szuka filmu w TMDB"""
    if not TMDB_API_KEY:
        return None
    
    # Oczyść tytuł
    clean_title = title.split('(')[0].strip()
    clean_title = clean_title.replace('Film:', '').strip()
    
    params = {
        'api_key': TMDB_API_KEY,
        'query': clean_title,
        'language': 'pl-PL'
    }
    if year:
        params['year'] = year
    
    try:
        response = requests.get(f'{TMDB_BASE_URL}/search/movie', params=params)
        results = response.json().get('results', [])
        return results[0] if results else None
    except:
        return None

def get_movie_details_tmdb(tmdb_id):
    """Pobiera szczegóły filmu z TMDB"""
    if not TMDB_API_KEY:
        return None
    
    params = {
        'api_key': TMDB_API_KEY,
        'language': 'pl-PL',
        'append_to_response': 'credits,videos'
    }
    
    try:
        response = requests.get(f'{TMDB_BASE_URL}/movie/{tmdb_id}', params=params)
        return response.json()
    except:
        return None

def save_movie_to_db(tmdb_data, conn):
    """Zapisuje film do bazy"""
    cursor = conn.cursor()
    
    genres = ','.join([g['name'] for g in tmdb_data.get('genres', [])])
    poster_url = f"{TMDB_IMAGE_BASE}{tmdb_data['poster_path']}" if tmdb_data.get('poster_path') else None
    
    cursor.execute('''
        INSERT OR IGNORE INTO movies 
        (tmdb_id, title, original_title, year, poster_url, description, runtime, genres, imdb_rating)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        tmdb_data['id'],
        tmdb_data.get('title'),
        tmdb_data.get('original_title'),
        tmdb_data.get('release_date', '')[:4] if tmdb_data.get('release_date') else None,
        poster_url,
        tmdb_data.get('overview'),
        tmdb_data.get('runtime'),
        genres,
        tmdb_data.get('vote_average')
    ))
    
    conn.commit()
    cursor.execute('SELECT id FROM movies WHERE tmdb_id = ?', (tmdb_data['id'],))
    return cursor.fetchone()[0]

# === MAIN IMPORT FUNCTION ===
def import_epg_for_channels(channel_ids, date_str, progress_bar=None):
    """Importuje EPG dla wybranych kanałów"""
    conn = get_connection()
    cursor = conn.cursor()
    
    total_programs = 0
    total_movies = 0
    
    for idx, channel_id in enumerate(channel_ids):
        if progress_bar:
            progress_bar.progress((idx + 1) / len(channel_ids), 
                                 text=f"Pobieranie: {channel_id}...")
        
        # Scrape EPG
        programs = scrape_teleman_channel(channel_id, date_str)
        
        channel_name = next((ch['name'] for ch in AVAILABLE_CHANNELS if ch['id'] == channel_id), channel_id)
        
        for program in programs:
            total_programs += 1
            
            # Sprawdź czy to film
            if is_movie_title(program['title']):
                # Szukaj w TMDB
                tmdb_movie = search_movie_tmdb(program['title'])
                
                movie_id = None
                if tmdb_movie:
                    details = get_movie_details_tmdb(tmdb_movie['id'])
                    if details:
                        movie_id = save_movie_to_db(details, conn)
                        total_movies += 1
                
                # Zapisz do programu TV
                cursor.execute('''
                    INSERT INTO tv_programs 
                    (channel_id, channel_name, movie_id, program_title, start_time, is_movie)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    channel_id,
                    channel_name,
                    movie_id,
                    program['title'],
                    program['start_time'].isoformat(),
                    1
                ))
        
        # Opóźnienie między requestami
        time.sleep(1)
    
    # Zapisz timestamp
    cursor.execute('''
        INSERT OR REPLACE INTO metadata (key, value, updated_at)
        VALUES ('last_update', ?, datetime('now'))
    ''', (date_str,))
    
    conn.commit()
    conn.close()
    
    return total_programs, total_movies

# === STREAMLIT APP ===
st.set_page_config(
    page_title="📺 Smart TV Guide - Prawdziwy EPG",
    page_icon="📺",
    layout="wide"
)

init_db()

st.title("📺 Smart TV Guide - Prawdziwy Program TV")

# === SIDEBAR ===
st.sidebar.title("🔍 Filtry i Ustawienia")

# Wybór kanałów
st.sidebar.markdown("### Kanały do wyświetlenia")
selected_channel_ids = st.sidebar.multiselect(
    "Wybierz kanały:",
    options=[ch['id'] for ch in AVAILABLE_CHANNELS],
    default=[ch['id'] for ch in AVAILABLE_CHANNELS[:5]],
    format_func=lambda x: next(ch['name'] for ch in AVAILABLE_CHANNELS if ch['id'] == x)
)

# Data
st.sidebar.markdown("### Zakres dat")
selected_date = st.sidebar.date_input(
    "Data programu:",
    value=datetime.now()
)

# Min. ocena
st.sidebar.markdown("### Filtrowanie")
min_rating = st.sidebar.slider(
    "Min. ocena IMDb:",
    0.0, 10.0, 7.0, 0.5
)

# Sortowanie
sort_option = st.sidebar.selectbox(
    "Sortuj po:",
    ["⏰ Czas emisji", "⭐ Ocena IMDb (malejąco)", "🎬 Tytuł (A-Z)"]
)

# === AKTUALIZACJA EPG ===
st.markdown("---")
col1, col2 = st.columns([3, 1])

with col1:
    st.markdown("### 🔄 Aktualizacja danych")
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value, updated_at FROM metadata WHERE key = 'last_update'")
    last_update = cursor.fetchone()
    conn.close()
    
    if last_update:
        st.info(f"Ostatnia aktualizacja: {last_update[1]} (data: {last_update[0]})")
    else:
        st.warning("Brak danych! Kliknij 'Pobierz program TV'")

with col2:
    st.markdown("###  ")
    if st.button("🔄 Pobierz program TV", type="primary"):
        if not selected_channel_ids:
            st.error("Wybierz przynajmniej jeden kanał!")
        else:
            with st.spinner("Pobieranie danych z internetu..."):
                progress = st.progress(0, text="Inicjalizacja...")
                
                date_str = selected_date.strftime('%Y-%m-%d')
                
                # Wyczyść stare dane
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM tv_programs WHERE DATE(start_time) = ?', (date_str,))
                conn.commit()
                conn.close()
                
                # Import
                total_prog, total_mov = import_epg_for_channels(
                    selected_channel_ids, 
                    date_str, 
                    progress
                )
                
                progress.progress(1.0, text="Gotowe!")
                st.success(f"✅ Pobrano {total_prog} programów, znaleziono {total_mov} filmów!")
                time.sleep(1)
                st.rerun()

st.markdown("---")

# === WYŚWIETLANIE PROGRAMU ===
view_mode = st.radio(
    "Tryb wyświetlania:",
    ["📊 Po kanałach", "🎬 Lista filmów", "📋 Tabela godzinowa"],
    horizontal=True
)

# Pobierz dane
conn = get_connection()
cursor = conn.cursor()

date_str = selected_date.strftime('%Y-%m-%d')

query = '''
    SELECT 
        p.id,
        p.channel_id,
        p.channel_name,
        p.program_title,
        p.start_time,
        m.title,
        m.year,
        m.poster_url,
        m.imdb_rating,
        m.genres,
        m.tmdb_id
    FROM tv_programs p
    LEFT JOIN movies m ON p.movie_id = m.id
    WHERE DATE(p.start_time) = ?
    AND p.is_movie = 1
'''

params = [date_str]

if selected_channel_ids:
    placeholders = ','.join(['?' for _ in selected_channel_ids])
    query += f" AND p.channel_id IN ({placeholders})"
    params.extend(selected_channel_ids)

# Sortowanie
if sort_option == "⏰ Czas emisji":
    query += " ORDER BY p.start_time"
elif sort_option == "⭐ Ocena IMDb (malejąco)":
    query += " ORDER BY m.imdb_rating DESC, p.start_time"
else:
    query += " ORDER BY m.title"

cursor.execute(query, params)
results = cursor.fetchall()

# Filtruj po ratingu
results = [r for r in results if (r[8] or 0) >= min_rating]

st.write(f"**Znaleziono {len(results)} filmów**")

if len(results) == 0:
    st.info("Brak filmów spełniających kryteria. Kliknij '🔄 Pobierz program TV' aby załadować dane.")
else:
    # === TRYB 1: PO KANAŁACH ===
    if view_mode == "📊 Po kanałach":
        channels_dict = {}
        for row in results:
            channel_name = row[2]
            if channel_name not in channels_dict:
                channels_dict[channel_name] = []
            channels_dict[channel_name].append(row)
        
        for channel_name, movies in channels_dict.items():
            with st.expander(f"📺 **{channel_name}** ({len(movies)} filmów)", expanded=True):
                for row in movies:
                    col1, col2, col3 = st.columns([1, 4, 1])
                    
                    with col1:
                        start_time = row[4]
                        if isinstance(start_time, str):
                            try:
                                dt = datetime.fromisoformat(start_time)
                                time_str = dt.strftime("%H:%M")
                            except:
                                time_str = start_time
                        st.markdown(f"### {time_str}")
                    
                    with col2:
                        title = row[5] or row[3]
                        year = f"({row[6]})" if row[6] else ""
                        rating = row[8] if row[8] else 0
                        rating_color = "🟢" if rating >= 7.5 else "🟡" if rating >= 6.0 else "🔴"
                        
                        st.markdown(f"**{title}** {year} {rating_color} **{rating}/10**")
                        
                        if row[9]:
                            st.caption(f"🎭 {row[9][:60]}")
                    
                    with col3:
                        if row[10]:
                            if st.button("📖", key=f"det_{row[0]}", help="Szczegóły"):
                                st.session_state.selected_movie = row[10]
                                st.rerun()
                    
                    st.divider()
    
    # === TRYB 2: LISTA ===
    elif view_mode == "🎬 Lista filmów":
        for row in results:
            col1, col2, col3, col4 = st.columns([1, 1, 3, 1])
            
            with col1:
                start_time = row[4]
                if isinstance(start_time, str):
                    dt = datetime.fromisoformat(start_time)
                    time_str = dt.strftime("%H:%M")
                st.markdown(f"**{time_str}**")
            
            with col2:
                st.markdown(f"📺 {row[2]}")
            
            with col3:
                title = row[5] or row[3]
                year = f"({row[6]})" if row[6] else ""
                rating = row[8] if row[8] else 0
                rating_color = "🟢" if rating >= 7.5 else "🟡" if rating >= 6.0 else "🔴"
                
                st.markdown(f"**{title}** {year} {rating_color} {rating}/10")
            
            with col4:
                if row[10]:
                    if st.button("📖", key=f"list_{row[0]}"):
                        st.session_state.selected_movie = row[10]
                        st.rerun()
            
            st.divider()
    
    # === TRYB 3: TABELA ===
    elif view_mode == "📋 Tabela godzinowa":
        table_data = []
        for row in results:
            start_time = row[4]
            if isinstance(start_time, str):
                dt = datetime.fromisoformat(start_time)
                time_str = dt.strftime("%H:%M")
            
            title = row[5] or row[3]
            rating = row[8] if row[8] else 0
            rating_emoji = "🟢" if rating >= 7.5 else "🟡" if rating >= 6.0 else "🔴"
            
            table_data.append({
                'Godzina': time_str,
                'Kanał': row[2],
                'Film': f"{title} ({row[6]})" if row[6] else title,
                'Ocena': f"{rating_emoji} {rating}"
            })
        
        df = pd.DataFrame(table_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

conn.close()

# === MODAL SZCZEGÓŁÓW ===
if 'selected_movie' in st.session_state and st.session_state.selected_movie:
    with st.sidebar:
        st.markdown("---")
        st.subheader("📽️ Szczegóły filmu")
        
        details = get_movie_details_tmdb(st.session_state.selected_movie)
        
        if details:
            if details.get('poster_path'):
                st.image(f"{TMDB_IMAGE_BASE}{details['poster_path']}")
            
            st.markdown(f"### {details['title']}")
            st.markdown(f"⭐ **{details.get('vote_average', 'N/A')}/10**")
            st.markdown(f"📅 {details.get('release_date', 'N/A')}")
            st.markdown(f"⏱️ {details.get('runtime', 'N/A')} min")
            
            st.markdown("**Opis:**")
            st.write(details.get('overview', 'Brak opisu'))
            
            genres_list = [g['name'] for g in details.get('genres', [])]
            if genres_list:
                st.markdown(f"**Gatunki:** {', '.join(genres_list)}")
            
            videos = details.get('videos', {}).get('results', [])
            trailers = [v for v in videos if v['type'] == 'Trailer' and v['site'] == 'YouTube']
            if trailers:
                st.markdown("**Trailer:**")
                st.video(f"https://www.youtube.com/watch?v={trailers[0]['key']}")
            
            if st.button("✖️ Zamknij"):
                st.session_state.selected_movie = None
                st.rerun()
