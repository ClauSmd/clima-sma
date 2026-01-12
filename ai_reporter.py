import google.generativeai as genai
import os
import random
class MeteorologistBot:
    def __init__(self, api_key=None):
        # In a real deployed env, use os.environ['GOOGLE_API_KEY']
        # For this environment, we assume the user might have set it or we rely on default auth if available.
        # However, typically we need an API key. 
        # I will check if there is an env var, otherwise I will use a placeholder or ask user.
        # Since I am an AI assistant, I don't have the user's key. 
        # I'll implement the logic assuming the key is in generated code or env.
        # But wait, I can use the model available to ME? No, the code runs on user machine.
        # I will assume the user has the key or I'll add a snippet to configuring it.
        # For now, I will use a placeholder logic that fails gracefully if no key.
        self.api_key = os.environ.get("GOOGLE_API_KEY") 
        if self.api_key:
            genai.configure(api_key=self.api_key)
        # Rotation List (Mapping user requests to likely real available models)
        self.models = [
            "gemini-1.5-flash",
            "gemini-1.5-flash-8b",
            "gemini-2.0-flash-exp"
        ]
    def generate_template_report(self, daily_data):
        # Logic for conditions based on data
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
        
        # Build the string
        # {daily_data['date_str']} – SMA: [condiciones] con [cielo detallado], máxima {daily_data['max_temp']}°C, mínima {daily_data['min_temp']}°C. Viento del {daily_data['wind_dir']} orden de {daily_data['wind_speed']} km/h (Ráfagas {daily_data['gusts']} km/h). #ClimaSMA
        
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
                    # Set a conservative timeout if possible, but library might not expose it easily per call
                    response = model.generate_content(prompt)
                    return response.text.strip()
                except Exception as e:
                    print(f"Model {model_name} failed: {e}")
                    # If quota exceeded (429), break loop and go to fallback immediately? 
                    # Or continue to other models? Usually quota is per project.
                    # We continue just in case, but likely all will fail.
                    continue
        
        # 2. Fallback to Template (Offline Mode)
        return self.generate_template_report(daily_data) + " (Reporte Automático Offline)"
