import os
import zipfile
import collections
import requests
import io
import datetime
import re
import pdfplumber
import json
import time
class SMNProvider:
    def __init__(self, location_id="CHAPELCO"):
        self.location_id = location_id
        self.zip_url = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=pron5d"
        self.cache_file = "smn_cache.json"
        
    def _load_cache(self):
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                    if time.time() - data.get('timestamp', 0) < 86400: # 24 hours
                        return data.get('content')
            return None
        except: return None
    def _save_cache(self, content):
        try:
            with open(self.cache_file, 'w') as f:
                json.dump({'timestamp': time.time(), 'content': content}, f)
        except: pass
    def get_forecast(self):
        content = None
        # 1. LIVE ATTEMPT
        try:
            r = requests.get(self.zip_url, stream=True, timeout=10)
            if r.status_code == 200:
                with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                    txt_files = [n for n in z.namelist() if n.endswith('.txt')]
                    if txt_files:
                        with z.open(txt_files[0]) as f:
                            raw_content = f.read().decode('latin-1', errors='ignore')
                            if len(raw_content) > 0 and self.location_id in raw_content:
                                content = raw_content
                                self._save_cache(content)
        except Exception as e:
            print(f"SMN Live Fetch Error: {e}")
        # 2. FALLBACK
        if not content:
            content = self._load_cache()
        if not content: return None
        # 3. PARSING
        try:
            lines = content.splitlines()
            capture = False
            date_pattern = re.compile(r'^\s*\d{1,2}/[A-Z]{3}/\d{4}')
            daily_agg = collections.defaultdict(lambda: {'temps': [], 'winds': [], 'precip': 0.0, 'dirs': []})
            meses = {"ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6, 
                     "JUL": 7, "AGO": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12}
            
            for line in lines:
                if self.location_id in line:
                    capture = True
                    continue 
                if capture:
                    if date_pattern.match(line):
                        parts = line.split()
                        try:
                            date_raw = parts[0]
                            day, month_str, year = date_raw.split('/')
                            date_obj = datetime.date(int(year), meses.get(month_str.upper(), 1), int(day))
                            temp = float(parts[2])
                            speed = 0
                            direction = "-"
                            if '|' in parts:
                                pipe_idx = parts.index('|')
                                speed = float(parts[pipe_idx + 1])
                                direction = parts[pipe_idx - 1]
                            daily_agg[date_obj]['temps'].append(temp)
                            daily_agg[date_obj]['winds'].append(speed)
                            daily_agg[date_obj]['dirs'].append(direction)
                        except: continue
                    elif "=======" in line:
                        break
            
            forecasts = []
            for date, data in sorted(daily_agg.items()):
                if not data['temps']: continue
                try: wind_dir = collections.Counter(data['dirs']).most_common(1)[0][0]
                except: wind_dir = "-"
                forecasts.append({
                    'date': date,
                    'max_temp': int(round(max(data['temps']))),
                    'min_temp': int(round(min(data['temps']))),
                    'wind_speed': int(round(max(data['winds']))),
                    'wind_dir': wind_dir,
                    'sky_text': "SMN", 
                    'source': 'SMN'
                })
            return forecasts
        except Exception: return None
class AICProvider:
    def __init__(self):
        self.pdf_url = "https://www.aic.gob.ar/sitio/extendido-pdf?a=1029&z=1750130550"
    def _clean_int(self, text):
        if not text: return None
        matches = re.findall(r'-?\d+', text)
        if matches: return int(matches[0])
        return None
    def get_forecast(self):
        try:
            response = requests.get(self.pdf_url, stream=True, timeout=10)
            with pdfplumber.open(io.BytesIO(response.content)) as pdf:
                page = pdf.pages[0]
                table = max(page.extract_tables(), key=len)
                forecasts = []
                row_map = {}
                for i, row in enumerate(table):
                    if not row or not row[0]: continue
                    label = row[0].lower()
                    if "cielo" in label: row_map['sky'] = i
                    elif "temp" in label: row_map['temp'] = i
                    elif "viento" in label: row_map['wind'] = i
                    elif "dir" in label: row_map['dir'] = i
                    elif "pres" in label: row_map['pres'] = i
                
                date_row = table[0]
                for c in range(1, len(date_row), 2):
                    if c+1 >= len(date_row): break
                    try: date_obj = datetime.datetime.strptime(date_row[c], "%d-%m-%Y").date()
                    except: continue 
                    sky_day = table[row_map.get('sky', 2)][c]
                    max_temp = self._clean_int(table[row_map.get('temp', 3)][c])
                    min_temp = self._clean_int(table[row_map.get('temp', 3)][c+1])
                    wind_speed = self._clean_int(table[row_map.get('wind', 4)][c])
                    wind_dir = table[row_map.get('dir', 6)][c]
                    pres = self._clean_int(table[row_map.get('pres', 7)][c])
                    
                    forecasts.append({
                        'date': date_obj,
                        'max_temp': max_temp,
                        'min_temp': min_temp,
                        'sky_text': sky_day.replace('\n', ' '),
                        'wind_speed': wind_speed,
                        'wind_dir': wind_dir,
                        'pressure': pres,
                        'source': 'AIC'
                    })
                return forecasts
        except: return None
class OpenMeteoProvider:
    def __init__(self, lat=-40.15, lon=-71.35):
        self.base_url = "https://api.open-meteo.com/v1/forecast"
        self.params = {
            "latitude": lat, "longitude": lon,
            "daily": ["wind_gusts_10m_max", "temperature_2m_max", "temperature_2m_min", "weather_code", "wind_speed_10m_max", "wind_direction_10m_dominant"],
            "timezone": "auto"
        }
    def get_data(self):
        try:
            r = requests.get(self.base_url, params=self.params, timeout=5)
            return r.json() if r.status_code == 200 else None
        except: return None
class MetNoProvider:
    def __init__(self, lat=-40.15, lon=-71.35):
        self.url = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
        self.params = {"lat": lat, "lon": lon}
        self.headers = {'User-Agent': 'WeatherAggregatorSMA/1.0 educational'}
    def get_forecast(self):
        try:
            r = requests.get(self.url, headers=self.headers, params=self.params, timeout=5)
            if r.status_code != 200: return None
            data = r.json()
            daily = {}
            for item in data['properties']['timeseries']:
                time_str = item['time']
                dt = datetime.datetime.fromisoformat(time_str.replace('Z', '+00:00')) - datetime.timedelta(hours=3)
                date_key = dt.date()
                details = item['data']['instant']['details']
                temp = details.get('air_temperature')
                wind = details.get('wind_speed')
                if date_key not in daily: daily[date_key] = {'temps': [], 'winds': []}
                if temp is not None: daily[date_key]['temps'].append(temp)
                if wind is not None: daily[date_key]['winds'].append(wind)
            
            forecasts = []
            for d, v in sorted(daily.items()):
                if not v['temps']: continue
                forecasts.append({
                    'date': d,
                    'max_temp': int(round(max(v['temps']))),
                    'min_temp': int(round(min(v['temps']))),
                    'wind_speed': int(round(max(v['winds']))),
                    'source': 'Met.no'
                })
            return forecasts
        except: return None
class AccuWeatherProvider:
    def get_forecast(self): return None
5. 

ai_reporter.py
Bot meteorólogo con modo híbrido (API + Fallback Offline).

import google.generativeai as genai
import os
class MeteorologistBot:
    def __init__(self):
        self.api_key = os.environ.get("GOOGLE_API_KEY") 
        if self.api_key:
            genai.configure(api_key=self.api_key)
        self.models = ["gemini-1.5-flash", "gemini-1.5-flash-8b", "gemini-2.0-flash-exp"]
    def generate_template_report(self, daily_data):
        sky = daily_data.get('sky_desc', 'Variable').lower()
        temp_max = daily_data.get('max_temp', 0)
        wind = daily_data.get('wind_speed', 0)
        
        condition = "tiempo agradable"
        if "lluvia" in sky or "llovizna" in sky: condition = "inestable"
        elif "tormenta" in sky: condition = "alerta por tormentas"
        elif "nieve" in sky: condition = "condiciones invernales"
        elif "despejado" in sky and temp_max > 25: condition = "caluroso"
        elif "despejado" in sky: condition = "buen tiempo"
        elif temp_max < 5: condition = "frío"
        
        if wind > 40: condition += " y ventoso"
        
        report = f"{daily_data['date_str']} – SMA: {condition} con {daily_data['sky_desc']}, máxima {daily_data['max_temp']}°C, mínima {daily_data['min_temp']}°C. Viento del {daily_data['wind_dir']} a {daily_data['wind_speed']} km/h (Ráfagas {daily_data['gusts']} km/h). #ClimaSMA"
        return report
    def generate_report(self, daily_data):
        # 1. Try API if Key exists
        if self.api_key:
            prompt = f"""
            Actúa como un meteorólogo local experto de San Martín de los Andes.
            Genera un reporte breve con "lógica de meteorólogo" para el siguiente día:
            
            Datos:
            Fecha: {daily_data['date_str']}
            Cielo: {daily_data['sky_desc']}
            Temp Máx: {daily_data['max_temp']}°C
            Temp Mín: {daily_data['min_temp']}°C
            Viento: {daily_data['wind_speed']} km/h (Dir: {daily_data['wind_dir']})
            Ráfagas: {daily_data['gusts']} km/h
            
            Formato OBLIGATORIO:
            {daily_data['date_str']} – SMA: [condiciones] con [cielo detallado], máxima {daily_data['max_temp']}°C, mínima {daily_data['min_temp']}°C. Viento del {daily_data['wind_dir']} a {daily_data['wind_speed']} km/h (Ráfagas {daily_data['gusts']} km/h). #ClimaSMA
            """
            for model_name in self.models:
                try:
                    model = genai.GenerativeModel(model_name)
                    response = model.generate_content(prompt)
                    return response.text.strip()
                except Exception: continue
        
        # 2. Fallback to Template (Offline Mode)
        return self.generate_template_report(daily_data) + " (Reporte Automático Offline)"
