import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime, timedelta

# 1. Configuración de Estética
st.set_page_config(page_title="Sintesis climatica sma", page_icon="🏔️", initial_sidebar_state="expanded")

# 2. Configuración de Inteligencia con Respaldo 2.5 Lite
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except Exception as e:
    st.error(f"Error de API: {e}")

def ejecutar_sintesis(prompt):
    # Intentamos primero con tu modelo principal y luego con el 2.5 Lite de tu lista
    modelos = ['gemini-3-flash-preview', 'gemini-2.5-flash-lite']
    for m in modelos:
        try:
            model_ai = genai.GenerativeModel(m)
            response = model_ai.generate_content(prompt)
            return response.text, m
        except Exception as e:
            if "429" in str(e) or "404" in str(e):
                continue # Salta al siguiente modelo si hay saturación o error de nombre
    return None, None

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

            # PROMPT ACTUALIZADO CON ANCLAJE DE FECHA REAL
            # fecha_base.strftime('%A') nos da el nombre del día seleccionado en el calendario
            prompt = f"""
            ESTACIÓN: San Martín de los Andes.
            FECHA DE INICIO: Hoy es {fecha_base.strftime('%A %d de %B de %Y')}.
            DATOS TÉCNICOS: {datos}
            CALIBRACIÓN MANUAL: {contexto_referencia}

            INSTRUCCIONES DE FORMATO (OBLIGATORIO):
            Genera el pronóstico para 3 días empezando desde hoy ({fecha_base.strftime('%A %d')}).
            Usa EXACTAMENTE esta estructura para cada día y sepáralos con ---:

            [Emoji] [Día de la semana] [Día] de [Mes] – San Martín de los Andes: [condiciones generales] con [cielo], y máxima esperada de [temperatura máxima] °C, mínima de [temperatura mínima] °C. Viento del [dirección del viento] entre [velocidad] y [velocidad máxima] km/h, [lluvias previstas].
            #[Lugar] #ClimaSMA #[Condición general 1] #[Condición general 2] #[Condición general 3]
            """

            resultado, modelo_usado = ejecutar_sintesis(prompt)
            
            if resultado:
                st.info(resultado)
                st.divider()
                st.caption(f"Fusión híbrida de datos satelitales y referencias locales SMA. | Inteligencia: {modelo_usado.upper()}")
            else:
                st.warning("⚠️ Servicio saturado en todos los modelos. Esperá un momento.")
                
        except Exception as e:
            st.error(f"Error técnico: {e}")

st.divider()
st.caption("Cerebro: Sistema de Respaldo 3.0 / 2.5 Lite | Fecha Sincronizada")
