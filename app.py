import streamlit as st
from datetime import datetime, timedelta
import sqlite3
import requests
import os
import pandas as pd

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
tab1, tab2, tab3, tab4 = st.tabs(["🎬 Program TV", "⭐ Ulubione", "➕ Dodaj Film", "🗑️ Zarządzanie"])

# === TAB 1: PROGRAM TV ===
with tab1:
    # Wybór trybu wyświetlania
    view_mode = st.radio(
        "Tryb wyświetlania:",
        ["📊 Po kanałach", "🎬 Grid (kafelki)", "📋 Tabela godzinowa"],
        horizontal=True
    )
    
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
            c.id as channel_id,
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
        ORDER BY c.name, p.start_time
    ''', (str(date_from), str(date_to), min_rating))
    
    results = cursor.fetchall()
    
    # Filtruj po kanałach
    if selected_channels:
        results = [r for r in results if r[4] in selected_channels]
    
    # Filtruj po gatunkach
    if genres:
        results = [r for r in results if any(g in str(r[10]) for g in genres)]
    
    st.write(f"**Znaleziono {len(results)} filmów**")
    
    if len(results) == 0:
        st.info("Brak filmów spełniających kryteria. Dodaj testowe dane w zakładce ➕")
    
    else:
        # === TRYB 1: PO KANAŁACH ===
        if view_mode == "📊 Po kanałach":
            # Grupuj po kanałach
            channels_dict = {}
            for row in results:
                channel_name = row[4]
                if channel_name not in channels_dict:
                    channels_dict[channel_name] = []
                channels_dict[channel_name].append(row)
            
            # Wyświetl każdy kanał
            for channel_name, movies in channels_dict.items():
                with st.expander(f"📺 **{channel_name}** ({len(movies)} filmów)", expanded=True):
                    for row in movies:
                        col1, col2, col3 = st.columns([1, 4, 1])
                        
                        with col1:
                            # Godzina
                            start_time = row[1]
                            if isinstance(start_time, str):
                                try:
                                    dt = datetime.fromisoformat(start_time)
                                    time_str = dt.strftime("%H:%M")
                                    date_str = dt.strftime("%d.%m")
                                except:
                                    time_str = start_time
                                    date_str = ""
                            st.markdown(f"### {time_str}")
                            if date_str:
                                st.caption(date_str)
                        
                        with col2:
                            # Tytuł + info
                            rating = row[9] if row[9] else 0
                            rating_color = "🟢" if rating >= 7.5 else "🟡" if rating >= 6.0 else "🔴"
                            
                            st.markdown(f"**{row[6]}** ({row[7]}) {rating_color} **{rating}/10**")
                            
                            if row[10]:  # genres
                                genres_short = row[10][:60] + "..." if len(row[10]) > 60 else row[10]
                                st.caption(f"🎭 {genres_short}")
                            
                            if row[3]:  # is_premiere
                                st.markdown("🔥 **PREMIERA**")
                        
                        with col3:
                            # Akcje
                            if st.button("📖", key=f"det_{row[0]}", help="Szczegóły"):
                                st.session_state.selected_movie = row[12]
                                st.rerun()
                        
                        st.divider()
        
        # === TRYB 2: GRID ===
        elif view_mode == "🎬 Grid (kafelki)":
            cols = st.columns(4)
            
            for idx, row in enumerate(results):
                col = cols[idx % 4]
                
                with col:
                    with st.container():
                        # Poster
                        if row[8]:
                            st.image(row[8], use_container_width=True)
                        else:
                            st.image("https://via.placeholder.com/300x450?text=Brak+plakatu", use_container_width=True)
                        
                        # Tytuł + ocena
                        rating = row[9] if row[9] else 0
                        rating_color = "🟢" if rating >= 7.5 else "🟡" if rating >= 6.0 else "🔴"
                        st.markdown(f"**{row[6]}** ({row[7]})")
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
                        
                        if row[3]:
                            st.markdown("🔥 **PREMIERA**")
                        
                        # Przycisk szczegółów
                        if st.button("Szczegóły", key=f"details_{row[0]}"):
                            st.session_state.selected_movie = row[12]
                            st.rerun()
        
        # === TRYB 3: TABELA GODZINOWA ===
        elif view_mode == "📋 Tabela godzinowa":
            # Przygotuj dane dla tabeli
            table_data = []
            for row in results:
                start_time = row[1]
                if isinstance(start_time, str):
                    try:
                        dt = datetime.fromisoformat(start_time)
                        time_str = dt.strftime("%H:%M")
                        date_str = dt.strftime("%d.%m")
                    except:
                        time_str = start_time
                        date_str = ""
                
                rating = row[9] if row[9] else 0
                rating_emoji = "🟢" if rating >= 7.5 else "🟡" if rating >= 6.0 else "🔴"
                
                table_data.append({
                    'Data': date_str,
                    'Godzina': time_str,
                    'Kanał': row[4],
                    'Film': f"{row[6]} ({row[7]})",
                    'Ocena': f"{rating_emoji} {rating}",
                    'tmdb_id': row[12],
                    'prog_id': row[0]
                })
            
            if table_data:
                df = pd.DataFrame(table_data)
                
                # Grupuj po dacie
                for date in df['Data'].unique():
                    st.markdown(f"### 📅 {date}")
                    
                    date_df = df[df['Data'] == date].drop('Data', axis=1)
                    
                    # Pivot table
                    try:
                        pivot = date_df.pivot_table(
                            index='Godzina',
                            columns='Kanał',
                            values='Film',
                            aggfunc='first',
                            fill_value='-'
                        )
                        
                        st.dataframe(pivot, use_container_width=True)
                    except:
                        # Jeśli pivot nie działa, pokaż zwykłą tabelę
                        st.dataframe(
                            date_df[['Godzina', 'Kanał', 'Film', 'Ocena']], 
                            use_container_width=True,
                            hide_index=True
                        )
                    
                    st.divider()
    
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
                if row[4]:
                    st.image(row[4], use_container_width=True)
                st.markdown(f"**{row[2]}** ({row[3]})")
                st.markdown(f"⭐ {row[8]}/10")
    
    conn.close()

# === TAB 3: DODAJ FILM ===
with tab3:
    st.subheader("Dodaj film do programu")
    
    if not TMDB_API_KEY:
        st.error("⚠️ Brak TMDB API Key!")
        st.markdown("""
**Ustaw TMDB_API_KEY w Streamlit Secrets:**

1. Settings → Secrets
2. Dodaj: `TMDB_API_KEY = "twoj_klucz"`

**Jak zdobyć klucz:**
1. https://www.themoviedb.org/signup
2. Settings → API → Request API Key
3. Developer
4. Application URL: http://localhost:8501
        """)
    else:
        col1, col2 = st.columns(2)
        
        with col1:
            movie_title = st.text_input("Tytuł filmu", "Dune")
            movie_year = st.number_input("Rok", 2000, 2026, 2021, step=1)
        
        with col2:
            channel_id = st.selectbox(
                "Kanał", 
                options=[ch['id'] for ch in CHANNELS], 
                format_func=lambda x: next(ch['name'] for ch in CHANNELS if ch['id'] == x)
            )
            start_datetime = st.datetime_input(
                "Data i godzina emisji", 
                value=datetime.now() + timedelta(hours=2)
            )
        
        if st.button("🔍 Znajdź w TMDB i dodaj"):
            with st.spinner("Szukam filmu..."):
                # Szukaj w TMDB
                tmdb_movie = search_movie(movie_title, movie_year)
                
                if tmdb_movie:
                    # Pobierz pełne detale
                    details = get_movie_details(tmdb_movie['id'])
                    
                    if details:
                        # Zapisz do bazy
                        conn = get_connection()
                        save_movie_to_db(details, conn)
                        
                        # Dodaj do programu TV
                        cursor = conn.cursor()
                        cursor.execute('SELECT id FROM movies WHERE tmdb_id = ?', (tmdb_movie['id'],))
                        movie_id = cursor.fetchone()[0]
                        
                        runtime = details.get('runtime', 120)
                        end_time = start_datetime + timedelta(minutes=runtime)
                        
                        # Sprawdź duplikaty
                        cursor.execute('''
                            SELECT id FROM tv_programs 
                            WHERE movie_id = ? AND channel_id = ? AND start_time = ?
                        ''', (movie_id, channel_id, start_datetime.isoformat()))
                        
                        if cursor.fetchone():
                            st.warning(f"⚠️ **{details['title']}** już jest w programie o tej godzinie na tym kanale!")
                        else:
                            cursor.execute('''
                                INSERT INTO tv_programs (channel_id, movie_id, start_time, end_time)
                                VALUES (?, ?, ?, ?)
                            ''', (
                                channel_id,
                                movie_id,
                                start_datetime.isoformat(),
                                end_time.isoformat()
                            ))
                            
                            conn.commit()
                            st.success(f"✅ Dodano: {details['title']}")
                            st.rerun()
                        
                        conn.close()
                    else:
                        st.error("Nie udało się pobrać szczegółów filmu")
                else:
                    st.error("Nie znaleziono filmu w TMDB")

# === TAB 4: ZARZĄDZANIE ===
with tab4:
    st.subheader("🗑️ Zarządzanie bazą danych")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Statystyki
    st.markdown("### 📊 Statystyki")
    col1, col2, col3 = st.columns(3)
    
    cursor.execute('SELECT COUNT(*) FROM movies')
    movies_count = cursor.fetchone()[0]
    col1.metric("Filmy w bazie", movies_count)
    
    cursor.execute('SELECT COUNT(*) FROM tv_programs')
    programs_count = cursor.fetchone()[0]
    col2.metric("Emisje w programie", programs_count)
    
    cursor.execute('SELECT COUNT(*) FROM favorites')
    favorites_count = cursor.fetchone()[0]
    col3.metric("Ulubione", favorites_count)
    
    st.divider()
    
    # Duplikaty
    st.markdown("### 🔍 Duplikaty w programie")
    cursor.execute('''
        SELECT 
            m.title,
            c.name,
            p.start_time,
            COUNT(*) as ile_razy
        FROM tv_programs p
        JOIN movies m ON p.movie_id = m.id
        JOIN channels c ON p.channel_id = c.id
        GROUP BY p.movie_id, p.channel_id, p.start_time
        HAVING COUNT(*) > 1
    ''')
    
    duplicates = cursor.fetchall()
    
    if duplicates:
        st.warning(f"Znaleziono {len(duplicates)} duplikatów:")
        for dup in duplicates:
            st.write(f"- **{dup[0]}** na {dup[1]} o {dup[2]} ({dup[3]}x)")
        
        if st.button("🗑️ Usuń wszystkie duplikaty"):
            cursor.execute('''
                DELETE FROM tv_programs
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM tv_programs
                    GROUP BY movie_id, channel_id, start_time
                )
            ''')
            conn.commit()
            st.success("✅ Duplikaty usunięte!")
            st.rerun()
    else:
        st.success("✅ Brak duplikatów")
    
    st.divider()
    
    # Resetuj bazę
    st.markdown("### ⚠️ Resetuj bazę danych")
    st.warning("To usunie WSZYSTKIE filmy, program TV i ulubione!")
    
    if st.button("🗑️ RESETUJ BAZĘ (nieodwracalne!)"):
        cursor.execute('DELETE FROM tv_programs')
        cursor.execute('DELETE FROM favorites')
        cursor.execute('DELETE FROM movies')
        conn.commit()
        st.success("✅ Baza wyczyszczona!")
        st.rerun()
        st.divider()
    
    # Dodaj nowy kanał
    st.markdown("### ➕ Dodaj nowy kanał")
    
    col1, col2 = st.columns(2)
    with col1:
        new_channel_name = st.text_input("Nazwa kanału", "")
    with col2:
        new_channel_category = st.selectbox(
            "Kategoria",
            ["Ogólne", "Publiczne", "Filmowe", "Rozrywka", "Edukacja", "Premium", "Streaming"]
        )
    
    if st.button("➕ Dodaj kanał"):
        if new_channel_name:
            cursor.execute('SELECT MAX(id) FROM channels')
            max_id = cursor.fetchone()[0]
            new_id = (max_id or 0) + 1
            
            cursor.execute(
                'INSERT INTO channels (id, name, category) VALUES (?, ?, ?)',
                (new_id, new_channel_name, new_channel_category)
            )
            conn.commit()
            st.success(f"✅ Dodano kanał: {new_channel_name}")
            st.rerun()
        else:
            st.error("Podaj nazwę kanału!")
    
    # Lista kanałów
    st.markdown("### 📺 Wszystkie kanały")
    cursor.execute('SELECT id, name, category FROM channels ORDER BY id')
    all_channels = cursor.fetchall()
    
    for ch in all_channels:
        st.write(f"{ch[0]}. **{ch[1]}** ({ch[2]})")
    conn.close()

# === MODAL SZCZEGÓŁÓW (sidebar) ===
if st.session_state.selected_movie:
    with st.sidebar:
        st.markdown("---")
        st.subheader("📽️ Szczegóły filmu")
        
        details = get_movie_details(st.session_state.selected_movie)
        
        if details:
            if details.get('poster_path'):
                st.image(f"{TMDB_IMAGE_BASE}{details['poster_path']}")
            
            st.markdown(f"### {details['title']}")
            st.markdown(f"⭐ **{details.get('vote_average', 'N/A')}/10**")
            st.markdown(f"📅 {details.get('release_date', 'N/A')}")
            st.markdown(f"⏱️ {details.get('runtime', 'N/A')} min")
            
            st.markdown("**Opis:**")
            st.write(details.get('overview', 'Brak opisu'))
            
            # Gatunki
            genres_list = [g['name'] for g in details.get('genres', [])]
            if genres_list:
                st.markdown(f"**Gatunki:** {', '.join(genres_list)}")
            
            # Trailer
            videos = details.get('videos', {}).get('results', [])
            trailers = [v for v in videos if v['type'] == 'Trailer' and v['site'] == 'YouTube']
            if trailers:
                st.markdown("**Trailer:**")
                st.video(f"https://www.youtube.com/watch?v={trailers[0]['key']}")
            
            # Ulubione
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM movies WHERE tmdb_id = ?', (st.session_state.selected_movie,))
            movie_row = cursor.fetchone()
            
            if movie_row:
                movie_id = movie_row[0]
                cursor.execute('SELECT id FROM favorites WHERE movie_id = ?', (movie_id,))
                is_favorite = cursor.fetchone() is not None
                
                if is_favorite:
                    if st.button("💔 Usuń z ulubionych"):
                        cursor.execute('DELETE FROM favorites WHERE movie_id = ?', (movie_id,))
                        conn.commit()
                        st.rerun()
                else:
                    if st.button("❤️ Dodaj do ulubionych"):
                        cursor.execute('INSERT INTO favorites (movie_id) VALUES (?)', (movie_id,))
                        conn.commit()
                        st.rerun()
            
            conn.close()
            
            if st.button("✖️ Zamknij"):
                st.session_state.selected_movie = None
                st.rerun()

