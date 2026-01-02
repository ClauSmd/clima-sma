import streamlit as st
import requests
import google.generativeai as genai

st.set_page_config(page_title="Consenso Climático SMA", page_icon="🌤️")

st.title("🛰️ Analizador Climático Infalible")
st.subheader("San Martín de los Andes")

# --- INICIALIZACIÓN FORZADA ---
def inicializar_modelo():
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    
    # Probamos con las rutas absolutas de modelos estables
    nombres_modelos = [
        'models/gemini-1.5-flash-latest',
        'models/gemini-1.5-pro-latest',
        'models/gemini-pro'
    ]
    
    for nombre in nombres_modelos:
        try:
            model = genai.GenerativeModel(model_name=nombre)
            # Prueba de vida
            model.generate_content("test") 
            st.success(f"Conectado exitosamente a: {nombre}")
            return model
        except Exception:
            continue
    
    return None

model_ai = inicializar_modelo()

if model_ai is None:
    st.error("No se pudo conectar con ningún modelo de Google. Revisa si tu API Key es válida en Google AI Studio.")
    st.stop()

# --- ACCIÓN DEL BOTÓN ---
if st.button("Generar Pronóstico de Consenso"):
    with st.spinner("Analizando modelos GFS, ECMWF e ICON..."):
        try:
            # Consulta a Open-Meteo (SMA)
            url = "https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35&hourly=temperature_2m,precipitation_probability,precipitation,cloudcover,windspeed_10m,windgusts_10m,snowfall,showers&models=ecmwf_ifs04,gfs_seamless,icon_seamless&timezone=America%2FArgentina%2FBuenos_Aires&forecast_days=1"
            datos = requests.get(url).json()

            prompt = f"""Analiza estos datos meteorológicos: {datos}.
            Genera un resumen siguiendo ESTRICTAMENTE este formato:
            [Día de la semana] [Día] de [Mes] – San Martín de los Andes: [condiciones generales] con [cielo], y máxima esperada de [temperatura máxima] °C, mínima de [temperatura mínima] °C. Viento del [dirección del viento] entre [velocidad del viento] y [velocidad máxima del viento] km/h, [lluvias previstas].
            #SanMartínDeLosAndes #ClimaSMA #[Condición1] #[Condición2] #[Condición3]"""

            response = model_ai.generate_content(prompt)
            st.info(response.text)

        except Exception as e:
            st.error(f"Error al procesar los datos climáticos: {e}")
