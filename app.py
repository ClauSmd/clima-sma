import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime, timedelta

# 1. CONFIGURACIÓN DE PÁGINA Y ESTÉTICA
st.set_page_config(
    page_title="Sintesis climatica sma V3.0", 
    page_icon="🏔️", 
    layout="centered"
)

# 2. CONFIGURACIÓN DE INTELIGENCIA ARTIFICIAL (GEMINI)
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except Exception as e:
    st.error("Error: No se encontró la API KEY en los Secrets de Streamlit.")

def sintetizar_con_ia(prompt):
    """
    Intenta generar el reporte con Gemini 3. 
    Si hay error de cuota (429) o no se encuentra (404), salta al 1.5.
    """
    modelos_a_probar = ['gemini-3-flash-preview', 'gemini-1.5-flash']
    
    for nombre_modelo in modelos_a_probar:
        try:
            modelo_ai = genai.GenerativeModel(nombre_modelo)
            response = modelo_ai.generate_content(prompt)
            return response.text, nombre_modelo
        except Exception as e:
            # Si es error de saturación o modelo no encontrado, probamos el siguiente
            if "429" in str(e) or "404" in str(e):
                continue
            else:
                return f"Error técnico: {e}", None
    return "Todos los modelos están saturados. Reintentá en 1 minuto.", None

# 3. INTERFAZ DE USUARIO (SIDEBAR)
st.title("🏔️ Sintesis climatica sma V3.0")

st.sidebar.header("🗓️ Configuración")
fecha_base = st.sidebar.date_input("Fecha de inicio", datetime.now())

st.sidebar.divider()
st.sidebar.subheader("🔗 Calibración Manual")
st.sidebar.caption("Tus datos tienen prioridad total sobre los modelos globales.")
val_smn = st.sidebar.text_input("SMN (Máx/Mín)", placeholder="Ej: 28/11")
val_aic = st.sidebar.text_input("AIC (Máx/Mín)", placeholder="Ej: 29/6")
val_accu = st.sidebar.text_input("AccuWeather", placeholder="Ej: 30/11")

# 4. PROCESAMIENTO PRINCIPAL
if st.button("Generar síntesis climática"):
    with st.spinner("🧠 Sincronizando 5 modelos globales y calibrando con datos locales..."):
        try:
            # Configuración de fechas para la API
            start_s = fecha_base.strftime("%Y-%m-%d")
            end_s = (fecha_base + timedelta(days=2)).strftime("%Y-%m-%d")
            
            # CONSULTA A OPEN-METEO (5 MODELOS TÉCNICOS)
            # ECMWF (IFS), GFS, ICON, GEM, METNO
            modelos_query = "ecmwf_ifs04,gfs_seamless,icon_seamless,gem_seamless,metno_seamless"
            url = (f"https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35"
                   f"&hourly=temperature_2m,precipitation_probability,windspeed_10m,windgusts_10m,snowfall,cloudcover"
                   f"&models={modelos_query}"
                   f"&start_date={start_s}&end_date={end_s}&timezone=America%2FArgentina%2FBuenos_Aires")
            
            datos_tecnicos = requests.get(url).json()

            # CONSTRUCCIÓN DEL PROMPT PARA LA IA
            ref_info = f"SMN: {val_smn} | AIC (Prioridad): {val_aic} | AccuWeather: {val_accu}"
            
            prompt = f"""
            ESTACIÓN: San Martín de los Andes.
            DATOS TÉCNICOS DE MODELOS (ECMWF, GFS, ICON, GEM, METNO): {datos_tecnicos}
            REFERENCIAS LOCALES INGRESADAS: {ref_info}

            TAREA: Realiza una síntesis climática profesional.
            
            REGLAS DE ORO:
            1. ESTRUCTURA (ESTRICTA): [Emoji] [Día de la semana] [Día] de [Mes] – San Martín de los Andes: [condiciones generales] con [cielo], y máxima esperada de [temperatura máxima] °C, mínima de [temperatura mínima] °C. Viento del [dirección] entre [velocidad] y [velocidad máxima] km/h, [lluvias previstas].
            2. CALIBRACIÓN: Si los datos de 'REFERENCIAS LOCALES' (especialmente AIC) difieren de los modelos técnicos, asume que los modelos tienen un sesgo y AJUSTA el pronóstico a la realidad local.
            3. ALERTAS: Agrega una línea con ⚠️ ALERTA si hay ráfagas > 45km/h, calor > 30°C o nieve.
            4. HASHTAGS: Al final de cada día poner #[Lugar] #ClimaSMA #[Condicion]
            """

            # EJECUCIÓN CON SISTEMA DE RESPALDO
            resultado, modelo_usado = sintetizar_con_ia(prompt)
            
            if resultado:
                st.info(resultado)
                
                # PIE DE PÁGINA DINÁMICO
                st.divider()
                st.caption(f"Fusión híbrida de datos satelitales y referencias locales SMA. | Inteligencia: {modelo_usado.upper()}")
            else:
                st.error("No se pudo procesar la información de los modelos.")

        except Exception as e:
            st.error(f"Error en la obtención de datos: {e}")

st.sidebar.divider()
st.sidebar.info("Cerebro: Gemini 3 Flash / 1.5 Flash")
