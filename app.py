import streamlit as st
import requests
import google.generativeai as genai

st.set_page_config(page_title="Consenso Climático SMA", page_icon="🌤️")

# Configuración Gemini 3
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    model_ai = genai.GenerativeModel('models/gemini-3-flash-preview')
except Exception as e:
    st.error(f"Configuración: {e}")

st.title("🛰️ Monitor Climático SMA v3.0")

# --- NUEVA SECCIÓN DE REFINAMIENTO ---
st.sidebar.header("🔍 Datos de Referencia (Opcional)")
st.sidebar.write("Ingresa lo que marcan las webs para refinar el consenso:")
val_smn = st.sidebar.text_input("SMN (Ej: 28/11)", placeholder="28/11")
val_accu = st.sidebar.text_input("AccuWeather (Ej: 32/13)", placeholder="32/13")
val_aic = st.sidebar.text_input("AIC (Ej: 29/6)", placeholder="29/6")

if st.button("Generar Pronóstico Refinado"):
    with st.spinner("Gemini 3 analizando divergencias..."):
        try:
            # Datos técnicos de modelos globales
            url = "https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35&hourly=temperature_2m,precipitation_probability,cloudcover,windspeed_10m,windgusts_10m&models=ecmwf_ifs04,gfs_seamless,icon_seamless&timezone=America%2FArgentina%2FBuenos_Aires&forecast_days=3"
            datos_raw = requests.get(url).json()

            # PROMPT DE JUICIO CRÍTICO
            prompt = f"""
            ESTACIÓN: San Martín de los Andes (SMA).
            DATOS TÉCNICOS (ECMWF/GFS/ICON): {datos_raw}
            
            REFERENCIAS EXTERNAS ACTUALES:
            - Servicio Meteorológico Nacional (SMN): {val_smn}
            - AccuWeather: {val_accu}
            - AIC: {val_aic}

            TAREA:
            1. Analiza la divergencia. AIC suele ser más preciso en mínimas en SMA por la inversión térmica, mientras que GFS (AccuWeather) a veces exagera las máximas en verano.
            2. Genera un "Consenso Inteligente" que no sea un simple promedio, sino una interpretación lógica.
            3. Si el SMN y AIC coinciden pero AccuWeather se dispara, dale más peso a los locales.

            FORMATO DE SALIDA (ESTRICTO):
            [Día de la semana] [Día] de [Mes] – San Martín de los Andes: [Resumen] con [cielo], Máx [Máx]°C / Mín [Mín]°C. Viento [Dirección] de [Vel] a [Ráf] km/h, [Lluvias].
            #SanMartínDeLosAndes #ClimaSMA #[Condición1] #[Condición2] #[Hashtag_Tendencia]
            ---
            """

            response = model_ai.generate_content(prompt)
            st.markdown("### 📊 Pronóstico de Consenso Refinado")
            st.info(response.text)
            
        except Exception as e:
            st.error(f"Error: {e}")
