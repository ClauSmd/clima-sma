import zipfile
import collections
import requests
import io
import datetime
import re
import pdfplumber
class SMNProvider:
    def __init__(self, location_id="CHAPELCO_AERO"):
        self.location_id = location_id # Now we search by Name
        self.zip_url = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=pron5d"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.cache_file = "smn_cache.json"
    def _parse_month(self, month_str):
        meses = {
            "ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
            "JUL": 7, "AGO": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12
        }
        return meses.get(month_str.upper(), 1)
    def get_forecast(self):
        try:
            # Download Zip
            r = requests.get(self.zip_url, stream=True, timeout=10)
            if r.status_code != 200: return None
            
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                # Find txt
                txt_files = [n for n in z.namelist() if n.endswith('.txt')]
                if not txt_files: return None
                
                with z.open(txt_files[0]) as f:
                    content = f.read().decode('latin-1', errors='ignore')
            
            # Parse Content
            lines = content.splitlines()
            start_idx = -1
            for i, line in enumerate(lines):
                if self.location_id in line:
                    start_idx = i
                    break
            
            if start_idx == -1: return None
            
            # Skip Headers (approx 5 lines based on inspection: Name, =====, Header, Units, =====)
            data_start = start_idx + 5
            
            daily_agg = collections.defaultdict(lambda: {'temps': [], 'winds': []})
            
            # Read until next station or end
            for i in range(data_start, len(lines)):
                line = lines[i].strip()
                if not line or "=" in line: 
                    # If empty or separator, might be end of block or just gap. 
                    # If "====" it's definitely end.
                    if "=" in line: break
                    continue
                
                # Format: 12/ENE/2026 00Hs. 13.1 4 | 6 0.0
                parts = line.split()
                if len(parts) < 6: continue
                
                try:
                    # Date: 12/ENE/2026
                    date_raw = parts[0]
                    day, month_str, year = date_raw.split('/')
                    date_obj = datetime.date(int(year), self._parse_month(month_str), int(day))
                    
                    # Temp: 13.1 (Index 2)
                    temp = float(parts[2])
                    
                    # Wind: 4 | 6 (Dir | Speed) -> Speed is index 5 usually
                    # line: 12/ENE... 00Hs. 13.1 4 | 6 0.0
                    # parts: [0]Date [1]Time [2]Temp [3]Dir [4]| [5]Speed [6]Precip
                    # Sometimes headers shift? Let's check for pipe
                    if '|' in parts:
                        pipe_idx = parts.index('|')
                        wind_speed = float(parts[pipe_idx + 1])
                    else:
                        wind_speed = 0
                    
                    daily_agg[date_obj]['temps'].append(temp)
                    daily_agg[date_obj]['winds'].append(wind_speed)
                    
                except Exception:
                    continue
            
            # Summarize
            forecasts = []
            for date, data in sorted(daily_agg.items()):
                if not data['temps']: continue
                forecasts.append({
                    'date': date,
                    'max_temp': int(round(max(data['temps']))),
                    'min_temp': int(round(min(data['temps']))),
                    'wind_speed': int(round(max(data['winds']))), # Using Max wind for safety
                    'sky_text': "SMN (Datos numéricos)", # SMN txt doesn't have clear sky desc
                    'wind_dir': "-", # Hard to agg direction
                    'pressure': "-",
                    'source': 'SMN'
                })
                
            return forecasts
            
        except Exception as e:
            print(f"SMN Error: {e}")
            return None
class AICProvider:
    def __init__(self):
        self.pdf_url = "https://www.aic.gob.ar/sitio/extendido-pdf?a=1029&z=1750130550"
    def _clean_int(self, text):
        if not text: return None
        matches = re.findall(r'-?\d+', text)
        if matches:
            return int(matches[0])
        return None
    def get_forecast(self):
        try:
            response = requests.get(self.pdf_url, stream=True, timeout=10)
            if response.status_code != 200:
                return None
            with pdfplumber.open(io.BytesIO(response.content)) as pdf:
                page = pdf.pages[0]
                tables = page.extract_tables()
                if not tables:
                    return None
                
                table = max(tables, key=len)
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
                num_cols = len(date_row)
                for c in range(1, num_cols, 2):
                    if c+1 >= num_cols: break
                    date_str = date_row[c]
                    try:
                        date_obj = datetime.datetime.strptime(date_str, "%d-%m-%Y").date()
                    except:
                        continue 
                        
                    day_idx = c
                    night_idx = c+1
                    
                    sky_day = table[row_map.get('sky', 2)][day_idx]
                    max_temp_raw = table[row_map.get('temp', 3)][day_idx]
                    min_temp_raw = table[row_map.get('temp', 3)][night_idx]
                    max_temp = self._clean_int(max_temp_raw)
                    min_temp = self._clean_int(min_temp_raw)
                    wind_raw = table[row_map.get('wind', 4)][day_idx] 
                    wind_speed = self._clean_int(wind_raw)
                    wind_dir = table[row_map.get('dir', 6)][day_idx]
                    pres_raw = table[row_map.get('pres', 7)][day_idx]
                    pressure_val = self._clean_int(pres_raw)
                    
                    forecasts.append({
                        'date': date_obj,
                        'max_temp': max_temp,
                        'min_temp': min_temp,
                        'sky_text': sky_day.replace('\n', ' '),
                        'wind_speed': wind_speed,
                        'wind_dir': wind_dir,
                        'pressure': pressure_val,
                        'source': 'AIC'
                    })
                    
                return forecasts
        except Exception as e:
            return None
class OpenMeteoProvider:
    def __init__(self, lat=-40.15, lon=-71.35):
        self.lat = lat
        self.lon = lon
        self.base_url = "https://api.open-meteo.com/v1/forecast"
    def get_data(self):
        params = {
            "latitude": self.lat,
            "longitude": self.lon,
            "daily": ["wind_gusts_10m_max", "temperature_2m_max", "temperature_2m_min", "weather_code", "wind_speed_10m_max", "wind_direction_10m_dominant"],
            "timezone": "auto"
        }
        try:
            response = requests.get(self.base_url, params=params, timeout=5)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            return None
class MetNoProvider:
    # 4th Source: Met.no (Norwegian Meteorological Institute)
    # Excellent global coverage, free API.
    def __init__(self, lat=-40.15, lon=-71.35):
        self.lat = lat
        self.lon = lon
        self.url = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
        self.headers = {
            'User-Agent': 'WeatherAggregatorSMA/1.0 (github.com/receptor-1) educational contact'
        }
    def get_forecast(self):
        try:
            params = {"lat": self.lat, "lon": self.lon}
            r = requests.get(self.url, headers=self.headers, params=params, timeout=5)
            if r.status_code != 200: return None
            
            data = r.json()
            timeseries = data['properties']['timeseries']
            
            # Aggregate by day
            daily = {}
            for item in timeseries:
                time_str = item['time']
                dt = datetime.datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                local_dt = dt - datetime.timedelta(hours=3) # Adjust for ART (UTC-3) roughly
                date_key = local_dt.date()
                
                details = item['data']['instant']['details']
                temp = details.get('air_temperature')
                wind = details.get('wind_speed')
                
                if date_key not in daily:
                    daily[date_key] = {'temps': [], 'winds': []}
                
                if temp is not None: daily[date_key]['temps'].append(temp)
                if wind is not None: daily[date_key]['winds'].append(wind)
                
            forecasts = []
            for d, v in sorted(daily.items()):
                if not v['temps']: continue
                forecasts.append({
                    'date': d,
                    'max_temp': int(round(max(v['temps']))),
                    'min_temp': int(round(min(v['temps']))),
                    'wind_speed': int(round(max(v['winds']))), # Max wind of day
                    'source': 'Met.no'
                })
            return forecasts
            
        except Exception as e:
            return None
class AccuWeatherProvider:
    def get_forecast(self): return None
class WindguruProvider:
    def get_forecast(self): return None
