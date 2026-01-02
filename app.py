import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime, timedelta

# 1. Configuración de Estética
st.set_page_config(page_title="Sintesis climatica sma", page_icon="🏔️", initial_sidebar_state="expanded")

# 2. Configuración de Inteligencia con Respaldo
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except Exception as e:
    st.error(f"Error de API: {e}")

def ejecutar_sintesis(prompt):
    modelos = ['gemini-3-flash-preview', 'gemini-2.5-flash-lite']
    for m in modelos:
        try:
            model_ai = genai.GenerativeModel(m)
            response = model_ai.generate_content(prompt)
            return response.text, m
        except Exception as e:
            if "429" in str(e) or "404" in str(e):
                continue
    return None, None

st.title("🏔️ Sintesis climatica sma V3.0")

# 3. Sidebar: Calibración Manual Multi-Fuente
st.sidebar.header("🗓️ Configuración")
fecha_base = st.sidebar.date_input("Fecha de inicio", datetime.now())

st.sidebar.divider()
st.sidebar.subheader("🔗 Fuentes de Referencia")
st.sidebar.caption("Ingresá datos para promediar con los satélites")

# Campos organizados por fuente (Temp y Viento)
with st.sidebar.expander("📍 AIC (Autoridad Local)", expanded=True):
    aic_t = st.text_input("AIC Temp (Máx/Mín)", key="at")
    aic_v = st.text_input("AIC Viento (km/h)", key="av")

with st.sidebar.expander("🌬️ Windguru"):
    wg_t = st.text_input("WG Temp", key="wt")
    wg_v = st.text_input("WG Viento/Ráfagas", key="wv")

with st.sidebar.expander("🇦🇷 SMN"):
    smn_t = st.text_input("SMN Temp", key="st")
    smn_v = st.text_input("SMN Viento", key="sv")

with st.sidebar.expander("☁️ AccuWeather"):
    accu_t = st.text_input("Accu Temp", key="act")
    accu_v = st.text_input("Accu Viento", key="acv")

# 4. Procesamiento
if st.button("Generar síntesis promediada"):
    with st.spinner("🧠 Procesando consenso entre modelos y referencias..."):
        try:
            start_s = fecha_base.strftime("%Y-%m-%d")
            end_s = (fecha_base + timedelta(days=2)).strftime("%Y-%m-%d")
            
            modelos_query = "ecmwf_ifs04,gfs_seamless,icon_seamless,gem_seamless,metno_seamless"
            url = (f"https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35"
                   f"&hourly=temperature_2m,precipitation_probability,windspeed_10m,windgusts_10m,snowfall,cloudcover"
                   f"&models={modelos_query}"
                   f"&start_date={start_s}&end_date={end_s}&timezone=America%2FArgentina%2FBuenos_Aires")
            
            datos_satelitales = requests.get(url).json()

            # Consolidación de datos manuales
            referencias = []
            if aic_t or aic_v: referencias.append(f"AIC: T({aic_t}) V({aic_v})")
            if wg_t or wg_v: referencias.append(f"Windguru: T({wg_t}) V({wg_v})")
            if smn_t or smn_v: referencias.append(f"SMN: T({smn_t}) V({smn_v})")
            if accu_t or accu_v: referencias.append(f"AccuWeather: T({accu_t}) V({accu_v})")
            
            contexto_manual = "\n".join(referencias) if referencias else "No hay datos manuales cargados."

            prompt = f"""
            ESTACIÓN: San Martín de los Andes.
            FECHA: Hoy es {fecha_base.strftime('%A %d de %B de %Y')}.
            
            DATOS TÉCNICOS (5 Modelos Satelitales): {datos_satelitales}
            REFERENCIAS LOCALES ADICIONALES: {contexto_manual}

            TAREA:
            Genera un pronóstico para 3 días. Tu objetivo es PROMEDIAR toda la información. 
            Si los satélites dicen una cosa y las referencias locales dicen otra, busca un punto medio lógico, dándole un poco más de peso a la AIC y Windguru para el viento.

            FORMATO DE SALIDA (ESTRICTO):
            [Emoji] [Día de la semana] [Día] de [Mes] – San Martín de los Andes: [condiciones] con [cielo], máxima de [temperatura máxima] °C, mínima de [temperatura mínima] °C. Viento del [dirección] entre [vel. mínima] y [vel. máxima] km/h, [lluvias].
            [Emoji] ALERTA: [Solo si el promedio final de ráfagas supera 45km/h o temperatura supera 30°C]
            #[Lugar] #ClimaSMA #[Condición1] #[Condición2] #[Condición3]
            
            ---
            Usa una línea horizontal entre cada día.
            """

            resultado, modelo_usado = ejecutar_sintesis(prompt)
            
            if resultado:
                st.info(resultado)
                st.divider()
                st.caption(f"Síntesis por consenso (Satelital + Local) | Motor: {modelo_usado.upper()}")
            else:
                st.warning("⚠️ Error de conexión con la IA. Reintentá en un minuto.")
                
        except Exception as e:
            st.error(f"Error técnico: {e}")

st.divider()
st.caption("Configuración SMA: Más datos = Mejor resultado.")
