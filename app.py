import streamlit as st
import requests
import google.generativeai as genai

st.set_page_config(page_title="Consenso Climático SMA", page_icon="🌤️")

# Configuración con Gemini 3
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    # Usamos Gemini 3 Flash que es el más moderno de tu lista
    model_ai = genai.GenerativeModel('models/gemini-3-flash-preview')
except Exception as e:
    st.error(f"Error de configuración: {e}")

st.title("🛰️ Monitor Climático SMA v3.0")

if st.button("Generar Pronóstico de 3 Días"):
    with st.spinner("Gemini 3 analizando modelos internacionales..."):
        try:
            url = "https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35&hourly=temperature_2m,precipitation_probability,precipitation,cloudcover,windspeed_10m,windgusts_10m&models=ecmwf_ifs04,gfs_seamless,icon_seamless&timezone=America%2FArgentina%2FBuenos_Aires&forecast_days=3"
            datos = requests.get(url).json()

            # Prompt optimizado para la versión 3
            prompt = f"""Analiza estos datos meteorológicos: {datos}.
            Redacta un informe profesional para HOY y los próximos DOS DÍAS.
            
            REGLAS CRÍTICAS:
            - Usa un lenguaje fluido (ej: "Se espera un día soleado" en lugar de "con despejado").
            - Para el viento, indica la dirección predominante (ej: "del Suroeste").
            - Si no hay lluvias, indica "sin precipitaciones".

            ESTRUCTURA POR DÍA:
            [Día de la semana] [Día] de [Mes] – San Martín de los Andes: [Resumen general] con [estado del cielo], máxima esperada de [Máx] °C y mínima de [Mín] °C. Viento [Dirección] de [Vel] a [Ráfaga] km/h, [Lluvias].
            #SanMartínDeLosAndes #ClimaSMA #[Condición1] #[Condición2] #[Condición3]
            ---
            """

            response = model_ai.generate_content(prompt)
            st.markdown("### 📊 Informe de Consenso (Gemini 3)")
            st.write(response.text)
            
        except Exception as e:
            st.error(f"Error: {e}")
