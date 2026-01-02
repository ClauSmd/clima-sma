import streamlit as st
import requests
import google.generativeai as genai

# Configuración básica
st.set_page_config(page_title="Consenso Climático SMA", page_icon="🌤️")

# Configuración de la API con manejo de errores directo
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    # Usamos el nombre de modelo más estándar
    model_ai = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error(f"Error de configuración: {e}")

st.title("🛰️ Analizador Climático Infalible")
st.subheader("San Martín de los Andes")

if st.button('Generar Pronóstico de Consenso'):
    with st.spinner('Analizando modelos globales...'):
        try:
            # Datos de Open-Meteo
            url = "https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35&hourly=temperature_2m,precipitation_probability,precipitation,cloudcover,windspeed_10m,windgusts_10m,snowfall,showers&models=ecmwf_ifs04,gfs_seamless,icon_seamless&timezone=America%23Argentina%2FBuenos_Aires&forecast_days=1"
            datos = requests.get(url).json()
            
            # Instrucción exacta para la IA
            prompt = f"""Analiza estos datos meteorológicos: {datos}. 
            Genera un resumen siguiendo este formato exacto:
            [Día de la semana] [Día] de [Mes] – San Martín de los Andes: [condiciones generales] con [cielo], y máxima esperada de [temperatura máxima] °C, mínima de [temperatura mínima] °C. Viento del [dirección] entre [velocidad] y [velocidad máxima] km/h, [lluvias previstas]. 
            #SanMartínDeLosAndes #ClimaSMA #[Condición1] #[Condición2] #[Condición3]"""
            
            # Generar respuesta
            response = model_ai.generate_content(prompt)
            
            st.success("Análisis completado")
            st.info(response.text)
            
        except Exception as e:
            st.error(f"Error en el proceso: {e}")
