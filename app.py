import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime, timedelta

# 1. Configuración de Estética y Página
st.set_page_config(page_title="Consenso Climático SMA", page_icon="🌤️", layout="centered")

# Estilo para que las alertas resalten
st.markdown("""
    <style>
    .reportview-container .main .block-container{ padding-top: 2rem; }
    .stAlert { margin-top: 1rem; }
    </style>
    """, unsafe_allow_html=True)

# 2. Configuración Gemini 3
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    model_ai = genai.GenerativeModel('models/gemini-3-flash-preview')
except Exception as e:
    st.error(f"Error de API: {e}")

st.title("🛰️ Monitor Climático SMA v3.0")
st.markdown("---")

# 3. Panel de Control (Sidebar)
st.sidebar.header("📅 Parámetros de Análisis")
fecha_base = st.sidebar.date_input("Fecha de inicio", datetime.now())
fecha_fin = fecha_base + timedelta(days=2)

st.sidebar.divider()
st.sidebar.subheader("🔍 Referencias Externas")
st.sidebar.caption("Dejar vacío si no hay datos para comparar.")
val_smn = st.sidebar.text_input("SMN (Máx/Mín)", value="")
val_accu = st.sidebar.text_input("AccuWeather", value="")
val_aic = st.sidebar.text_input("AIC", value="")

# 4. Lógica de Ejecución
if st.button(f"🚀 Generar Informe de Consenso"):
    with st.spinner("Sincronizando modelos GFS, ECMWF e ICON..."):
        try:
            # Fechas para API
            start_s = fecha_base.strftime("%Y-%m-%d")
            end_s = fecha_fin.strftime("%Y-%m-%d")
            
            url = (f"https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35"
                   f"&hourly=temperature_2m,precipitation_probability,precipitation,cloudcover,windspeed_10m,windgusts_10m,snowfall"
                   f"&models=ecmwf_ifs04,gfs_seamless,icon_seamless"
                   f"&start_date={start_s}&end_date={end_s}&timezone=America%2FArgentina%2FBuenos_Aires")
            
            datos = requests.get(url).json()

            # Evitar alucinaciones: Solo enviamos datos si existen
            ref_data = []
            if val_smn: ref_data.append(f"SMN marca: {val_smn}")
            if val_accu: ref_data.append(f"AccuWeather marca: {val_accu}")
            if val_aic: ref_data.append(f"AIC marca: {val_aic}")
            
            contexto_referencia = "\n".join(ref_data) if ref_data else "NO hay datos externos. Basa tu análisis 100% en los modelos técnicos adjuntos."

            prompt = f"""
            ESTACIÓN: San Martín de los Andes.
            FECHAS: {start_s} al {end_s}.
            DATOS TÉCNICOS: {datos}
            
            CONTEXTO DE REFERENCIA (Día 1):
            {contexto_referencia}

            TAREA:
            1. Genera el pronóstico para los 3 días siguiendo tu estructura habitual.
            2. Usa un lenguaje natural y fluido. No inventes datos si no te los proporcioné.
            3. SECCIÓN DE ALERTAS: Al final de TODO el informe, agrega un apartado llamado "⚠️ ALERTAS Y ADVERTENCIAS". 
               - Si detectas ráfagas > 45km/h: Alerta por viento fuerte.
               - Si hay nieve > 0mm: Alerta por nevadas.
               - Si hay lluvia > 10mm: Alerta por lluvias intensas.
               - Si la máxima > 30°C: Advertencia por altas temperaturas.
               - Si no hay nada relevante, indica: "Sin alertas vigentes".

            ESTRUCTURA POR DÍA:
            [Día] [Día num] de [Mes] – San Martín de los Andes: [Resumen] con [Cielo], Máx [X]°C / Mín [Y]°C. Viento [Dir] de [Vel] a [Ráf] km/h, [Lluvias].
            #SanMartínDeLosAndes #ClimaSMA #Hashtag1 #Hashtag2
            ---
            """

            response = model_ai.generate_content(prompt)
            
            # 5. Visualización de Resultados
            st.markdown("### 📊 Informe Final")
            with st.container():
                st.info(response.text)
                
        except Exception as e:
            st.error(f"Error técnico: {e}")

st.divider()
st.caption("Consenso dinámico procesado con Gemini 3 Flash. Datos: Open-Meteo.")
