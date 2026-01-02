import streamlit as st
import requests
import google.generativeai as genai

st.set_page_config(page_title="Consenso Climático SMA", page_icon="🌤️")

# CONFIGURACIÓN FORZADA
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    # Forzamos la configuración para evitar el error v1beta
    genai.configure(api_key=api_key)
    # Usamos la ruta completa del modelo estable
    model_ai = genai.GenerativeModel(model_name='models/gemini-1.5-flash')
except Exception as e:
    st.error(f"Error de configuración: {e}")

st.title("🛰️ Analizador Climático SMA")

if st.button("Generar Pronóstico de Consenso"):
    with st.spinner("Consultando modelos GFS, ECMWF e ICON..."):
        try:
            # Consulta a Open-Meteo (SMA)
            url = "https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35&hourly=temperature_2m,precipitation_probability,precipitation,cloudcover,windspeed_10m,windgusts_10m,snowfall,showers&models=ecmwf_ifs04,gfs_seamless,icon_seamless&timezone=America%2FArgentina%2FBuenos_Aires&forecast_days=1"
            datos = requests.get(url).json()

            # Estructura guardada en tus instrucciones
            prompt = f"""Analiza estos datos meteorológicos: {datos}.
            Genera un resumen siguiendo ESTRICTAMENTE este formato:
            Viernes 2 de Enero – San Martín de los Andes: [condiciones generales] con [cielo], y máxima esperada de [temperatura máxima] °C, mínima de [temperatura mínima] °C. Viento del [dirección del viento] entre [velocidad del viento] y [velocidad máxima del viento] km/h, [lluvias previstas].
            #SanMartínDeLosAndes #ClimaSMA #[Condición1] #[Condición2] #[Condición3]"""

            # Generar contenido usando la API estable
            response = model_ai.generate_content(prompt)
            st.info(response.text)

        except Exception as e:
            st.error(f"Error técnico: {e}")
