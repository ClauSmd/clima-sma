import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime, timedelta

# 1. Configuración de Estética y Página
st.set_page_config(page_title="Sintesis climatica sma", page_icon="🏔️")

# 2. Configuración Gemini
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except Exception as e:
    st.error(f"Error de configuración: {e}")

# FUNCIÓN DE RESPALDO (Para evitar el error 429)
def sintetizar_clima(prompt):
    # Intentamos primero con tu modelo preferido (Gemini 3 Flash)
    # Si falla por cuota, saltamos al 1.5 Flash que tiene 1500 consultas/día
    modelos = ['gemini-3-flash-preview', 'gemini-1.5-flash']
    
    for mod in modelos:
        try:
            modelo_ai = genai.GenerativeModel(mod)
            response = modelo_ai.generate_content(prompt)
            return response.text, mod
        except Exception as e:
            if "429" in str(e):
                continue # Salta al siguiente modelo si el actual está saturado
            else:
                return f"Error técnico: {e}", None
    return "Lo siento, todos los servicios están saturados. Reintentá en 1 minuto.", None

st.title("🏔️ Sintesis climatica sma V3.0")

# 3. Sidebar (Tu centro de control)
st.sidebar.header("🗓️ Configuración")
fecha_base = st.sidebar.date_input("Fecha de inicio", datetime.now())

st.sidebar.divider()
st.sidebar.subheader("🔗 Calibración Manual")
st.sidebar.caption("Tus datos son 'Verdad de Campo' y corrigen a los modelos.")
val_smn = st.sidebar.text_input("SMN (Máx/Mín)", placeholder="Ej: 28/11")
val_aic = st.sidebar.text_input("AIC (Máx/Mín)", placeholder="Ej: 29/6")
val_accu = st.sidebar.text_input("AccuWeather", placeholder="Ej: 30/11")

# 4. Lógica de Discusión de 5 Modelos
if st.button("Generar sintesis climatica"):
    with st.spinner("🧠 Consultando 5 modelos y calibrando con tus datos..."):
        try:
            start_s = fecha_base.strftime("%Y-%m-%d")
            end_s = (fecha_base + timedelta(days=2)).strftime("%Y-%m-%d")
            
            # Consulta a los 5 mejores modelos del mundo para SMA
            modelos_query = "ecmwf_ifs04,gfs_seamless,icon_seamless,gem_seamless,metno_seamless"
            url = (f"https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35"
                   f"&hourly=temperature_2m,precipitation_probability,windspeed_10m,windgusts_10m,snowfall,cloudcover"
                   f"&models={modelos_query}"
                   f"&start_date={start_s}&end_date={end_s}&timezone=America%2FArgentina%2FBuenos_Aires")
            
            datos_tecnicos = requests.get(url).json()

            # Construcción del Prompt con tu estructura guardada
            prompt = f"""
            ESTACIÓN: San Martín de los Andes.
            DATOS TÉCNICOS: {datos_tecnicos}
            REFERENCIAS LOCALES: SMN({val_smn}), AIC({val_aic}), Accu({val_accu})

            INSTRUCCIONES CRÍTICAS:
            1. ESTRUCTURA RÍGIDA: [Emoji] [Día de la semana] [Día] de [Mes] – San Martín de los Andes: [condiciones] con [cielo], y máxima esperada de [temperatura máxima] °C, mínima de [temperatura mínima] °C. Viento del [dirección] entre [vel] y [vel máx] km/h, [lluvias].
            2. PRIORIDAD: Si AIC indica valores distintos a los modelos, AJUSTA el reporte hacia los valores de la AIC (Verdad de Campo).
            3. ALERTAS: Una línea extra con emoji ⚠️ si ráfagas > 45km/h o temp > 30°C.
            4. FINAL: Agregá los hashtags #[Lugar] #ClimaSMA #[Condicion]
            """

            resultado, mod_usado = sintetizar_clima(prompt)
            
            if mod_usado:
                st.info(resultado)
                st.caption(f"⚙️ Motor: {mod_usado} | Consenso: ECMWF, GFS, ICON, GEM, METNO")
            else:
                st.error(resultado)

        except Exception as e:
            st.error(f"Error de conexión: {e}")

st.divider()
st.caption("Fusión híbrida de datos satelitales y referencias locales SMA.")
