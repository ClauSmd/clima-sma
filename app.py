import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime, timedelta

# 1. Configuración de Estética
st.set_page_config(page_title="Sintesis climatica sma", page_icon="🏔️", initial_sidebar_state="expanded")

# 2. Configuración Gemini 3
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    model_ai = genai.GenerativeModel('models/gemini-3-flash-preview')
except Exception as e:
    st.error(f"Error de API: {e}")

st.title("🏔️ Sintesis climatica sma V3.0")

# 3. Sidebar
st.sidebar.header("🗓️ Configuración")
fecha_base = st.sidebar.date_input("Fecha de inicio", datetime.now())

st.sidebar.divider()
st.sidebar.subheader("🔗 Calibración Manual")
val_smn = st.sidebar.text_input("SMN (Máx/Mín)", placeholder="Ej: 28/11")
val_aic = st.sidebar.text_input("AIC (Máx/Mín)", placeholder="Ej: 29/6")
val_accu = st.sidebar.text_input("AccuWeather", placeholder="Ej: 30/11")

# 4. Procesamiento
if st.button("Generar sintesis climatica"):
    with st.spinner("🧠 Sincronizando modelos con el formato solicitado..."):
        try:
            start_s = fecha_base.strftime("%Y-%m-%d")
            end_s = (fecha_base + timedelta(days=2)).strftime("%Y-%m-%d")
            
            modelos_query = "ecmwf_ifs04,gfs_seamless,icon_seamless,gem_seamless,metno_seamless"
            url = (f"https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35"
                   f"&hourly=temperature_2m,precipitation_probability,windspeed_10m,windgusts_10m,snowfall,cloudcover"
                   f"&models={modelos_query}"
                   f"&start_date={start_s}&end_date={end_s}&timezone=America%2FArgentina%2FBuenos_Aires")
            
            datos = requests.get(url).json()

            ref_data = []
            if val_smn: ref_data.append(f"SMN: {val_smn}")
            if val_aic: ref_data.append(f"AIC: {val_aic}")
            if val_accu: ref_data.append(f"AccuWeather: {val_accu}")
            contexto_referencia = "\n".join(ref_data) if ref_data else "Sin datos manuales."

            # PROMPT CON ESTRUCTURA RÍGIDA
            prompt = f"""
            ESTACIÓN: San Martín de los Andes.
            DATOS TÉCNICOS: {datos}
            CALIBRACIÓN MANUAL: {contexto_referencia}

            INSTRUCCIONES DE FORMATO (OBLIGATORIO):
            Para cada día, utiliza EXACTAMENTE esta estructura, sin negritas en los títulos ni etiquetas como "Condiciones" o "Viento":

            [Emoji de clima] [Día de la semana] [Día] de [Mes] – San Martín de los Andes: [condiciones generales] con [cielo], y máxima esperada de [temperatura máxima] °C, mínima de [temperatura mínima] °C. Viento del [dirección del viento] entre [velocidad del viento] y [velocidad máxima del viento] km/h, [lluvias previstas].
            [Emoji de Alerta] ALERTA: [Solo si aplica por ráfagas >45km/h, calor >30°C o nieve. Si no, omite esta línea]
            #[Lugar] #ClimaSMA #[Condición1] #[Condición2]

            REGLAS TÉCNICAS:
            - Los datos manuales (especialmente AIC) tienen prioridad sobre los modelos globales.
            - Usa emojis para que sea visualmente atractivo.
            - Separa cada día con una línea horizontal ---.
            """

            response = model_ai.generate_content(prompt)
            st.info(response.text)
                
        except Exception as e:
            st.error(f"Error técnico: {e}")

st.divider()
st.caption("Cerebro: Gemini 3 Flash | Estructura Personalizada SMA")
