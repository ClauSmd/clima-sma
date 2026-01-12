import pandas as pd
import datetime
from data_sources import SMNProvider, AICProvider, OpenMeteoProvider, AccuWeatherProvider, WindguruProvider, MetNoProvider
class FusionEngine:
    def __init__(self):
        self.smn = SMNProvider()
        self.aic = AICProvider()
        self.om = OpenMeteoProvider()
        self.metno = MetNoProvider() # New 4th Source
        self.aw = AccuWeatherProvider()
        self.wg = WindguruProvider()
    def get_5_day_forecast(self):
        # 1. Initialize target dates (Today + 4 days)
        today = datetime.date.today()
        target_dates = [today + datetime.timedelta(days=i) for i in range(5)]
        
        # 2. Fetch Data
        aic_data = self.aic.get_forecast() 
        smn_data = self.smn.get_forecast()
        om_data = self.om.get_data()
        metno_data = self.metno.get_forecast()
        aw_data = self.aw.get_forecast()
        wg_data = self.wg.get_forecast()
        
        # 3. Build Base DataFrame
        final_forecast = []
        
        # Helper to find date in list of dicts (Generic)
        def find_by_date(date, data):
            if not data: return None
            for d in data:
                if d['date'] == date: return d
            return None
        # Helper to find date in Open-Meteo
        def find_in_om(date, data):
            if not data or 'daily' not in data: return None
            daily = data['daily']
            times = daily.get('time', [])
            date_str = date.isoformat()
            try:
                idx = times.index(date_str)
                return {
                    'max_temp': round(daily['temperature_2m_max'][idx]),
                    'min_temp': round(daily['temperature_2m_min'][idx]),
                    'gusts': round(daily['wind_gusts_10m_max'][idx]),
                    'code': daily['weather_code'][idx],
                    'wind_speed': round(daily['wind_speed_10m_max'][idx]),
                    'wind_dir_deg': daily['wind_direction_10m_dominant'][idx]
                }
            except ValueError: return None
        wmo_codes = {
            0: "Despejado", 1: "Mayormente Despejado", 2: "Parcialmente Nublado", 3: "Nublado",
            45: "Niebla", 48: "Niebla", 51: "Llovizna", 53: "Llovizna", 55: "Llovizna",
            61: "Lluvias", 63: "Lluvias", 65: "Lluvias Fuertes",
            80: "Chubascos", 81: "Chubascos", 82: "Chubascos",
            95: "Tormenta", 96: "Tormenta Granizo", 99: "Tormenta Granizo"
        }
        
        def deg_to_cardinal(deg):
            dirs = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]
            idx = round(deg / 45) % 8
            return dirs[idx]
        for date in target_dates:
            day_summary = {
                'date': date,
                'date_str': date.strftime("%A %d").title().replace("Sunday", "Domingo").replace("Monday", "Lunes").replace("Tuesday", "Martes").replace("Wednesday", "Miércoles").replace("Thursday", "Jueves").replace("Friday", "Viernes").replace("Saturday", "Sábado"), # Simple Spanish mapping
                'sky_desc': "Desconocido",
                'max_temp': None,
                'min_temp': None,
                'wind_speed': None,
                'wind_dir': "-",
                'gusts': None,
                'pressure': "-",
                'source': 'Fusion'
            }
            
            aic_record = find_by_date(date, aic_data)
            smn_record = find_by_date(date, smn_data)
            metno_record = find_by_date(date, metno_data)
            om_record = find_in_om(date, om_data)
            
            # Placeholders
            aw_record = None 
            wg_record = None
            
            val_sources = []
            
            # 1. Open-Meteo (40%)
            if om_record:
                val_sources.append({'src': 'OM', 'max': om_record['max_temp'], 'min': om_record['min_temp'], 'wind': om_record['wind_speed'], 'weight': 0.4})
            
            # Others share 60%
            others = [
                ('AIC', aic_record),
                ('SMN', smn_record),
                ('Met.no', metno_record),
                ('AccuWeather', aw_record),
                ('Windguru', wg_record)
            ]
            
            active_others = []
            for name, rec in others:
                if rec:
                    val_sources.append({'src': name, 'max': rec['max_temp'], 'min': rec['min_temp'], 'wind': rec['wind_speed'], 'weight': 0.0})
                    active_others.append(name)
            
            # Distribute weights
            non_om_sources = [x for x in val_sources if x['src'] != 'OM']
            if non_om_sources:
                share = 0.6 / len(non_om_sources)
                for x in non_om_sources: x['weight'] = share
            elif val_sources:
                # Only OM available
                val_sources[0]['weight'] = 1.0
            # Calculate Weighted Averages
            w_max, w_min, w_wind, total_w = 0, 0, 0, 0
            for item in val_sources:
                if item['max'] is not None:
                    w_max += item['max'] * item['weight']
                    w_min += item['min'] * item['weight']
                    w_wind += item['wind'] * item['weight']
                    total_w += item['weight']
            
            if total_w > 0:
                day_summary['max_temp'] = int(round(w_max / total_w))
                day_summary['min_temp'] = int(round(w_min / total_w))
                day_summary['wind_speed'] = int(round(w_wind / total_w))
            
            # Sky/Icon Priority (AIC > OM > SMN...)
            if aic_record:
                day_summary['sky_desc'] = aic_record['sky_text']
                day_summary['wind_dir'] = aic_record['wind_dir']
                day_summary['pressure'] = f"{aic_record['pressure']} hPa" if aic_record['pressure'] else "-"
            elif om_record:
                day_summary['sky_desc'] = wmo_codes.get(om_record['code'], "Variable")
                day_summary['wind_dir'] = deg_to_cardinal(om_record['wind_dir_deg'])
            if om_record:
                day_summary['gusts'] = om_record['gusts']
            
            # Source Label
            srcs = [x['src'] for x in val_sources]
            day_summary['source'] = f"Fusion ({', '.join(srcs)})"
            # Ensure Integers
            if day_summary['max_temp'] is not None: day_summary['max_temp'] = int(round(day_summary['max_temp']))
            if day_summary['min_temp'] is not None: day_summary['min_temp'] = int(round(day_summary['min_temp']))
            if day_summary['wind_speed'] is not None: day_summary['wind_speed'] = int(round(day_summary['wind_speed']))
            if day_summary['gusts'] is not None: day_summary['gusts'] = int(round(day_summary['gusts']))
            # Debug Info
            day_summary['debug'] = {
                'aic': aic_record,
                'om': om_record,
                'smn': smn_record,
                'aw': metno_record, # Using AW slot to show Met.no for now, or I should add a column
                'wg': None
            }
            final_forecast.append(day_summary)
        return final_forecast
if __name__ == "__main__":
    engine = FusionEngine()
    forecast = engine.get_5_day_forecast()
    for day in forecast:
        print(day)
