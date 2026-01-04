import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime, timedelta
import zipfile
import io
import re
import pdfplumber
import httpx
import asyncio

# 1. Configuración de Estética
st.set_page_config(page_title="Sintesis Climática SMA", page_icon="🏔️")

st.markdown("""
    <style>
    .reporte-final { background-color: #1e1e1e; padding: 20px; border-radius: 10px; font-size: 1.1rem; color: #f0f2f6; border: 1px solid #444; }
    </style>
    """, unsafe_allow_html=True)

# 2. Configuración de API
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# --- FUNCIONES DE SCRAPING ---

def obtener_datos_smn():
    url = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=pron5d"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            nombre_txt = [f for f in z.namelist() if f.endswith('.txt')][0]
            with z.open(nombre_txt) as f:
                contenido = f.read().decode('utf-8', errors='ignore')
                if "CHAPELCO_AERO" in contenido:
                    bloque = contenido.split("CHAPELCO_AERO")[1].split("=")[0]
                    return bloque
        return None
    except: return None

def obtener_datos_aic_sync():
    """Versión adaptada de tu código funcional para Streamlit"""
    url = "https://www.aic.gob.ar/sitio/extendido-pdf?id_localidad=22"
    try:
        r = requests.get(url, verify=False, timeout=15)
        with pdfplumber.open(io.BytesIO(r.content)) as pdf:
            return pdf.pages[0].extract_text()
    except: return None

def obtener_satelital(fecha_inicio):
    start = fecha_inicio.strftime("%Y-%m-%d")
    end = (fecha_inicio + timedelta(days=5)).strftime("%Y-%m-%d")
    url = (f"https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35"
           f"&daily=temperature_2m_max,temperature_2m_min,windspeed_10m_max,windgusts_10m_max"
           f"&timezone=America%2FArgentina%2FBuenos_Aires&start_date={start}&end_date={end}")
    return requests.get(url).json()

# --- NÚCLEO DE INTELIGENCIA ---

def ejecutar_sintesis(prompt):
    modelos = ['gemini-1.5-flash', 'gemini-1.5-pro']
    for m in modelos:
        try:
            model = genai.GenerativeModel(m)
            response = model.generate_content(prompt)
            return response.text, m
        except: continue
    return None, None

# --- INTERFAZ ---

st.title("🏔️ Síntesis Climática SMA V3.5")
st.sidebar.header("🗓️ Control de Fecha")
fecha_base = st.sidebar.date_input("Fecha de inicio", datetime.now())

if st.button("Generar Reporte Automático (6 Días)"):
    with st.spinner("🧠 Sincronizando SMN, AIC y Modelos Satelitales..."):
        
        # Ejecución de Scraping
        smn_raw = obtener_datos_smn()
        aic_raw = obtener_datos_aic_sync()
        sat_raw = obtener_satelital(fecha_base)
        
        # Construcción del Prompt con tus ejemplos
        prompt = f"""
        SOS UN METEORÓLOGO EXPERTO EN SAN MARTÍN DE LOS ANDES.
        TU TAREA: Generar un pronóstico de 6 DÍAS empezando el {fecha_base}.

        REGLA DE ORO (FUSIÓN 40/60): 
        - Da un 40% de peso a las fuentes oficiales (SMN y AIC).
        - Da un 60% de peso a los modelos satelitales.
        - Si una fuente oficial falta, la otra toma su lugar en el 40%.

        DATOS CRUDOS:
        - AIC: {aic_raw if aic_raw else 'No disponible'}
        - SMN (Chapelco): {smn_raw if smn_raw else 'No disponible'}
        - SATELITAL: {sat_raw}

        ESTILO DE REDACCIÓN (Sigue este tono):
        "Sábado 20 de Diciembre – San Martín de los Andes: tiempo estable y agradable con cielo despejado, máxima de 24°C, mínima de 8°C. Viento del Oeste entre 20 y 45 km/h."
        "Lunes 23 de Junio – San Martín de los Andes: condiciones de frío extremo con cielo parcialmente nublado, máxima de 4°C, mínima de -5°C."

        FORMATO POR CADA DÍA:
        [Día de la semana] [Día] de [Mes] – San Martín de los Andes: [Descripción rica de condiciones], máxima de [X] °C, mínima de [Y] °C. Viento del [Dir] entre [min] y [max] km/h, [probabilidad de lluvias]. 
        #[Lugar] #ClimaSMA #[Condicion1] #[Condicion2]
        --- (separador entre días)

        IMPORTANTE: Si hay ráfagas >45km/h o nieve/tormentas, agrega una línea de ⚠️ ALERTA al final de ese día.
        """

        resultado, modelo_usado = ejecutar_sintesis(prompt)
        
        if resultado:
            st.markdown(f'<div class="reporte-final">{resultado}</div>', unsafe_allow_html=True)
            
            # Diagnóstico de Fuentes (Testigo de Verdad)
            st.divider()
            cols = st.columns(3)
            cols[0].write(f"📡 **SMN:** {'✅ OK' if smn_raw else '❌ Caído'}")
            cols[1].write(f"📄 **AIC:** {'✅ OK' if aic_raw else '❌ Caído'}")
            cols[2].write(f"🤖 **IA:** {modelo_usado.upper()}")
            
            st.caption(f"Reporte generado para 6 días partiendo del {fecha_base.strftime('%d/%m/%Y')}")
