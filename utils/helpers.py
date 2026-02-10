from datetime import datetime, timedelta
import pandas as pd

def format_time(dt):
    """Formatuje datetime do czytelnego formatu"""
    if isinstance(dt, str):
        dt = pd.to_datetime(dt)
    return dt.strftime("%d.%m %H:%M")

def format_duration(minutes):
    """Konwertuje minuty na format HH:MM"""
    if not minutes:
        return "N/A"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins}min"

def get_rating_color(rating):
    """Zwraca emoji koloru według oceny"""
    if rating >= 8.0:
        return "🟢"
    elif rating >= 7.0:
        return "🟡"
    elif rating >= 6.0:
        return "🟠"
    else:
        return "🔴"

def filter_by_time_range(df, start_time, end_time):
    """Filtruje program po zakresie godzin"""
    df['hour'] = pd.to_datetime(df['start_time']).dt.time
    mask = (df['hour'] >= start_time) & (df['hour'] <= end_time)
    return df[mask]

def filter_by_genres(df, selected_genres):
    """Filtruje filmy po gatunkach"""
    if not selected_genres:
        return df
    
    def has_genre(genres_str):
        if not genres_str:
            return False
        return any(genre in str(genres_str) for genre in selected_genres)
    
    return df[df['genres'].apply(has_genre)]
