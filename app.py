import streamlit as st
import requests
import google.generativeai as genai

st.set_page_config(page_title="Consenso Climático SMA", page_icon="🌤️")

# Configuración del modelo con "red de seguridad"
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    # Forzamos la versión 1.5 Flash que es la gratuita y rápida
    model_ai = genai.GenerativeModel(model_name='gemini-1.5-flash')
except Exception as e:
    st.error(f"Error de configuración: {e}")

st.title("🛰️ Analizador Climático Infalible")
st.subheader("San Martín de los Andes")

if st.button('Generar Pronóstico de Consenso'):
    with st.spinner('Analizando modelos GFS, ECMWF e ICON...'):
        try:
            # Consulta a Open-Meteo (Datos de hoy)
            url = "https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35&hourly=temperature_2m,precipitation_probability,precipitation,cloudcover,windspeed_10m,windgusts_10m,snowfall,showers&models=ecmwf_ifs04,gfs_seamless,icon_seamless&timezone=America%23Argentina%2FBuenos_Aires&forecast_days=1"
            datos = requests.get(url).json()
            
            # Prompt optimizado para evitar errores de contenido
            prompt = f"Analiza estos datos meteorológicos de SMA: {datos}. Genera un resumen siguiendo ESTRICTAMENTE este formato: [Día de la semana] [Día] de [Mes] – San Martín de los Andes: [condiciones] con [cielo], y máxima esperada de [temp] °C, mínima de [temp] °C. Viento del [dir] entre [vel] y [vel] km/h, [lluvias]. #SanMartínDeLosAndes #ClimaSMA"
            
            # Llamada directa al método de generación
            response = model_ai.generate_content(prompt)
            
            if response.text:
                st.success("Análisis completado")
                st.info(response.text)
            else:
                st.warning("La IA no pudo generar el texto, intenta nuevamente.")
                
        except Exception as e:
            # Este bloque nos dirá si el error es de la API o del modelo
            st.error(f"Error técnico: {e}")
