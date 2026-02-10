import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from database.db import init_db, get_connection
from services.tmdb import search_movie, get_movie_details, save_movie_to_db
from config import CHANNELS
import os

# Konfiguracja strony
st.set_page_config(
    page_title="📺 Smart TV Guide",
    page_icon="📺",
    layout="wide"
)

# Inicjalizacja bazy
if not os.path.exists('data'):
    os.makedirs('data')
init_db()

# Session state
if 'selected_movie' not in st.session_state:
    st.session_state.selected_movie = None

# ===== SIDEBAR - FILTRY =====
st.sidebar.title("🔍 Filtry")

# Wybór kanałów
selected_channels = st.sidebar.multiselect(
    "Kanały",
    options=[ch['name'] for ch in CHANNELS],
    default=[ch['name'] for ch in CHANNELS[:3]]
)

# Zakres dat
date_from = st.sidebar.date_input(
    "Data od",
    value=datetime.now()
)
date_to = st.sidebar.date_input(
    "Data do",
    value=datetime.now() + timedelta(days=2)
)

# Ocena minimalna
min_rating = st.sidebar.slider(
    "Min. ocena IMDb",
    min_value=0.0,
    max_value=10.0,
    value=6.0,
    step=0.5
)

# Gatunki
genres = st.sidebar.multiselect(
    "Gatunki",
    options=['Akcja', 'Komedia', 'Dramat', 'Thriller', 'Sci-Fi', 'Horror', 'Romans'],
    default=[]
)

# Godzina emisji
time_from = st.sidebar.time_input("Godzina od", value=datetime.strptime("18:00", "%H:%M").time())
time_to = st.sidebar.time_input("Godzina do", value=datetime.strptime("23:59", "%H:%M").time())

# ===== MAIN AREA =====
st.title("📺 Smart TV Guide")

# Tabs
tab1, tab2, tab3 = st.tabs(["🎬 Program TV", "⭐ Ulubione", "➕ Dodaj Film Testowy"])

# ===== TAB 1: PROGRAM TV =====
with tab1:
    conn = get_connection()
    cursor = conn.cursor()
    
    # Query z filtrami
    query = '''
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
            m.tmdb_id
        FROM tv_programs p
        JOIN channels c ON p.channel_id = c.id
        JOIN movies m ON p.movie_id = m.id
        WHERE DATE(p.start_time) BETWEEN ? AND ?
        AND m.imdb_rating >= ?
        ORDER BY p.start_time
    '''
    
    df = pd.read_sql_query(
        query, 
        conn, 
        params=(date_from, date_to, min_rating)
    )
    
    # Dodatkowe filtry (w pamięci)
    if selected_channels:
        df = df[df['channel_name'].isin(selected_channels)]
    
    if genres:
        df = df[df['genres'].apply(lambda x: any(g in str(x) for g in genres))]
    
    # Wyświetlanie w gridzie
    if len(df) == 0:
        st.info("Brak filmów spełniających kryteria. Dodaj testowe dane w zakładce ➕")
    else:
        # Grid layout
        cols = st.columns(4)
        
        for idx, row in df.iterrows():
            col = cols[idx % 4]
            
            with col:
                with st.container():
                    # Poster
                    if row['poster_url']:
                        st.image(row['poster_url'], use_container_width=True)
                    else:
                        st.image("https://via.placeholder.com/300x450?text=Brak+plakatu", use_container_width=True)
                    
                    # Tytuł + ocena
                    rating_color = "🟢" if row['imdb_rating'] >= 7.5 else "🟡" if row['imdb_rating'] >= 6.0 else "🔴"
                    st.markdown(f"**{row['title']}** ({row['year']})")
                    st.markdown(f"{rating_color} **{row['imdb_rating']}/10**")
                    
                    # Info
                    start_time = pd.to_datetime(row['start_time']).strftime("%d.%m %H:%M")
                    st.caption(f"📺 {row['channel_name']} • {start_time}")
                    
                    if row['is_premiere']:
                        st.markdown("🔥 **PREMIERA**")
                    
                    # Przycisk szczegółów
                    if st.button("Szczegóły", key=f"details_{row['id']}"):
                        st.session_state.selected_movie = row['tmdb_id']
                        st.rerun()
    
    conn.close()

# ===== TAB 2: ULUBIONE =====
with tab2:
    conn = get_connection()
    
    query = '''
        SELECT m.*, f.added_at
        FROM favorites f
        JOIN movies m ON f.movie_id = m.id
        ORDER BY f.added_at DESC
    '''
    
    fav_df = pd.read_sql_query(query, conn)
    
    if len(fav_df) == 0:
        st.info("Nie masz jeszcze ulubionych filmów")
    else:
        cols = st.columns(4)
        for idx, row in fav_df.iterrows():
            col = cols[idx % 4]
            with col:
                if row['poster_url']:
                    st.image(row['poster_url'], use_container_width=True)
                st.markdown(f"**{row['title']}**")
                st.markdown(f"⭐ {row['imdb_rating']}/10")
    
    conn.close()

# ===== TAB 3: DODAJ TESTOWE DANE =====
with tab3:
    st.subheader("Dodaj film testowy")
    
    col1, col2 = st.columns(2)
    
    with col1:
        movie_title = st.text_input("Tytuł filmu", "Dune")
        movie_year = st.number_input("Rok", 2021, step=1)
    
    with col2:
        channel_id = st.selectbox("Kanał", options=[ch['id'] for ch in CHANNELS], format_func=lambda x: next(ch['name'] for ch in CHANNELS if ch['id'] == x))
        start_datetime = st.datetime_input("Data i godzina emisji", value=datetime.now() + timedelta(hours=2))
    
    if st.button("🔍 Znajdź w TMDB i dodaj"):
        with st.spinner("Szukam filmu..."):
            # Szukaj w TMDB
            tmdb_movie = search_movie(movie_title, movie_year)
            
            if tmdb_movie:
                # Pobierz pełne detale
                details = get_movie_details(tmdb_movie['id'])
                
                # Zapisz do bazy
                conn = get_connection()
                save_movie_to_db(details, conn)
                
                # Dodaj do programu TV
                cursor = conn.cursor()
                cursor.execute('SELECT id FROM movies WHERE tmdb_id = ?', (tmdb_movie['id'],))
                movie_id = cursor.fetchone()[0]
                
                cursor.execute('''
                    INSERT INTO tv_programs (channel_id, movie_id, start_time, end_time)
                    VALUES (?, ?, ?, ?)
                ''', (
                    channel_id,
                    movie_id,
                    start_datetime,
                    start_datetime + timedelta(minutes=details.get('runtime', 120))
                ))
                
                conn.commit()
                conn.close()
                
                st.success(f"✅ Dodano: {details['title']}")
                st.rerun()
            else:
                st.error("Nie znaleziono filmu w TMDB")

# ===== MODAL SZCZEGÓŁÓW (sidebar) =====
if st.session_state.selected_movie:
    with st.sidebar:
        st.markdown("---")
        st.subheader("📽️ Szczegóły filmu")
        
        details = get_movie_details(st.session_state.selected_movie)
        
        if details.get('poster_path'):
            st.image(f"https://image.tmdb.org/t/p/w500{details['poster_path']}")
        
        st.markdown(f"### {details['title']}")
        st.markdown(f"⭐ **{details.get('vote_average', 'N/A')}/10**")
        st.markdown(f"📅 {details.get('release_date', 'N/A')}")
        st.markdown(f"⏱️ {details.get('runtime', 'N/A')} min")
        
        st.markdown("**Opis:**")
        st.write(details.get('overview', 'Brak opisu'))
        
        # Gatunki
        genres_list = [g['name'] for g in details.get('genres', [])]
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
