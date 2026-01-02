import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime, timedelta

st.set_page_config(page_title="Consenso Climático SMA", page_icon="🌤️")

# Configuración Gemini 3
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    model_ai = genai.GenerativeModel('models/gemini-3-flash-preview')
except Exception as e:
    st.error(f"Configuración: {e}")

st.title("🛰️ Monitor Climático SMA v3.0")

# --- BARRA LATERAL: FECHA Y REFERENCIAS ---
st.sidebar.header("📅 Configuración de Consulta")

# Selector de fecha (por defecto hoy)
fecha_base = st.sidebar.date_input("Fecha de inicio", datetime.now())
fecha_fin = fecha_base + timedelta(days=2)

st.sidebar.divider()
st.sidebar.write(f"🔍 Referencias para el {fecha_base.strftime('%d/%m')}:")
val_smn = st.sidebar.text_input("SMN (Máx/Mín)", placeholder="Ej: 28/11")
val_accu = st.sidebar.text_input("AccuWeather", placeholder="Ej: 32/13")
val_aic = st.sidebar.text_input("AIC", placeholder="Ej: 29/6")

if st.button(f"Generar Consenso {fecha_base.strftime('%d/%m')} al {fecha_fin.strftime('%d/%m')}"):
    with st.spinner("Analizando modelos y comparando fuentes..."):
        try:
            # Formateamos fechas para la API
            start_str = fecha_base.strftime("%Y-%m-%d")
            end_str = fecha_fin.strftime("%Y-%m-%d")
            
            # URL dinámica con el rango de fechas elegido
            url = (
                f"https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35"
                f"&hourly=temperature_2m,precipitation_probability,cloudcover,windspeed_10m,windgusts_10m"
                f"&models=ecmwf_ifs04,gfs_seamless,icon_seamless"
                f"&start_date={start_str}&end_date={end_str}"
                f"&timezone=America%2FArgentina%2FBuenos_Aires"
            )
            
            datos_raw = requests.get(url).json()

            # PROMPT CON CONTEXTO DE FECHA Y COMPARATIVA
            prompt = f"""
            ESTACIÓN: San Martín de los Andes.
            RANGO SOLICITADO: {start_str} al {end_str} (3 días).
            
            DATOS TÉCNICOS DE MODELOS: {datos_raw}
            
            REFERENCIAS MANUALES (Solo para el día {start_str}):
            - SMN: {val_smn}
            - AccuWeather: {val_accu}
            - AIC: {val_aic}

            TAREA:
            1. Para el primer día ({start_str}), utiliza las 'REFERENCIAS MANUALES' para ajustar los datos de los modelos globales. Si hay mucha diferencia, prioriza el consenso entre AIC y SMN.
            2. Para los dos días siguientes, realiza la predicción basada en la tendencia de los modelos GFS/ECMWF/ICON.
            3. Redacta el informe con tono profesional y natural.

            FORMATO DE SALIDA:
            [Día de la semana] [Día] de [Mes] – San Martín de los Andes: [Resumen] con [cielo], Máx [Máx]°C / Mín [Mín]°C. Viento [Dirección] de [Vel] a [Ráf] km/h, [Lluvias].
            #SanMartínDeLosAndes #ClimaSMA #[Condición1] #[Condición2] #[Tendencia]
            ---
            """

            response = model_ai.generate_content(prompt)
            st.markdown(f"### 📊 Informe de Consenso Refinado")
            st.info(response.text)
            
        except Exception as e:
            st.error(f"Error: {e}")
