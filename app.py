import streamlit as st
import requests
import google.generativeai as genai

# Configuración de página
st.set_page_config(page_title="Consenso Climático SMA", page_icon="🌤️")

# Acceder a la clave de API de forma segura
api_key = st.secrets["GOOGLE_API_KEY"]
genai.configure(api_key=api_key)
model_ai = genai.GenerativeModel('gemini-pro')

st.title("🛰️ Analizador Climático Infalible")
st.subheader("San Martín de los Andes")

if st.button('Generar Pronóstico de Consenso'):
    with st.spinner('Consultando modelos GFS, ECMWF e ICON...'):
        try:
            # Consulta a Open-Meteo con múltiples modelos
            url = "https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35&hourly=temperature_2m,precipitation_probability,precipitation,cloudcover,windspeed_10m,windgusts_10m,snowfall,showers&models=ecmwf_ifs04,gfs_seamless,icon_seamless&timezone=America%23Argentina%2FBuenos_Aires&forecast_days=3"
            datos = requests.get(url).json()
            
            prompt = f"Analiza estos datos climáticos multifuente: {datos}. Genera un pronóstico de consenso para hoy. Usa EXACTAMENTE este formato: [Día de la semana] [Día] de [Mes] – San Martín de los Andes: [condiciones] con [cielo], máxima [temp] °C, mínima [temp] °C. Viento del [dir] entre [vel] y [vel] km/h, [lluvias]. #SanMartínDeLosAndes #ClimaSMA"
            
            response = model_ai.generate_content(prompt)
            st.success("Análisis finalizado")
            st.info(response.text)
            
        except Exception as e:
            st.error(f"Error al conectar con los modelos: {e}")

st.caption("Los datos se actualizan en tiempo real al pulsar el botón.")
