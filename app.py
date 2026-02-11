import streamlit as st
from datetime import datetime, timedelta
import sqlite3
import requests
import os
import pandas as pd
from bs4 import BeautifulSoup
import time
import xml.etree.ElementTree as ET

# === CONFIG ===
try:
    TMDB_API_KEY = st.secrets["TMDB_API_KEY"]
except:
    TMDB_API_KEY = os.getenv('TMDB_API_KEY', '')

TMDB_BASE_URL = 'https://api.themoviedb.org/3'
TMDB_IMAGE_BASE = 'https://image.tmdb.org/t/p/w500'

# EPG.ovh URLs
EPG_URLS = {
    'standard': 'https://epg.ovh/pl.xml',
    'extended': 'https://epg.ovh/plar.xml',
    'detailed': 'https://epg.ovh/pltv.xml'
}

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
            category TEXT,
            year INTEGER,
            FOREIGN KEY (movie_id) REFERENCES movies(id)
        )
    ''')
    
    # Channels
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS channels (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT
        )
    ''')
    
    # Metadata
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

# === EPG.OVH PARSER ===
def download_epg_xml(epg_type='detailed'):
    """Pobiera EPG XML z EPG.ovh"""
    url = EPG_URLS.get(epg_type, EPG_URLS['detailed'])
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.content
    except Exception as e:
        st.error(f"Błąd pobierania EPG: {e}")
        return None

def parse_epg_xml(xml_content):
    """Parsuje XML EPG do struktury danych"""
    try:
        root = ET.fromstring(xml_content)
        
        # Pobierz kanały
        channels = {}
        for channel in root.findall('.//channel'):
            channel_id = channel.get('id')
            display_name = channel.find('display-name')
            if display_name is not None:
                channels[channel_id] = display_name.text
        
        # Pobierz programy
        programs = []
        for programme in root.findall('.//programme'):
            channel_id = programme.get('channel')
            start = programme.get('start')
            stop = programme.get('stop')
            
            title_elem = programme.find('title')
            title = title_elem.text if title_elem is not None else 'Unknown'
            
            # Kategoria
            category_elem = programme.find('category')
            category = category_elem.text if category_elem is not None else None
            
            # Rok produkcji (jeśli dostępny)
            date_elem = programme.find('date')
            year = int(date_elem.text[:4]) if date_elem is not None and date_elem.text else None
            
            # Parsuj czas (format: 20240210180000 +0100)
            try:
                start_dt = datetime.strptime(start[:14], '%Y%m%d%H%M%S')
                stop_dt = datetime.strptime(stop[:14], '%Y%m%d%H%M%S')
            except:
                continue
            
            programs.append({
                'channel_id': channel_id,
                'channel_name': channels.get(channel_id, channel_id),
                'title': title,
                'start_time': start_dt,
                'end_time': stop_dt,
                'category': category,
                'year': year
            })
        
        return channels, programs
    
    except Exception as e:
        st.error(f"Błąd parsowania XML: {e}")
        return {}, []

def is_movie_program(title, category, year):
    """Sprawdza czy program to film"""
    if not title:
        return False
    
    title_lower = title.lower()
    
    # Wykluczenia
    non_movie = ['wiadomości', 'news', 'pogoda', 'sport', 'serial', 'telenovela', 
                 'show', 'program', 'koncert', 'magazyn', 'talk']
    
    for keyword in non_movie:
        if keyword in title_lower:
            return False
    
    # Jeśli ma kategorię "film" lub rok produkcji -> prawdopodobnie film
    if category and 'film' in category.lower():
        return True
    
    if year and year < datetime.now().year:
        return True
    
    return False

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
    result = cursor.fetchone()
    return result[0] if result else None

# === MAIN IMPORT FUNCTION ===
def import_epg_from_xml(progress_bar=None):
    """Importuje EPG z EPG.ovh"""
    
    # Pobierz XML
    if progress_bar:
        progress_bar.progress(0.1, text="Pobieranie EPG XML...")
    
    xml_content = download_epg_xml('detailed')
    if not xml_content:
        return 0, 0
    
    # Parsuj
    if progress_bar:
        progress_bar.progress(0.2, text="Parsowanie XML...")
    
    channels, programs = parse_epg_xml(xml_content)
    
    if not programs:
        return 0, 0
    
    # Zapisz kanały
    conn = get_connection()
    cursor = conn.cursor()
    
    for channel_id, channel_name in channels.items():
        cursor.execute('''
            INSERT OR REPLACE INTO channels (id, name, category)
            VALUES (?, ?, ?)
        ''', (channel_id, channel_name, 'TV'))
    
    conn.commit()
    
    # Filtruj tylko filmy
    movie_programs = [p for p in programs if is_movie_program(p['title'], p['category'], p['year'])]
    
    total_movies = 0
    total_programs = len(movie_programs)
    
    # Importuj programy
    for idx, program in enumerate(movie_programs):
        if progress_bar and idx % 10 == 0:
            progress = 0.2 + (0.7 * idx / total_programs)
            progress_bar.progress(progress, text=f"Przetwarzanie: {idx}/{total_programs}...")
        
        # Szukaj w TMDB
        tmdb_movie = search_movie_tmdb(program['title'], program['year'])
        
        movie_id = None
        if tmdb_movie:
            details = get_movie_details_tmdb(tmdb_movie['id'])
            if details:
                movie_id = save_movie_to_db(details, conn)
                total_movies += 1
        
        # Zapisz program
        cursor.execute('''
            INSERT INTO tv_programs 
            (channel_id, channel_name, movie_id, program_title, start_time, end_time, category, year)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            program['channel_id'],
            program['channel_name'],
            movie_id,
            program['title'],
            program['start_time'].isoformat(),
            program['end_time'].isoformat(),
            program['category'],
            program['year']
        ))
        
        # Co 50 programów - commit
        if idx % 50 == 0:
            conn.commit()
    
    # Zapisz timestamp
    cursor.execute('''
        INSERT OR REPLACE INTO metadata (key, value, updated_at)
        VALUES ('last_update', ?, datetime('now'))
    ''', (datetime.now().strftime('%Y-%m-%d'),))
    
    conn.commit()
    conn.close()
    
    return total_programs, total_movies

# === STREAMLIT APP ===
st.set_page_config(
    page_title="📺 Smart TV Guide - EPG",
    page_icon="📺",
    layout="wide"
)

init_db()

st.title("📺 Smart TV Guide - Program TV")

# === SIDEBAR ===
st.sidebar.title("🔍 Filtry")

# Pobierz listę kanałów z bazy
conn = get_connection()
cursor = conn.cursor()
cursor.execute('SELECT DISTINCT channel_id, channel_name FROM tv_programs ORDER BY channel_name')
available_channels = cursor.fetchall()
conn.close()

# Wybór kanałów
if available_channels:
    selected_channels = st.sidebar.multiselect(
        "Wybierz kanały:",
        options=[ch[0] for ch in available_channels],
        default=[ch[0] for ch in available_channels[:10]],
        format_func=lambda x: next((ch[1] for ch in available_channels if ch[0] == x), x)
    )
else:
    st.sidebar.warning("Brak kanałów. Pobierz EPG!")
    selected_channels = []

# Zakres dat
date_from = st.sidebar.date_input(
    "Data od:",
    value=datetime.now()
)
date_to = st.sidebar.date_input(
    "Data do:",
    value=datetime.now() + timedelta(days=3)
)

# Min. ocena
min_rating = st.sidebar.slider(
    "Min. ocena IMDb:",
    0.0, 10.0, 6.0, 0.5
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
        st.info(f"📡 Źródło: EPG.ovh | Ostatnia aktualizacja: {last_update[1]}")
    else:
        st.warning("Brak danych! Kliknij 'Pobierz EPG'")

with col2:
    st.markdown("###  ")
    if st.button("🔄 Pobierz EPG", type="primary"):
        with st.spinner("Pobieranie EPG z EPG.ovh..."):
            progress = st.progress(0, text="Łączenie z EPG.ovh...")
            
            # Wyczyść stare dane
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM tv_programs')
            conn.commit()
            conn.close()
            
            # Import
            total_prog, total_mov = import_epg_from_xml(progress)
            
            progress.progress(1.0, text="Gotowe!")
            st.success(f"✅ Zaimportowano {total_prog} filmów, {total_mov} dopasowano z TMDB!")
            time.sleep(2)
            st.rerun()

st.markdown("---")

# === WYŚWIETLANIE PROGRAMU ===
view_mode = st.radio(
    "Tryb wyświetlania:",
    ["📊 Po kanałach", "🎬 Lista filmów", "📋 Tabela"],
    horizontal=True
)

# Pobierz dane
conn = get_connection()
cursor = conn.cursor()

query = '''
    SELECT 
        p.id,
        p.channel_id,
        p.channel_name,
        p.program_title,
        p.start_time,
        p.end_time,
        m.title,
        m.year,
        m.poster_url,
        m.imdb_rating,
        m.genres,
        m.tmdb_id
    FROM tv_programs p
    LEFT JOIN movies m ON p.movie_id = m.id
    WHERE DATE(p.start_time) >= ?
    AND DATE(p.start_time) <= ?
'''

params = [str(date_from), str(date_to)]

if selected_channels:
    placeholders = ','.join(['?' for _ in selected_channels])
    query += f" AND p.channel_id IN ({placeholders})"
    params.extend(selected_channels)

# Sortowanie
if sort_option == "⏰ Czas emisji":
    query += " ORDER BY p.start_time"
elif sort_option == "⭐ Ocena IMDb (malejąco)":
    query += " ORDER BY m.imdb_rating DESC NULLS LAST, p.start_time"
else:
    query += " ORDER BY COALESCE(m.title, p.program_title)"

cursor.execute(query, params)
results = cursor.fetchall()

# Filtruj po ratingu
results = [r for r in results if (r[9] or 0) >= min_rating]

st.write(f"**Znaleziono {len(results)} filmów**")

if len(results) == 0:
    st.info("Brak filmów spełniających kryteria. Zmień filtry lub pobierz EPG.")
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
            with st.expander(f"📺 **{channel_name}** ({len(movies)} filmów)", expanded=len(channels_dict) <= 5):
                for row in movies:
                    col1, col2, col3 = st.columns([1, 4, 1])
                    
                    with col1:
                        start_time = row[4]
                        if isinstance(start_time, str):
                            dt = datetime.fromisoformat(start_time)
                            time_str = dt.strftime("%H:%M")
                            date_str = dt.strftime("%d.%m")
                        st.markdown(f"### {time_str}")
                        st.caption(date_str)
                    
                    with col2:
                        title = row[6] or row[3]
                        year = f"({row[7]})" if row[7] else ""
                        rating = row[9] if row[9] else 0
                        rating_color = "🟢" if rating >= 7.5 else "🟡" if rating >= 6.0 else "🔴"
                        
                        st.markdown(f"**{title}** {year} {rating_color} **{rating}/10**")
                        
                        if row[10]:
                            st.caption(f"🎭 {row[10][:60]}")
                    
                    with col3:
                        if row[11]:
                            if st.button("📖", key=f"det_{row[0]}", help="Szczegóły"):
                                st.session_state.selected_movie = row[11]
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
                    time_str = dt.strftime("%d.%m %H:%M")
                st.markdown(f"**{time_str}**")
            
            with col2:
                st.markdown(f"📺 {row[2]}")
            
            with col3:
                title = row[6] or row[3]
                year = f"({row[7]})" if row[7] else ""
                rating = row[9] if row[9] else 0
                rating_color = "🟢" if rating >= 7.5 else "🟡" if rating >= 6.0 else "🔴"
                
                st.markdown(f"**{title}** {year} {rating_color} {rating}/10")
            
            with col4:
                if row[11]:
                    if st.button("📖", key=f"list_{row[0]}"):
                        st.session_state.selected_movie = row[11]
                        st.rerun()
            
            st.divider()
    
    # === TRYB 3: TABELA ===
    elif view_mode == "📋 Tabela":
        table_data = []
        for row in results:
            start_time = row[4]
            if isinstance(start_time, str):
                dt = datetime.fromisoformat(start_time)
                datetime_str = dt.strftime("%d.%m %H:%M")
            
            title = row[6] or row[3]
            rating = row[9] if row[9] else 0
            rating_emoji = "🟢" if rating >= 7.5 else "🟡" if rating >= 6.0 else "🔴"
            
            table_data.append({
                'Data i czas': datetime_str,
                'Kanał': row[2],
                'Film': f"{title} ({row[7]})" if row[7] else title,
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
