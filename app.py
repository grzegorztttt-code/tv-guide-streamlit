import streamlit as st
import json
import os
from datetime import datetime, timedelta, time
import pandas as pd

st.set_page_config(
    page_title="📺 Smart TV Guide",
    page_icon="📺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Stylizacja paska bocznego
st.markdown("""
<style>
    section[data-testid="stSidebar"] {
        width: 400px !important;
    }
    section[data-testid="stSidebar"] > div {
        padding-top: 2rem;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def load_data():
    # Upewnij się, że ścieżka do pliku jest poprawna
    data_file = 'data/movies.json'
    if not os.path.exists(data_file):
        return None
    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

data = load_data()

if 'selected_movie' not in st.session_state:
    st.session_state.selected_movie = None

with st.sidebar:
    st.title("🔍 Filtry")
    
    if data:
        all_channels = sorted(set(m['channel_name'] for m in data['movies']))
        
        # DEFINICJA KANAŁÓW PRIORYTETOWYCH
        # Dodajemy różne warianty zapisu, żeby na pewno je wyłapać
        target_priorities = ['TVP1', 'TVP 1', 'TVP1 HD', 'TVP2', 'TVP 2', 'TVP 2 HD', 'Ale Kino+', 'Ale kino']
        
        preferred_order = []
        # Najpierw dodaj te, które pasują do naszych priorytetów
        for priority in target_priorities:
            for real_channel in all_channels:
                if priority.lower() in real_channel.lower() and real_channel not in preferred_order:
                    preferred_order.append(real_channel)
        
        # Potem dodaj resztę znanych stacji
        other_popular = ['Polsat', 'TVN', 'TVN7', 'HBO', 'HBO2', 'HBO3', 'Cinemax', 'Canal+ Premium']
        for p in other_popular:
            for real_channel in all_channels:
                if p.lower() in real_channel.lower() and real_channel not in preferred_order:
                    preferred_order.append(real_channel)

        # Na końcu cała reszta, której nie ma powyżej
        sorted_channels = preferred_order + [ch for ch in all_channels if ch not in preferred_order]
        
        # Domyślnie zaznaczamy te z góry listy
        default_selection = [ch for ch in sorted_channels if any(p.lower() in ch.lower() for p in target_priorities)]
        if not default_selection:
            default_selection = sorted_channels[:10]

        selected_channels = st.multiselect(
            "Wybierz kanały:",
            options=sorted_channels,
            default=default_selection
        )
        
        movies = data['movies']
        if movies:
            dates = [datetime.fromisoformat(m['start_time']) for m in movies]
            min_date = min(dates).date()
            max_date = max(dates).date()
            
            date_from = st.date_input("Data od:", value=datetime.now().date(), min_value=min_date, max_value=max_date)
            date_to = st.date_input("Data do:", value=datetime.now().date() + timedelta(days=3), min_value=min_date, max_value=max_date)
        else:
            date_from = datetime.now().date()
            date_to = date_from + timedelta(days=3)
        
        st.markdown("### ⏰ Godziny emisji")
        time_from = st.time_input("Od godziny:", value=time(18, 0))
        time_to = st.time_input("Do godziny:", value=time(23, 59))
        
        min_rating = st.slider("Min. ocena IMDb:", 0.0, 10.0, 6.0, 0.5)
        
        sort_option = st.selectbox(
            "Sortuj po:",
            ["⏰ Czas emisji", "⭐ Ocena IMDb", "🎬 Tytuł"]
        )
        
        st.divider()
        if st.button("🔄 Odśwież dane"):
            st.cache_data.clear()
            st.rerun()

st.title("📺 Smart TV Guide")

if not data:
    st.error("❌ Nie znaleziono pliku data/movies.json!")
    st.info("Upewnij się, że skrypt skrapujący dane zadziałał poprawnie.")
    st.stop()

# Nagłówki statystyk
col1, col2, col3 = st.columns(3)
with col1:
    updated = datetime.fromisoformat(data['updated_at'])
    st.metric("Ostatnia aktualizacja", updated.strftime("%d.%m %H:%M"))
with col2:
    st.metric("Filmów w bazie", data['count'])
with col3:
    next_update = updated + timedelta(hours=6)
    st.metric("Następna aktualizacja ok.", next_update.strftime("%H:%M"))

st.markdown("---")

# Filtrowanie
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

# Sortowanie
if sort_option == "⏰ Czas emisji":
    filtered.sort(key=lambda x: x['start_time'])
elif sort_option == "⭐ Ocena IMDb":
    filtered.sort(key=lambda x: x.get('tmdb', {}).get('rating', 0), reverse=True)
else:
    filtered.sort(key=lambda x: x.get('tmdb', {}).get('title', x['title']))

st.write(f"**Znaleziono {len(filtered)} filmów spełniających kryteria**")

if len(filtered) == 0:
    st.warning("Brak filmów dla wybranych filtrów. Spróbuj zmniejszyć wymagania co do oceny lub dodać więcej kanałów.")
    # Pomoc dla użytkownika: pokaż jakie kanały w ogóle są w bazie
    with st.expander("Sprawdź dostępne kanały w bazie"):
        st.write(", ".join(all_channels))
else:
    view_mode = st.radio("Widok:", ["📊 Kanały", "🎬 Plakaty", "📋 Tabela"], horizontal=True)
    
    if view_mode == "📊 Kanały":
        channels_dict = {}
        for movie in filtered:
            ch = movie['channel_name']
            if ch not in channels_dict: channels_dict[ch] = []
            channels_dict[ch].append(movie)
        
        for channel, channel_movies in channels_dict.items():
            with st.expander(f"📺 {channel} ({len(channel_movies)})", expanded=True):
                for m in channel_movies:
                    tmdb = m.get('tmdb', {})
                    dt = datetime.fromisoformat(m['start_time'])
                    col1, col2, col3, col4 = st.columns([1, 1, 3, 1])
                    with col1:
                        st.markdown(f"**{dt.strftime('%H:%M')}**")
                        st.caption(dt.strftime('%d.%m'))
                    with col2:
                        if tmdb.get('poster'): st.image(tmdb['poster'], width=80)
                    with col3:
                        st.markdown(f"**{tmdb.get('title', m['title'])}** ({tmdb.get('year', '')})")
                        st.markdown(f"⭐ {tmdb.get('rating', 0)}/10")
                    with col4:
                        if st.button("Szczegóły", key=f"det_{m['channel_id']}_{m['start_time']}"):
                            st.session_state.selected_movie = m
                            st.rerun()

    elif view_mode == "🎬 Plakaty":
        for m in filtered:
            tmdb = m.get('tmdb', {})
            dt = datetime.fromisoformat(m['start_time'])
            col1, col2, col3 = st.columns([1, 4, 1])
            with col1:
                if tmdb.get('poster'): st.image(tmdb['poster'], width=120)
            with col2:
                st.subheader(tmdb.get('title', m['title']))
                st.write(f"📺 {m['channel_name']} | ⏰ {dt.strftime('%d.%m %H:%M')}")
                st.write(f"⭐ IMDb: {tmdb.get('rating', 0)}")
                if tmdb.get('overview'): st.caption(tmdb['overview'][:200] + "...")
            with col3:
                if st.button("Więcej", key=f"post_{m['channel_id']}_{m['start_time']}"):
                    st.session_state.selected_movie = m
                    st.rerun()
            st.divider()

    else:
        df_data = [{
            'Czas': datetime.fromisoformat(m['start_time']).strftime('%d.%m %H:%M'),
            'Kanał': m['channel_name'],
            'Tytuł': m.get('tmdb', {}).get('title', m['title']),
            'Ocena': m.get('tmdb', {}).get('rating', 0)
        } for m in filtered]
        st.dataframe(pd.DataFrame(df_data), use_container_width=True, hide_index=True)

# Dialog ze szczegółami
if st.session_state.selected_movie:
    m = st.session_state.selected_movie
    tmdb = m.get('tmdb', {})
    dt = datetime.fromisoformat(m['start_time'])
    
    @st.dialog("🎬 Szczegóły filmu")
    def show_movie_details():
        col1, col2 = st.columns([1, 2])
        with col1:
            if tmdb.get('poster'): st.image(tmdb['poster'])
        with col2:
            st.title(tmdb.get('title', m['title']))
            st.write(f"📅 Rok: {tmdb.get('year', 'Brak danych')}")
            st.write(f"⭐ Ocena: {tmdb.get('rating', 0)}/10")
            st.divider()
            st.write(f"📺 Kanał: **{m['channel_name']}**")
            st.write(f"⏰ Start: {dt.strftime('%d.%m %H:%M')}")
        
        if tmdb.get('overview'):
            st.write("### Opis fabuły")
            st.write(tmdb['overview'])
            
        if st.button("Zamknij"):
            st.session_state.selected_movie = None
            st.rerun()
    
    show_movie_details()
