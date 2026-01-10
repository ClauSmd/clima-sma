import streamlit as st
import requests
import pdfplumber
import io
import json
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Weather Aggregator SMA", layout="wide")

# --- FUNCIONES DE EXTRACCIÓN ---

def get_aic_data():
    url = "https://www.aic.gob.ar/sitio/extendido-pdf?a=1029&z=1750130550"
    try:
        response = requests.get(url)
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            tabla = pdf.pages[0].extract_table({"vertical_strategy": "lines", "horizontal_strategy": "lines"})
            # Procesamos solo los primeros 5 días (10 columnas: día/noche)
            fechas = [f.replace("\n", "") for f in tabla[0] if f][0:10]
            cielos = [c.replace("\n", " ") for c in tabla[2][1:11]]
            temps = [float(t.replace(" ºC", "").strip()) for t in tabla[3][1:11]]
            return {"fuente": "AIC", "fechas": fechas, "cielos": cielos, "temps": temps, "status": "OK"}
    except:
        return {"fuente": "AIC", "status": "ERROR"}

def get_open_meteo_data():
    # Coordenadas San Martín de los Andes
    url = "https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35&daily=temperature_2m_max,temperature_2m_min,weathercode&timezone=America%2FArgentina%2FSalta&forecast_days=5"
    try:
        r = requests.get(url)
        data = r.json()
        return {"fuente": "Open-Meteo", "data": data["daily"], "status": "OK"}
    except:
        return {"fuente": "Open-Meteo", "status": "ERROR"}

# --- FUNCIÓN DE IA (OPENROUTER) ---

def consultar_ia_sintesis(prompt):
    api_key = st.secrets["OPENROUTER_API_KEY"]
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            data=json.dumps({
                "model": "google/gemini-2.0-flash-exp:free", # Modelo gratuito y potente
                "messages": [{"role": "user", "content": prompt}]
            })
        )
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"Error en IA: {e}"

# --- INTERFAZ STREAMLIT ---

st.sidebar.title("Fuentes de Datos")
usa_aic = st.sidebar.checkbox("AIC (Neuquén)", value=True)
usa_om = st.sidebar.checkbox("Open-Meteo", value=True)

st.title("Sistema de Pronóstico Ponderado - SMA")

if st.button("Generar Pronóstico Unificado"):
    datos_crudos = []
    
    # Recolección
    with st.spinner("Obteniendo datos..."):
        if usa_aic:
            res_aic = get_aic_data()
            datos_crudos.append(res_aic)
        if usa_om:
            res_om = get_open_meteo_data()
            datos_crudos.append(res_om)

    # Lógica de Ponderación (Prompt para la IA)
    # Le enviamos los datos a la IA indicando que Open-Meteo vale el 50%
    prompt_ia = f"""
    Actúa como un meteorólogo experto en San Martín de los Andes. 
    Analiza los siguientes datos de fuentes distintas: {json.dumps(datos_crudos)}.
    
    INSTRUCCIONES:
    1. Si hay más de una fuente, dales un peso del 50% a Open-Meteo y reparte el resto.
    2. Genera una SÍNTESIS NARRATIVA inicial (como el ejemplo de AIC).
    3. Luego genera el reporte diario para 5 días siguiendo exacto este formato:
       [Día de la semana] [Día] de [Mes] – San Martín de los Andes: [condiciones] con [cielo], máxima [temp]°C, mínima [temp]°C. Viento [dir] [vel] km/h. #Hashtags
    """

    # 1. RESULTADO PONDERADO (SÍNTESIS IA)
    st.subheader("☀️ Pronóstico Sintetizado (Ponderado)")
    resultado_ia = consultar_ia_sintesis(prompt_ia)
    st.markdown(resultado_ia)

    st.divider()

    # 2. DESGLOSE PARA COMPARAR
    st.subheader("📊 Desglose por Fuente")
    col1, col2 = st.columns(2)

    with col1:
        if usa_aic:
            st.info("AIC Datos Obtenidos")
            st.write(res_aic)
    
    with col2:
        if usa_om:
            st.success("Open-Meteo Datos Obtenidos")
            st.write(res_om)
