# 📺 Smart TV Guide

Lekka aplikacja do przeglądania programu TV z polskich kanałów filmowych.

## 🚀 Funkcje

- ✅ Automatyczna aktualizacja EPG co 6h (GitHub Actions)
- ✅ Dane z EPG.ovh + oceny z TMDB
- ✅ Filtrowanie po kanałach, datach, ocenach
- ✅ 3 tryby wyświetlania
- ✅ Ultra-szybka (tylko UI, dane pre-generated)

## 🛠️ Setup

### 1. Dodaj TMDB API Key do GitHub Secrets

Settings → Secrets → Actions → New secret:
- Name: `TMDB_API_KEY`
- Value: `twoj_klucz_z_tmdb`

### 2. Uruchom pierwszy import

Actions → Update EPG Data → Run workflow

### 3. Deploy na Streamlit Cloud

Połącz repo i gotowe!

## 📊 Jak to działa
```
GitHub Actions (co 6h)
  ↓
Pobiera EPG.ovh
  ↓
Matchuje z TMDB
  ↓
Zapisuje data/movies.json
  ↓
Streamlit ładuje JSON (cache 1h)
```

## 🎯 Zalety

- ⚡ Błyskawiczna (bez importu w UI)
- 🤖 Automatyczna aktualizacja
- 💰 Darmowa (GitHub Actions free tier)
- 📦 Lekka (~200 linii kodu)
