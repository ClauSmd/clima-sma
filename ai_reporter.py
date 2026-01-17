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
