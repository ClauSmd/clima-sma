import streamlit as st
import requests
import google.generativeai as genai

# 1. Configuración de la página
st.set_page_config(page_title="Consenso Climático SMA", page_icon="🌤️")

# 2. Configuración de seguridad para la API Key
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    # Probamos con la versión más estable para 2026
    model_ai = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error("Error en la configuración de la API Key. Revisa los Secrets en Streamlit.")

st.title("🛰️ Analizador Climático Infalible")
st.subheader("San Martín de los Andes")
st.markdown("---")

# 3. El Botón de Acción
if st.button('Generar Pronóstico de Consenso'):
    with st.spinner('Analizando modelos GFS, ECMWF e ICON...'):
        try:
            # Consulta a Open-Meteo con múltiples modelos profesionales
            # Latitud y Longitud de San Martín de los Andes
            url = "https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35&hourly=temperature_2m,precipitation_probability,precipitation,cloudcover,windspeed_10m,windgusts_10m,snowfall,showers&models=ecmwf_ifs04,gfs_seamless,icon_seamless&timezone=America%23Argentina%2FBuenos_Aires&forecast_days=1"
            
            response_data = requests.get(url)
            datos = response_data.json()
            
            # 4. Prompt optimizado para evitar errores de modelo
            prompt = f"""
            Actúa como un experto meteorólogo analizando datos para San Martín de los Andes.
            Datos crudos de modelos (ECMWF, GFS, ICON): {datos}
            
            Tu tarea es encontrar el consenso entre estos modelos y redactar el pronóstico.
            REGLA CRÍTICA: Debes responder ÚNICAMENTE con el siguiente formato, sin texto extra:
            
            [Día de la semana] [Día] de [Mes] – San Martín de los Andes: [condiciones generales] con [cielo], y máxima esperada de [temperatura máxima] °C, mínima de [temperatura mínima] °C. Viento del [dirección del viento] entre [velocidad del viento] y [velocidad máxima del viento] km/h, [lluvias previstas]. #SanMartínDeLosAndes #ClimaSMA #[Condición general 1] #[Condición general 2] #[Condición general 3]
            """
            
            # Generación del contenido
            resultado = model_ai.generate_content(prompt)
            
            st.success("Análisis de modelos completado con éxito")
            st.write("---")
            st.info(resultado.text)
            st.write("---")
            
        except Exception as e:
            st.error(f"Hubo un problema al procesar los datos: {e}")
            st.warning("Consejo: Asegúrate de que el modelo 'gemini-1.5-flash' esté habilitado en tu Google AI Studio.")

st.caption("Esta app analiza datos de supercomputadoras en tiempo real para generar un consenso.")
