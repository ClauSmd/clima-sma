import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime, timedelta

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(
    page_title="Sintesis climatica sma V3.2", 
    page_icon="🏔️", 
    layout="centered"
)

# 2. CONFIGURACIÓN DE INTELIGENCIA ARTIFICIAL
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except Exception as e:
    st.error("Error: Configura tu GOOGLE_API_KEY en los Secrets de Streamlit.")

def sintetizar_con_ia(prompt):
    """
    Sistema de Respaldo con modelos validados de tu lista:
    1. Gemini 3 Flash (Análisis profundo)
    2. Gemini 2.0 Flash Lite (Salto de límites RPM)
    3. Gemini 2.0 Flash (Estable)
    """
    # Nombres exactos de tu lista de Google AI Studio
    modelos_a_probar = [
        'gemini-3-flash-preview',
        'gemini-2.0-flash-lite-preview',
        'gemini-2.0-flash'
    ]
    
    for nombre_modelo in modelos_a_probar:
        try:
            modelo_ai = genai.GenerativeModel(nombre_modelo)
            response = modelo_ai.generate_content(prompt)
            if response and response.text:
                return response.text, nombre_modelo
        except Exception as e:
            # Si el modelo no existe o la cuota se agotó, pasa al siguiente
            if "404" in str(e) or "429" in str(e):
                continue
    return None, None

# 3. INTERFAZ (SIDEBAR)
st.title("🏔️ Sintesis climatica sma V3.2")

st.sidebar.header("🗓️ Configuración")
fecha_base = st.sidebar.date_input("Fecha de inicio", datetime.now())

st.sidebar.divider()
st.sidebar.subheader("🔗 Calibración Manual")
val_smn = st.sidebar.text_input("SMN (Máx/Mín)", placeholder="Ej: 28/11")
val_aic = st.sidebar.text_input("AIC (Máx/Mín)", placeholder="Ej: 29/6")
val_accu = st.sidebar.text_input("AccuWeather", placeholder="Ej: 30/11")

# 4. LÓGICA DE PROCESAMIENTO
if st.button("Generar síntesis climática"):
    with st.spinner("🧠 Sincronizando modelos globales y calibrando datos..."):
        try:
            # Fechas para la API Open-Meteo
            start_s = fecha_base.strftime("%Y-%m-%d")
            end_s = (fecha_base + timedelta(days=2)).strftime("%Y-%m-%d")
            
            # Consulta Multi-Modelo (5 fuentes técnicas)
            modelos_query = "ecmwf_ifs04,gfs_seamless,icon_seamless,gem_seamless,metno_seamless"
            url = (f"https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35"
                   f"&hourly=temperature_2m,precipitation_probability,windspeed_10m,windgusts_10m,snowfall,cloudcover"
                   f"&models={modelos_query}"
                   f"&start_date={start_s}&end_date={end_s}&timezone=America%2FArgentina%2FBuenos_Aires")
            
            r = requests.get(url)
            datos_tecnicos = r.json()

            # CONSTRUCCIÓN DEL PROMPT (Respetando tu estructura guardada)
            referencias = f"SMN: {val_smn} | AIC (Dato Prioritario): {val_aic} | AccuWeather: {val_accu}"
            
            prompt = f"""
            ESTACIÓN: San Martín de los Andes.
            DATOS TÉCNICOS: {datos_tecnicos}
            REFERENCIAS LOCALES: {referencias}

            INSTRUCCIONES DE FORMATO (ESTRICTO):
            [Emoji] [Día de la semana] [Día] de [Mes] – San Martín de los Andes: [condiciones generales] con [cielo], y máxima esperada de [temperatura máxima] °C, mínima de [temperatura mínima] °C. Viento del [dirección] entre [velocidad] y [velocidad máxima] km/h, [lluvias previstas].
            ⚠️ ALERTA: [Solo si aplica por ráfagas > 45km/h, calor > 30°C o nieve]
            #[Lugar] #ClimaSMA #[Condicion1] #[Condicion2]

            NOTAS: La AIC es prioridad absoluta sobre los modelos globales. 
            Analiza el consenso entre ECMWF, GFS, ICON, GEM y METNO.
            """

            # Generación con respaldo automático
            resultado, modelo_final = sintetizar_con_ia(prompt)
            
            if resultado and modelo_final:
                st.info(resultado)
                st.divider()
                # Línea interna solicitada con el modelo real utilizado
                st.caption(f"Fusión híbrida de datos satelitales y referencias locales SMA. | Inteligencia: {modelo_final.upper()}")
            else:
                st.warning("⚠️ **Servicio temporalmente saturado.** Google limitó las consultas por este minuto. Esperá 60 segundos y volvé a intentar.")

        except Exception as e:
            st.error(f"Error en la consulta de datos: {e}")

st.sidebar.divider()
st.sidebar.info("Cerebro: Jerarquía Gemini 3 / 2.0 Lite / 2.0")
