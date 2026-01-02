import streamlit as st
import requests
import google.generativeai as genai

st.set_page_config(page_title="Consenso Climático SMA", page_icon="🌤️")

# Configuración del modelo con versión estable
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    # Cambiamos a 'gemini-pro' que tiene la ruta de API más estable
    model_ai = genai.GenerativeModel('gemini-pro')
except Exception as e:
    st.error(f"Error de configuración: {e}")

st.title("🛰️ Analizador Climático Infalible")
st.subheader("San Martín de los Andes")

if st.button('Generar Pronóstico de Consenso'):
    with st.spinner('Sincronizando modelos GFS, ECMWF e ICON...'):
        try:
            # Consulta a Open-Meteo (Datos de hoy)
            url = "https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35&hourly=temperature_2m,precipitation_probability,precipitation,cloudcover,windspeed_10m,windgusts_10m,snowfall,showers&models=ecmwf_ifs04,gfs_seamless,icon_seamless&timezone=America%23Argentina%2FBuenos_Aires&forecast_days=1"
            datos = requests.get(url).json()
            
            # Prompt optimizado con tu estructura requerida
            prompt = f"""Analiza estos datos meteorológicos de SMA: {datos}. 
            Genera un resumen siguiendo ESTRICTAMENTE este formato: 
            [Día de la semana] [Día] de [Mes] – San Martín de los Andes: [condiciones generales] con [cielo], y máxima esperada de [temperatura máxima] °C, mínima de [temperatura mínima] °C. Viento del [dirección del viento] entre [velocidad del viento] y [velocidad máxima del viento] km/h, [lluvias previstas]. 
            #SanMartínDeLosAndes #ClimaSMA #[Condición general 1] #[Condición general 2] #[Condición general 3]"""
            
            # Llamada al modelo
            response = model_ai.generate_content(prompt)
            
            if response.text:
                st.success("Análisis completado")
                st.info(response.text)
            else:
                st.warning("La IA no pudo procesar la respuesta, intenta de nuevo.")
                
        except Exception as e:
            st.error(f"Error técnico: {e}")
