import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime, timedelta

# 1. Configuración de Estética y Página
st.set_page_config(page_title="Sintesis climatica sma", page_icon="🏔️", layout="centered")

# Estilo visual para mejorar la legibilidad
st.markdown("""
    <style>
    .stButton>button { 
        width: 100%; 
        border-radius: 10px; 
        height: 3.5em; 
        background-color: #2E7D32; 
        color: white; 
        font-weight: bold;
        border: none;
    }
    .stButton>button:hover {
        background-color: #1B5E20;
        color: white;
    }
    .stInfo { border-radius: 15px; border-left: 5px solid #2E7D32; }
    </style>
    """, unsafe_allow_html=True)

# 2. Configuración Gemini 3
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    model_ai = genai.GenerativeModel('models/gemini-3-flash-preview')
except Exception as e:
    st.error(f"Error de API: {e}")

# Título de la Aplicación
st.title("🏔️ Sintesis climatica sma V3.0")
st.markdown("---")

# 3. Barra Lateral (Sidebar)
st.sidebar.header("🗓️ Configuración")
fecha_base = st.sidebar.date_input("Fecha de inicio", datetime.now())
fecha_fin = fecha_base + timedelta(days=2)

st.sidebar.divider()
st.sidebar.subheader("🔗 Referencias Locales")
st.sidebar.caption("Comparativa opcional (SMN, AIC, AccuWeather)")
val_smn = st.sidebar.text_input("SMN (Máx/Mín)", placeholder="Ej: 28/11")
val_accu = st.sidebar.text_input("AccuWeather", placeholder="Ej: 32/13")
val_aic = st.sidebar.text_input("AIC", placeholder="Ej: 29/6")

# 4. Procesamiento al presionar el Botón
if st.button("Generar sintesis climatica"):
    with st.spinner("🧠 Analizando modelos y redactando informe..."):
        try:
            start_s = fecha_base.strftime("%Y-%m-%d")
            end_s = fecha_fin.strftime("%Y-%m-%d")
            
            # Consulta a Open-Meteo
            url = (f"https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35"
                   f"&hourly=temperature_2m,precipitation_probability,precipitation,cloudcover,windspeed_10m,windgusts_10m,snowfall"
                   f"&models=ecmwf_ifs04,gfs_seamless,icon_seamless"
                   f"&start_date={start_s}&end_date={end_s}&timezone=America%2FArgentina%2FBuenos_Aires")
            
            datos = requests.get(url).json()

            # Gestión de campos vacíos para evitar alucinaciones
            ref_data = []
            if val_smn: ref_data.append(f"SMN indica: {val_smn}")
            if val_accu: ref_data.append(f"AccuWeather indica: {val_accu}")
            if val_aic: ref_data.append(f"AIC indica: {val_aic}")
            contexto_referencia = "\n".join(ref_data) if ref_data else "No se proporcionaron datos externos. Basa tu análisis solo en los modelos técnicos."

            prompt = f"""
            ESTACIÓN: San Martín de los Andes.
            FECHAS: {start_s} al {end_s}.
            DATOS TÉCNICOS: {datos}
            REFERENCIAS DE COTEJO: {contexto_referencia}

            INSTRUCCIONES DE DISEÑO:
            1. Redacción amena, profesional y con EMOJIS variados (🌡️, ☀️, ☁️, 🌬️, 🌧️).
            2. Para CADA DÍA, si se cumplen estos umbrales, inserta la alerta JUSTO ANTES de los hashtags:
               - Viento > 45km/h: 🌬️ ALERTA POR VIENTO: [Descripción breve de intensidad y ráfagas]
               - Nieve > 0mm: ❄️ ALERTA POR NEVADAS: [Descripción breve]
               - Temperatura > 30°C: 🌡️ ADVERTENCIA POR CALOR: [Descripción breve]
               - Lluvia > 10mm: 🌧️ ALERTA POR LLUVIAS: [Descripción breve]
            
            ESTRUCTURA POR DÍA:
            [Emoji según clima] [Día de la semana] [Día num] de [Mes] – San Martín de los Andes: [Redacción fluida del clima], Máxima de [X]°C y mínima de [Y]°C. Viento del [Dirección] entre [Vel] y [Ráf] km/h. [Probabilidad de lluvias/nieve].
            [Línea de Alerta correspondiente al día si existe]
            #SanMartínDeLosAndes #ClimaSMA #[CondicionPrincipal]
            ---
            """

            response = model_ai.generate_content(prompt)
            
            st.markdown("### 📋 Síntesis Generada")
            st.info(response.text)
                
        except Exception as e:
            st.error(f"Se produjo un error al procesar los datos: {e}")

st.divider()
st.caption("Powered by Gemini 3 Flash | Consenso de Modelos GFS, ECMWF e ICON.")
