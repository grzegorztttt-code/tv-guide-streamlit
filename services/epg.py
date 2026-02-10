import requests
from datetime import datetime, timedelta

def fetch_tvmaze_schedule(country='PL', date=None):
    """
    Pobiera program TV z TVMaze API
    
    Args:
        country: Kod kraju (PL, US, UK, etc.)
        date: Data w formacie YYYY-MM-DD (domyślnie dzisiaj)
    
    Returns:
        Lista programów TV
    """
    if not date:
        date = datetime.now().strftime('%Y-%m-%d')
    
    url = f'https://api.tvmaze.com/schedule'
    params = {
        'country': country,
        'date': date
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Błąd pobierania EPG: {e}")
        return []

def normalize_epg_data(tvmaze_data):
    """
    Normalizuje dane z TVMaze do naszego formatu
    
    Returns:
        Lista słowników z kluczami: title, start_time, end_time, channel
    """
    normalized = []
    
    for item in tvmaze_data:
        show = item.get('show', {})
        
        # Tylko filmy (pomijamy seriale dla uproszczenia)
        if show.get('type') != 'Scripted':
            continue
        
        normalized.append({
            'title': show.get('name'),
            'start_time': item.get('airtime'),
            'runtime': item.get('runtime', 120),
            'channel': item.get('_embedded', {}).get('show', {}).get('network', {}).get('name', 'Unknown'),
            'external_ids': show.get('externals', {})
        })
    
    return normalized

def get_schedule_for_date_range(start_date, days=7, country='PL'):
    """
    Pobiera program na kilka dni
    
    Args:
        start_date: Data początkowa (datetime)
        days: Liczba dni
        country: Kod kraju
    
    Returns:
        Lista wszystkich programów
    """
    all_programs = []
    
    for i in range(days):
        date = (start_date + timedelta(days=i)).strftime('%Y-%m-%d')
        programs = fetch_tvmaze_schedule(country, date)
        all_programs.extend(programs)
    
    return all_programs
```

---

## 9️⃣ **`LICENSE`** (MIT License - opcjonalnie)
```
MIT License

Copyright (c) 2026 [Twoje Imię]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
