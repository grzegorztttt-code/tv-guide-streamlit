import streamlit as st
import json
import os
from datetime import datetime, timedelta, time
import pandas as pd

st.set_page_config(
    page_title="📺 Smart TV Guide",
    page_icon="📺",
    layout="wide"
)

@st.cache_data(ttl=3600)
def load_data():
    data_file = 'data/movies.json'
    if not os.path.exists(data_file):
        return None
    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

data = load_data()

st.title("📺 Smart TV Guide")

if not data:
    st.error("❌ Brak danych EPG! Czekam na pierwszą aktualizację...")
    st.info("💡 Dane są aktualizowane automatycznie co 6 godzin przez GitHub Actions")
    st.stop()

if 'selected_movie' not in st.session_state:
    st.session_state.selected_movie = None

col1, col2, col3 = st.columns(3)
with col1:
    updated = datetime.fromisoformat(data['updated_at'])
    st.metric("Ostatnia aktualizacja", updated.strftime("%d.%m %H:%M"))
with col2:
    st.metric("Filmów w bazie", data['count'])
with col3:
    next_update = updated + timedelta(hours=6)
    hours_left = (next_update - datetime.now()).total_seconds() / 3600
    st.metric("Następna za", f"{hours_left:.1f}h")

st.markdown("---")

st.sidebar.title("🔍 Filtry")

all_channels = sorted(set(m['channel_name'] for m in data['movies']))

selected_channels = st.sidebar.multiselect(
    "Kanały:",
    options=all_channels,
    default=all_channels[:10] if len(all_channels) > 10 else all_channels
)

movies = data['movies']
if movies:
    dates = [datetime.fromisoformat(m['start_time']) for m in movies]
    min_date = min(dates).date()
    max_date = max(dates).date()
    
    date_from = st.sidebar.date_input("Data od:", value=datetime.now().date(), min_value=min_date, max_value=max_date)
    date_to = st.sidebar.date_input("Data do:", value=datetime.now().date() + timedelta(days=3), min_value=min_date, max_value=max_date)
else:
    date_from = datetime.now().date()
    date_to = date_from + timedelta(days=3)

st.sidebar.markdown("### ⏰ Godziny emisji")
time_from = st.sidebar.time_input("Od godziny:", value=time(18, 0))
time_to = st.sidebar.time_input("Do godziny:", value=time(23, 59))

min_rating = st.sidebar.slider("Min. ocena IMDb:", 0.0, 10.0, 6.0, 0.5)

sort_option = st.sidebar.selectbox(
    "Sortuj po:",
    ["⏰ Czas emisji", "⭐ Ocena IMDb", "🎬 Tytuł"]
)

filtered = data['movies']

if selected_channels:
    filtered = [m for m in filtered if m['channel_name'] in selected_channels]

filtered = [
    m for m in filtered 
    if date_from <= datetime.fromisoformat(m['start_time']).date() <= date_to
]

filtered = [
    m for m in filtered
    if time_from <= datetime.fromisoformat(m['start_time']).time() <= time_to
]

filtered = [
    m for m in filtered
    if m.get('tmdb', {}).get('rating', 0) >= min_rating
]

if sort_option == "⏰ Czas emisji":
    filtered.sort(key=lambda x: x['start_time'])
elif sort_option == "⭐ Ocena IMDb":
    filtered.sort(key=lambda x: x.get('tmdb', {}).get('rating', 0), reverse=True)
else:
    filtered.sort(key=lambda x: x.get('tmdb', {}).get('title', x['title']))

st.write(f"**Znaleziono {len(filtered)} filmów**")

if len(filtered) == 0:
    st.info("Brak filmów spełniających kryteria. Zmień filtry.")
else:
    view_mode = st.radio(
        "Tryb:",
        ["📊 Po kanałach", "🎬 Lista z posterami", "📋 Tabela"],
        horizontal=True
    )
    
    if view_mode == "📊 Po kanałach":
        channels_dict = {}
        for movie in filtered:
            ch = movie['channel_name']
            if ch not in channels_dict:
                channels_dict[ch] = []
            channels_dict[ch].append(movie)
        
        for channel, channel_movies in channels_dict.items():
            with st.expander(f"📺 {channel} ({len(channel_movies)} filmów)", expanded=len(channels_dict) <= 3):
                for m in channel_movies:
                    tmdb = m.get('tmdb', {})
                    dt = datetime.fromisoformat(m['start_time'])
                    
                    movie_id = f"{m['channel_id']}_{m['start_time']}"
                    
                    col1, col2, col3, col4 = st.columns([1, 1, 3, 1])
                    
                    with col1:
                        st.markdown(f"### {dt.strftime('%H:%M')}")
                        st.caption(dt.strftime('%d.%m'))
                    
                    with col2:
                        if tmdb.get('poster'):
                            st.image(tmdb['poster'], width=100)
                        else:
                            st.markdown("🎬")
                    
                    with col3:
                        title = tmdb.get('title', m['title'])
                        year = tmdb.get('year', m.get('year', ''))
                        rating = tmdb.get('rating', 0)
                        
                        rating_color = "🟢" if rating >= 7.5 else "🟡" if rating >= 6.0 else "🔴"
                        
                        st.markdown(f"**{title}** ({year}) {rating_color} **{rating}/10**")
                        
                        if tmdb.get('overview'):
                            overview = tmdb['overview']
                            st.caption(overview[:100] + "..." if len(overview) > 100 else overview)
                    
                    with col4:
                        if st.button("📖 Więcej", key=movie_id):
                            st.session_state.selected_movie = m
                            st.rerun()
                    
                    st.divider()
    
    elif view_mode == "🎬 Lista z posterami":
        for m in filtered:
            tmdb = m.get('tmdb', {})
            dt = datetime.fromisoformat(m['start_time'])
            
            movie_id = f"{m['channel_id']}_{m['start_time']}_list"
            
            col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 3, 1])
            
            with col1:
                st.markdown(f"**{dt.strftime('%d.%m %H:%M')}**")
            
            with col2:
                if tmdb.get('poster'):
                    st.image(tmdb['poster'], width=80)
            
            with col3:
                st.markdown(f"📺 {m['channel_name']}")
            
            with col4:
                title = tmdb.get('title', m['title'])
                rating = tmdb.get('rating', 0)
                rating_color = "🟢" if rating >= 7.5 else "🟡" if rating >= 6.0 else "🔴"
                
                st.markdown(f"**{title}** {rating_color} {rating}/10")
                
                if tmdb.get('overview'):
                    st.caption(tmdb['overview'][:80] + "...")
            
            with col5:
                if st.button("📖", key=movie_id):
                    st.session_state.selected_movie = m
                    st.rerun()
            
            st.divider()
    
    else:
        table_data = []
        for m in filtered:
            dt = datetime.fromisoformat(m['start_time'])
            tmdb = m.get('tmdb', {})
            title = tmdb.get('title', m['title'])
            rating = tmdb.get('rating', 0)
            rating_emoji = "🟢" if rating >= 7.5 else "🟡" if rating >= 6.0 else "🔴"
            
            table_data.append({
                'Data i czas': dt.strftime('%d.%m %H:%M'),
                'Kanał': m['channel_name'],
                'Film': title,
                'Ocena': f"{rating_emoji} {rating}"
            })
        
        df = pd.DataFrame(table_data)
        st.dataframe(df, use_column_width=True, hide_index=True)

if st.session_state.selected_movie:
    m = st.session_state.selected_movie
    tmdb = m.get('tmdb', {})
    dt = datetime.fromisoformat(m['start_time'])
    dt_end = datetime.fromisoformat(m['end_time'])
    
    with st.sidebar:
        st.markdown("---")
        st.markdown("## 🎬 Szczegóły filmu")
        
        if tmdb.get('poster'):
            st.image(tmdb['poster'], use_column_width=True)
        
        title = tmdb.get('title', m['title'])
        year = tmdb.get('year', m.get('year', ''))
        rating = tmdb.get('rating', 0)
        
        st.markdown(f"### {title}")
        
        if year:
            st.markdown(f"📅 **Rok:** {year}")
        
        rating_color = "🟢" if rating >= 7.5 else "🟡" if rating >= 6.0 else "🔴"
        st.markdown(f"{rating_color} **Ocena IMDb:** {rating}/10")
        
        st.markdown("---")
        st.markdown("### 📺 Emisja")
        st.markdown(f"**Kanał:** {m['channel_name']}")
        st.markdown(f"**Start:** {dt.strftime('%d.%m.%Y %H:%M')}")
        st.markdown(f"**Koniec:** {dt_end.strftime('%H:%M')}")
        
        duration = (dt_end - dt).total_seconds() / 60
        st.markdown(f"**Czas trwania:** {int(duration)} min")
        
        if tmdb.get('overview'):
            st.markdown("---")
            st.markdown("### 📖 Opis")
            st.write(tmdb['overview'])
        
        if tmdb.get('tmdb_id'):
            st.markdown("---")
            tmdb_url = f"https://www.themoviedb.org/movie/{tmdb['tmdb_id']}"
            st.markdown(f"[🔗 Zobacz na TMDB]({tmdb_url})")
        
        if st.button("✖️ Zamknij", use_container_width=True):
            st.session_state.selected_movie = None
            st.rerun()
