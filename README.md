
# 📺 Smart TV Guide

Prosta aplikacja do przeglądania programu TV z ocenami filmów.

## 🚀 Funkcje

- ✅ Przeglądanie programu TV
- ✅ Filtry: kanały, data, ocena, gatunki, godzina
- ✅ Integracja z TMDB (plakaty, opisy, oceny)
- ✅ Ulubione filmy
- ✅ Szczegóły filmów + trailery

## 🛠️ Instalacja lokalna
```bash
# Klonuj repo
git clone https://github.com/TwojUsername/tv-guide-streamlit.git
cd tv-guide-streamlit

# Zainstaluj zależności
pip install -r requirements.txt

# Ustaw API key
# Stwórz plik .env i dodaj:
# TMDB_API_KEY=twoj_klucz

# Uruchom
streamlit run app.py
```

## 🌐 Deploy na Streamlit Cloud

1. Fork tego repo
2. Idź na [share.streamlit.io](https://share.streamlit.io)
3. Połącz swoje GitHub
4. Wybierz repo i `app.py`
5. Dodaj Secret: `TMDB_API_KEY`
6. Deploy! 🎉

## 📝 Jak zdobyć TMDB API Key

1. Zarejestruj się na [themoviedb.org](https://www.themoviedb.org)
2. Idź do Settings → API
3. Request API Key (wybierz "Developer")
4. Skopiuj klucz

## 📸 Screenshots

(Dodaj screenshoty później)

## 🔮 Roadmap

- [ ] EPG auto-update (cron)
- [ ] Powiadomienia o ulubionych filmach
- [ ] Eksport do kalendarza
- [ ] Multi-user profiles
- [ ] Rekomendacje AI

## 📄 Licencja

MIT
