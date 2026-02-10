import sqlite3
from datetime import datetime

DB_PATH = 'data/tv_guide.db'

def init_db():
    """Tworzy bazę danych z tabelami"""
    conn = sqlite3.connect(DB_PATH)
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
    
    # Indexy
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_programs_time ON tv_programs(start_time)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_movies_tmdb ON movies(tmdb_id)')
    
    conn.commit()
    conn.close()

def get_connection():
    """Zwraca połączenie do bazy"""
    return sqlite3.connect(DB_PATH, check_same_thread=False)
