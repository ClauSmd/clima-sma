import streamlit as st
import requests
import google.generativeai as genai

# --------------------------------------------------
# Configuración de la página
# --------------------------------------------------
st.set_page_config(
    page_title="Consenso Climático SMA",
    page_icon="🌤️",
    layout="centered"
)

st.title("🛰️ Analizador Climático Infalible")
st.subheader("San Martín de los Andes")

# --------------------------------------------------
# Configuración Gemini con fallback de modelos
# --------------------------------------------------
MODELOS_GEMINI = [
    "models/gemini-1.5-flash",   # recomendado
    "models/gemini-1.5-pro",     # más potente
    "models/gemini-1.0-pro"      # legacy (último recurso)
]

def inicializar_modelo():
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)

    ultimo_error = None

    for modelo in MODELOS_GEMINI:
        try:
            model = genai.GenerativeModel(modelo)
            # test mínimo para validar que el modelo responde
            model.generate_content("Test")
            st.success(f"Modelo activo: {modelo}")
            return model
        except Exception as e:
            ultimo_error = e

    raise RuntimeError(f"No se pudo inicializar ningún modelo Gemini. Último error: {ultimo_error}")

# Inicialización segura
try:
    model_ai = inicializar_modelo()
except Exception as e:
    st.error(str(e))
    st.stop()

# --------------------------------------------------
# Botón principal
# --------------------------------------------------
if st.button("Generar Pronóstico de Consenso"):
    with st.spinner("Sincronizando modelos GFS, ECMWF e ICON..."):
        try:
            # --------------------------------------------------
            # Consulta Open-Meteo
            # --------------------------------------------------
            url = (
                "https://api.open-meteo.com/v1/forecast"
                "?latitude=-40.15"
                "&longitude=-71.35"
                "&hourly=temperature_2m,precipitation_probability,"
                "precipitation,cloudcover,windspeed_10m,windgusts_10m,"
                "snowfall,showers"
                "&models=ecmwf_ifs04,gfs_seamless,icon_seamless"
                "&timezone=America%2FArgentina%2FBuenos_Aires"
                "&forecast_days=1"
            )

            datos = requests.get(url, timeout=20).json()

            # --------------------------------------------------
            # Prompt
            # --------------------------------------------------
            prompt = f"""
Analiza estos datos meteorológicos de San Martín de los Andes (SMA): {datos}

Genera el resultado siguiendo ESTRICTAMENTE este formato:

[Día de la semana] [Día] de [Mes] – San Martín de los Andes:
[condiciones generales] con [estado del cielo],
máxima de [temperatura máxima] °C y mínima de [temperatura mínima] °C.
Viento del [dirección] entre [velocidad mínima] y [velocidad máxima] km/h.
[Lluvias o nevadas previstas].

Finaliza con hashtags:
#SanMartínDeLosAndes #ClimaSMA #[Condición1] #[Condición2] #[Condición3]
"""

            # --------------------------------------------------
            # Generación con Gemini
            # --------------------------------------------------
            response = model_ai.generate_content(prompt)

            if response and response.text:
                st.success("Análisis completado")
                st.info(response.text)
            else:
                st.warning("La IA no devolvió texto. Intenta nuevamente.")

        except Exception as e:
            st.error(f"Error técnico: {e}")
