import streamlit as st
import requests
import google.generativeai as genai

# Configuración de página
st.set_page_config(page_title="Consenso Climático SMA", page_icon="🌤️")

# Conexión con el modelo verificado
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    # Usamos el modelo que confirmamos que funciona en tu cuenta
    model_ai = genai.GenerativeModel('models/gemini-2.5-flash')
except Exception as e:
    st.error(f"Error de configuración: {e}")

st.title("🛰️ Analizador Climático SMA")
st.subheader("Consenso para Hoy y próximos 2 días")

if st.button("Generar Pronóstico Extendido"):
    with st.spinner("Analizando modelos GFS, ECMWF e ICON para los próximos 3 días..."):
        try:
            # URL actualizada: forecast_days=3 para obtener hoy + 2 días
            url = "https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35&hourly=temperature_2m,precipitation_probability,precipitation,cloudcover,windspeed_10m,windgusts_10m&models=ecmwf_ifs04,gfs_seamless,icon_seamless&timezone=America%2FArgentina%2FBuenos_Aires&forecast_days=3"
            datos = requests.get(url).json()

            # Prompt ajustado para generar los 3 días por separado
            prompt = f"""Analiza estos datos meteorológicos de San Martín de los Andes: {datos}.
            
            Genera un resumen para HOY y los próximos DOS DÍAS (en total 3 días). 
            Debes entregar 3 bloques separados, uno por día, siguiendo ESTRICTAMENTE este formato para cada uno:

            [Día de la semana] [Día] de [Mes] – San Martín de los Andes: [condiciones generales] con [cielo], y máxima esperada de [temperatura máxima] °C, mínima de [temperatura mínima] °C. Viento del [dirección del viento] entre [velocidad] y [velocidad máxima] km/h, [lluvias previstas].
            #SanMartínDeLosAndes #ClimaSMA #[Condición1] #[Condición2] #[Condición3]
            
            Separa cada día con una línea horizontal o un espacio claro."""

            response = model_ai.generate_content(prompt)
            
            st.success("Análisis de 3 días completado")
            st.markdown("---")
            # Mostramos el resultado. Usamos markdown por si la IA usa negritas o separadores
            st.write(response.text)
            st.markdown("---")
            
        except Exception as e:
            st.error(f"Error al generar el pronóstico: {e}")

st.caption("Pronóstico generado por IA mediante consenso de modelos internacionales (ECMWF, GFS, ICON).")
