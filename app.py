import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime, timedelta

# 1. Configuración de Estética y Diseño Visual Limpio
st.set_page_config(page_title="Sintesis climatica sma", page_icon="🏔️", initial_sidebar_state="expanded")

# Inyectamos CSS para eliminar el recuadro azul y mejorar la legibilidad
st.markdown("""
    <style>
    /* Estilo para el texto del resultado final */
    .reporte-final {
        background-color: transparent;
        padding: 10px;
        font-size: 1.1rem;
        line-height: 1.6;
        color: #f0f2f6; /* Ajusta según el tema oscuro/claro */
    }
    /* Estilo para los divisores */
    hr {
        margin: 1.5rem 0;
        border: 0;
        border-top: 1px solid #444;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. Configuración de Inteligencia
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

# 3. Sidebar: Calibración Manual Reordenada
st.sidebar.header("🗓️ Configuración")
fecha_base = st.sidebar.date_input("Fecha de inicio", datetime.now())

st.sidebar.divider()
st.sidebar.subheader("🔗 Fuentes de Referencia")

# NUEVO ORDEN SOLICITADO
with st.sidebar.expander("🇦🇷 SMN", expanded=False):
    smn_t = st.text_input("SMN Temp (Máx/Mín)", key="st")
    smn_v = st.text_input("SMN Viento (Min/Max)", key="sv")

with st.sidebar.expander("📍 AIC", expanded=False):
    aic_t = st.text_input("AIC Temp (Máx/Mín)", key="at")
    aic_v = st.text_input("AIC Viento (Min/Max)", key="av")

with st.sidebar.expander("🌬️ Windguru", expanded=False):
    wg_t = st.text_input("WG Temp", key="wt")
    wg_v = st.text_input("WG Viento/Ráfagas", key="wv")

with st.sidebar.expander("☁️ AccuWeather", expanded=False):
    accu_t = st.text_input("Accu Temp", key="act")
    accu_v = st.text_input("Accu Viento", key="acv")

# 4. Procesamiento
if st.button("Generar síntesis promediada"):
    with st.spinner("🧠 Sincronizando modelos..."):
        try:
            start_s = fecha_base.strftime("%Y-%m-%d")
            end_s = (fecha_base + timedelta(days=2)).strftime("%Y-%m-%d")
            
            url = (f"https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35"
                   f"&hourly=temperature_2m,precipitation_probability,windspeed_10m,windgusts_10m,snowfall,cloudcover"
                   f"&models=ecmwf_ifs04,gfs_seamless,icon_seamless,gem_seamless,metno_seamless"
                   f"&start_date={start_s}&end_date={end_s}&timezone=America%2FArgentina%2FBuenos_Aires")
            
            datos_satelitales = requests.get(url).json()

            referencias = []
            if smn_t or smn_v: referencias.append(f"SMN: T({smn_t}) V({smn_v})")
            if aic_t or aic_v: referencias.append(f"AIC: T({aic_t}) V({aic_v})")
            if wg_t or wg_v: referencias.append(f"Windguru: T({wg_t}) V({wg_v})")
            if accu_t or accu_v: referencias.append(f"AccuWeather: T({accu_t}) V({accu_v})")
            
            contexto_manual = "\n".join(referencias) if referencias else "No hay datos manuales."

            prompt = f"""
            ESTACIÓN: San Martín de los Andes.
            FECHA: Hoy es {fecha_base.strftime('%A %d de %B de %Y')}.
            DATOS SATELITALES: {datos_satelitales}
            REFERENCIAS LOCALES: {contexto_manual}

            TAREA: Pronóstico de 3 días (empezando {fecha_base.strftime('%A %d')}) promediando satélites y manuales.
            
            FORMATO ESTRICTO:
            [Emoji] [Día] de [Mes] – San Martín de los Andes: [condiciones] con [cielo], máxima de [max] °C, mínima de [min] °C. Viento del [dir] entre [min] y [max] km/h, [lluvias].
            [Emoji] ALERTA: [Solo si ráfagas >45km/h o calor >30°C]
            #[Lugar] #ClimaSMA #[Condición1] #[Condición2] #[Condición3]
            
            --- (Separador entre días)
            """

            resultado, modelo_usado = ejecutar_sintesis(prompt)
            
            if resultado:
                # Mostramos el resultado como texto plano para evitar el recuadro azul
                st.markdown(f'<div class="reporte-final">{resultado}</div>', unsafe_allow_html=True)
                st.divider()
                st.caption(f"Fusión Satelital + Local | Motor: {modelo_usado.upper()}")
            else:
                st.warning("⚠️ Servicio saturado.")
                
        except Exception as e:
            st.error(f"Error técnico: {e}")
