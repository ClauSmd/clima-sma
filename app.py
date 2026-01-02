import streamlit as st
import requests
import google.generativeai as genai

st.set_page_config(page_title="Consenso Climático SMA", page_icon="🌤️")

# Configuración simplificada al máximo
try:
    key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=key)
    # Usamos el modelo más básico y compatible
    model_ai = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error(f"Error de configuración: {e}")

st.title("🛰️ Analizador Climático SMA")

if st.button("Generar Pronóstico"):
    with st.spinner("Obteniendo datos..."):
        try:
            # Datos de Open-Meteo
            url = "https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35&hourly=temperature_2m,precipitation_probability,windspeed_10m&models=ecmwf_ifs04,gfs_seamless,icon_seamless&timezone=America%2FArgentina%2FBuenos_Aires&forecast_days=1"
            datos = requests.get(url).json()

            prompt = f"Resume estos datos: {datos}. Usa el formato: [Día] [Día] de [Mes] – San Martín de los Andes: [condiciones] con [cielo], máxima [máx] °C, mínima [mín] °C. Viento [vel] km/h, [lluvias]. #SanMartínDeLosAndes #ClimaSMA"

            # Intento de generación directa
            response = model_ai.generate_content(prompt)
            st.info(response.text)

        except Exception as e:
            st.error(f"Error: {e}")
            st.write("Si ves un 404, por favor crea una NUEVA API Key en un proyecto nuevo en Google AI Studio.")
