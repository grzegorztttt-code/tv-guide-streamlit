import streamlit as st
from datetime import datetime, timedelta
import sqlite3
import requests
import os

# === CONFIG ===
try:
    TMDB_API_KEY = st.secrets["TMDB_API_KEY"]
except:
    TMDB_API_KEY = os.getenv('TMDB_API_KEY', '')

TMDB_BASE_URL = 'https://api.themoviedb.org/3'
TMDB_IMAGE_BASE = 'https://image.tmdb.org/t/p/w500'

CHANNELS = [
    {'id': 1, 'name': 'TVN', 'category': 'Ogólne'},
    {'id': 2, 'name': 'Polsat', 'category': 'Ogólne'},
    {'id': 3, 'name': 'TVP1', 'category': 'Publiczne'},
    {'id': 4, 'name': 'HBO', 'category': 'Filmowe'},
    {'id': 5, 'name': 'Ale Kino+', 'category': 'Filmowe'},
]

# === DATABASE FUNCTIONS ===
def init_db():
    """Tworzy bazę danych z tabelami"""
    if not os.path.exists('data'):
        os.makedirs('data')
    
    conn = sqlite3.connect('data/tv_guide.db')
    cursor = conn.cursor()
    
    # Channels
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT
        )
    ''')
    
    # Movies
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tmdb_id INTEGER UNIQUE,
            title TEXT NOT NULL,
            year INTEGER,
            poster_url TEXT,
            description TEXT,
            runtime INTEGER,
            genres TEXT,
            imdb_rating REAL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # TV Programs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tv_programs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER,
            movie_id INTEGER,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            is_premiere BOOLEAN DEFAULT 0,
            FOREIGN KEY (channel_id) REFERENCES channels(id),
            FOREIGN KEY (movie_id) REFERENCES movies(id)
        )
    ''')
    
    # Favorites
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            movie_id INTEGER,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (movie_id) REFERENCES movies(id)
        )
    ''')
    
    # Dodaj kanały jeśli puste
    cursor.execute('SELECT COUNT(*) FROM channels')
    if cursor.fetchone()[0] == 0:
        for ch in CHANNELS:
            cursor.execute('INSERT INTO channels (id, name, category) VALUES (?, ?, ?)',
                         (ch['id'], ch['name'], ch['category']))
    
    # Indexy
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_programs_time ON tv_programs(start_time)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_movies_tmdb ON movies(tmdb_id)')
    
    conn.commit()
    conn.close()

def get_connection():
    """Zwraca połączenie do bazy"""
    return sqlite3.connect('data/tv_guide.db', check_same_thread=False)

# === TMDB FUNCTIONS ===
def search_movie(title, year=None):
    """Szuka filmu w TMDB"""
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
        response = requests.get(f'{TMDB_BASE_URL}/search/movie', params=params)
        results = response.json().get('results', [])
        return results[0] if results else None
    except:
        return None

def get_movie_details(tmdb_id):
    """Pobiera szczegóły filmu"""
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
        (tmdb_id, title, year, poster_url, description, runtime, genres, imdb_rating)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        tmdb_data['id'],
        tmdb_data['title'],
        tmdb_data.get('release_date', '')[:4] if tmdb_data.get('release_date') else None,
        poster_url,
        tmdb_data.get('overview'),
        tmdb_data.get('runtime'),
        genres,
        tmdb_data.get('vote_average')
    ))
    
    conn.commit()
    return cursor.lastrowid

# === MAIN APP ===
st.set_page_config(
    page_title="📺 Smart TV Guide",
    page_icon="📺",
    layout="wide"
)

# Inicjalizacja bazy
init_db()

# Session state
if 'selected_movie' not in st.session_state:
    st.session_state.selected_movie = None

# === SIDEBAR - FILTRY ===
st.sidebar.title("🔍 Filtry")

# Wybór kanałów
selected_channels = st.sidebar.multiselect(
    "Kanały",
    options=[ch['name'] for ch in CHANNELS],
    default=[ch['name'] for ch in CHANNELS]
)

# Zakres dat
date_from = st.sidebar.date_input(
    "Data od",
    value=datetime.now() - timedelta(days=1)
)
date_to = st.sidebar.date_input(
    "Data do",
    value=datetime.now() + timedelta(days=7)
)

# Ocena minimalna
min_rating = st.sidebar.slider(
    "Min. ocena IMDb",
    min_value=0.0,
    max_value=10.0,
    value=0.0,
    step=0.5
)

# Gatunki
all_genres = ['Akcja', 'Komedia', 'Dramat', 'Thriller', 'Sci-Fi', 'Horror', 'Romans', 'Animacja']
genres = st.sidebar.multiselect(
    "Gatunki",
    options=all_genres,
    default=[]
)

# === MAIN AREA ===
st.title("📺 Smart TV Guide")

# Tabs
tab1, tab2, tab3 = st.tabs(["🎬 Program TV", "⭐ Ulubione", "➕ Dodaj Film Testowy"])

# === TAB 1: PROGRAM TV ===
with tab1:
    conn = get_connection()
    cursor = conn.cursor()
    
    # Query z filtrami
    cursor.execute('''
        SELECT 
            p.id,
            p.start_time,
            p.end_time,
            p.is_premiere,
            c.name as channel_name,
            m.title,
            m.year,
            m.poster_url,
            m.imdb_rating,
            m.genres,
            m.description,
            m.tmdb_id,
            m.id as movie_id
        FROM tv_programs p
        JOIN channels c ON p.channel_id = c.id
        JOIN movies m ON p.movie_id = m.id
        WHERE DATE(p.start_time) BETWEEN ? AND ?
        AND m.imdb_rating >= ?
        ORDER BY p.start_time
    ''', (str(date_from), str(date_to), min_rating))
    
    results = cursor.fetchall()
    
    # Filtruj po kanałach
    if selected_channels:
        results = [r for r in results if r[4] in selected_channels]
    
    # Filtruj po gatunkach
    if genres:
        results = [r for r in results if any(g in str(r[9]) for g in genres)]
    
    st.write(f"**Znaleziono {len(results)} filmów**")
    
    # Wyświetlanie w gridzie
    if len(results) == 0:
        st.info("Brak filmów spełniających kryteria. Dodaj testowe dane w zakładce ➕")
    else:
        # Grid layout
        cols = st.columns(4)
        
        for idx, row in enumerate(results):
            col = cols[idx % 4]
            
            with col:
                with st.container():
                    # Poster
                    if row[7]:  # poster_url
                        st.image(row[7], use_container_width=True)
                    else:
                        st.image("https://via.placeholder.com/300x450?text=Brak+plakatu", use_container_width=True)
                    
                    # Tytuł + ocena
                    rating = row[8] if row[8] else 0
                    rating_color = "🟢" if rating >= 7.5 else "🟡" if rating >= 6.0 else "🔴"
                    st.markdown(f"**{row[5]}** ({row[6]})")
                    st.markdown(f"{rating_color} **{rating}/10**")
                    
                    # Info
                    start_time = row[1]
                    if isinstance(start_time, str):
                        try:
                            dt = datetime.fromisoformat(start_time)
                            start_time = dt.strftime("%d.%m %H:%M")
                        except:
                            pass
                    st.caption(f"📺 {row[4]} • {start_time}")
                    
                    if row[3]:  # is_premiere
                        st.markdown("🔥 **PREMIERA**")
                    
                    # Przycisk szczegółów
                    if st.button("Szczegóły", key=f"details_{row[0]}"):
                        st.session_state.selected_movie = row[11]  # tmdb_id
                        st.rerun()
    
    conn.close()

# === TAB 2: ULUBIONE ===
with tab2:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT m.*, f.added_at
        FROM favorites f
        JOIN movies m ON f.movie_id = m.id
        ORDER BY f.added_at DESC
    ''')
    
    fav_results = cursor.fetchall()
    
    if len(fav_results) == 0:
        st.info("Nie masz jeszcze ulubionych filmów")
    else:
        cols = st.columns(4)
        for idx, row in enumerate(fav_results):
            col = cols[idx % 4]
            with col:
                if row[4]:  # poster_url
                    st.image(row[4], use_container_width=True)
                st.markdown(f"**{row[2]}** ({row[3]})")
                st.markdown(f"⭐ {row[8]}/10")
    
    conn.close()

# === TAB 3: DODAJ TESTOWE DANE ===
with tab3:
    st.subheader("Dodaj film testowy")
    
    if not TMDB_API_KEY:
        st.error("⚠️ Brak TMDB API Key!")
        st.info("""
        **Ustaw TMDB_API_KEY w Streamlit Secrets:**
        
        1. Settings → Secrets
        2. Dodaj:
