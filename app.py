import streamlit as st
import requests
import google.generativeai as genai

# --------------------------------------------------
# Configuración de página
# --------------------------------------------------
st.set_page_config(
    page_title="Consenso Climático SMA",
    page_icon="🌤️"
)

st.title("🛰️ Analizador Climático Infalible")
st.subheader("San Martín de los Andes")

# --------------------------------------------------
# Inicialización Gemini (fallback REAL)
# --------------------------------------------------
MODELOS_GEMINI = [
    "gemini-1.5-flash",
    "gemini-1.5-pro"
]

def inicializar_modelo():
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)

    ultimo_error = None

    for modelo in MODELOS_GEMINI:
        try:
            model = genai.GenerativeModel(modelo)
            model.generate_content("Ping")
            st.success(f"Modelo Gemini activo: {modelo}")
            return model
        except Exception as e:
            ultimo_error = e

    raise RuntimeError(f"No se pudo inicializar Gemini. Último error: {ultimo_error}")

try:
    model_ai = inicializar_modelo()
except Exception as e:
    st.error(str(e))
    st.stop()

# --------------------------------------------------
# Acción principal
# --------------------------------------------------
if st.button("Generar Pronóstico de Consenso"):
    with st.spinner("Sincronizando modelos GFS, ECMWF e ICON..."):
        try:
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

            prompt = f"""
Analiza estos datos meteorológicos de San Martín de los Andes: {datos}

Devuelve SOLO este formato:

[Día] [fecha] – San Martín de los Andes:
[condición general], cielo [estado].
Máx [°C] / Mín [°C].
Viento [dirección] [velocidad] km/h.
[Lluvia / nieve / sin precipitaciones].

#SanMartínDeLosAndes #ClimaSMA
"""

            response = model_ai.generate_content(prompt)

            if response.text:
                st.success("Pronóstico generado")
                st.info(response.text)
            else:
                st.warning("Respuesta vacía del modelo")

        except Exception as e:
            st.error(f"Error técnico: {e}")
