import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime, timedelta

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(
    page_title="Sintesis climatica sma V3.0", 
    page_icon="🏔️", 
    layout="centered"
)

# 2. CONFIGURACIÓN DE INTELIGENCIA ARTIFICIAL
try:
    # Asegurate de tener cargada la clave en Settings > Secrets de Streamlit
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except Exception as e:
    st.error("Error: Configura tu GOOGLE_API_KEY en los Secrets de Streamlit.")

def sintetizar_con_ia(prompt):
    """
    Función de respaldo: Intenta usar Gemini 3 y, ante errores 404 o 429,
    salta automáticamente a Gemini 1.5 Flash.
    """
    # Identificadores de modelos validados para evitar errores de ruta
    modelos_a_probar = ['gemini-3-flash-preview', 'gemini-1.5-flash']
    
    for nombre_modelo in modelos_a_probar:
        try:
            modelo_ai = genai.GenerativeModel(nombre_modelo)
            response = modelo_ai.generate_content(prompt)
            return response.text, nombre_modelo
        except Exception as e:
            # Captura error de cuota (429) o modelo no encontrado (404)
            if "429" in str(e) or "404" in str(e):
                continue
            else:
                return f"Error técnico inesperado: {e}", None
    return "Servicio temporalmente saturado. Reintentá en 1 minuto.", None

# 3. INTERFAZ (SIDEBAR)
st.title("🏔️ Sintesis climatica sma V3.0")

st.sidebar.header("🗓️ Configuración")
fecha_base = st.sidebar.date_input("Fecha de inicio", datetime.now())

st.sidebar.divider()
st.sidebar.subheader("🔗 Calibración Manual")
st.sidebar.caption("Tus datos tienen prioridad de 'Verdad de Campo'.")
val_smn = st.sidebar.text_input("SMN (Máx/Mín)", placeholder="Ej: 28/11")
val_aic = st.sidebar.text_input("AIC (Máx/Mín)", placeholder="Ej: 29/6")
val_accu = st.sidebar.text_input("AccuWeather", placeholder="Ej: 30/11")

# 4. LÓGICA DE PROCESAMIENTO
if st.button("Generar síntesis climática"):
    with st.spinner("🧠 Sincronizando modelos (ECMWF, GFS, ICON, GEM, METNO)..."):
        try:
            # Configuración de fechas
            start_s = fecha_base.strftime("%Y-%m-%d")
            end_s = (fecha_base + timedelta(days=2)).strftime("%Y-%m-%d")
            
            # Consulta Multi-Modelo a Open-Meteo
            modelos_query = "ecmwf_ifs04,gfs_seamless,icon_seamless,gem_seamless,metno_seamless"
            url = (f"https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35"
                   f"&hourly=temperature_2m,precipitation_probability,windspeed_10m,windgusts_10m,snowfall,cloudcover"
                   f"&models={modelos_query}"
                   f"&start_date={start_s}&end_date={end_s}&timezone=America%2FArgentina%2FBuenos_Aires")
            
            datos_tecnicos = requests.get(url).json()

            # Estructura del Prompt
            referencias = f"SMN: {val_smn} | AIC (Dato Prioritario): {val
