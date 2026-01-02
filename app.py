import streamlit as st
import requests
import google.generativeai as genai

# Configuración de página
st.set_page_config(page_title="Consenso Climático SMA", page_icon="🌤️")

# Conexión con el modelo verificado de tu lista
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    # Usamos el modelo 2.5 Flash que confirmamos que tienes activo
    model_ai = genai.GenerativeModel('models/gemini-2.5-flash')
except Exception as e:
    st.error(f"Error de configuración: {e}")

st.title("🛰️ Analizador Climático SMA")
st.subheader("Consenso GFS, ECMWF e ICON")

if st.button("Generar Pronóstico de Hoy"):
    with st.spinner("Analizando modelos climáticos..."):
        try:
            # Consulta de datos (SMA)
            url = "https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35&hourly=temperature_2m,precipitation_probability,precipitation,cloudcover,windspeed_10m,windgusts_10m&models=ecmwf_ifs04,gfs_seamless,icon_seamless&timezone=America%2FArgentina%2FBuenos_Aires&forecast_days=1"
            datos = requests.get(url).json()

            # Tu formato exacto de las instrucciones
            prompt = f"""Analiza estos datos meteorológicos: {datos}.
            Genera un resumen siguiendo ESTRICTAMENTE este formato:
            [Día de la semana] [Día] de [Mes] – San Martín de los Andes: [condiciones generales] con [cielo], y máxima esperada de [temperatura máxima] °C, mínima de [temperatura mínima] °C. Viento del [dirección del viento] entre [velocidad del viento] y [velocidad máxima del viento] km/h, [lluvias previstas].
            #SanMartínDeLosAndes #ClimaSMA #[Condición1] #[Condición2] #[Condición3]"""

            response = model_ai.generate_content(prompt)
            
            st.success("Análisis completado")
            st.markdown("---")
            st.info(response.text)
            st.markdown("---")
            
        except Exception as e:
            st.error(f"Error al generar el pronóstico: {e}")

st.caption("Datos procesados mediante consenso de modelos internacionales.")
