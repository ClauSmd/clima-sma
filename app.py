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
st.sidebar.caption("Tus datos actúan como 'Verdad de Campo' para corregir los modelos.")
val_smn = st.sidebar.text_input("SMN (Máx/Mín)", placeholder="Ej: 28/11")
val_aic = st.sidebar.text_input("AIC (Máx/Mín)", placeholder="Ej: 29/6")
val_accu = st.sidebar.text_input("AccuWeather", placeholder="Ej: 30/11")

# 4. Procesamiento
if st.button("Generar sintesis climatica"):
    with st.spinner("🧠 Calibrando 5 modelos con tus datos de referencia..."):
        try:
            start_s = fecha_base.strftime("%Y-%m-%d")
            end_s = (fecha_base + timedelta(days=2)).strftime("%Y-%m-%d")
            
            # Consulta Multi-Modelo (ECMWF, GFS, ICON, GEM, METNO)
            modelos_query = "ecmwf_ifs04,gfs_seamless,icon_seamless,gem_seamless,metno_seamless"
            url = (f"https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35"
                   f"&hourly=temperature_2m,precipitation_probability,windspeed_10m,windgusts_10m,snowfall,cloudcover"
                   f"&models={modelos_query}"
                   f"&start_date={start_s}&end_date={end_s}&timezone=America%2FArgentina%2FBuenos_Aires")
            
            datos = requests.get(url).json()

            # Gestión de referencias para el Prompt
            ref_data = []
            if val_smn: ref_data.append(f"SMN (Referencia): {val_smn}")
            if val_aic: ref_data.append(f"AIC (Dato Prioritario): {val_aic}")
            if val_accu: ref_data.append(f"AccuWeather: {val_accu}")
            contexto_referencia = "\n".join(ref_data) if ref_data else "No se ingresaron datos manuales. Basar síntesis en el promedio ponderado de los 5 modelos."

            prompt = f"""
            ESTACIÓN: San Martín de los Andes.
            FECHAS: {start_s} al {end_s}.
            DATOS TÉCNICOS (Multi-Modelo): {datos}
            
            DATOS DE CALIBRACIÓN MANUAL (Día 1):
            {contexto_referencia}

            ROL DEL SISTEMA:
            Eres un experto meteorólogo de montaña. Tu tarea es sintetizar los 5 modelos globales (ECMWF, GFS, ICON, GEM, METNO).
            
            REGLAS DE ORO:
            1. PRIORIDAD: Si hay 'DATOS DE CALIBRACIÓN MANUAL', tómalos como la medición real actual. Si los modelos dicen algo distinto, asume que el modelo tiene un sesgo y corrígelo. 
            2. La AIC es especialmente confiable para las mínimas en el valle de SMA.
            3. ESTRUCTURA: [Emoji] [Día]... Máx/Mín, Viento.
            4. ALERTAS: Incluye alertas específicas por día si ráfagas > 45km/h, calor > 30°C o nevadas.
            """

            response = model_ai.generate_content(prompt)
            st.info(response.text)
                
        except Exception as e:
            st.error(f"Error técnico: {e}")

st.divider()
st.caption("Cerebro: Gemini 3 Flash | Modelos: ECMWF, GFS, ICON, GEM, METNO")
