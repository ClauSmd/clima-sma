import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime, timedelta
import zipfile
import io
import re
import pdfplumber
import urllib3
import pandas as pd
import logging
from bs4 import BeautifulSoup

# Configurar logging para debug
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Deshabilitar warnings de SSL para AIC
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================================================
# 1. CONFIGURACIÓN DE PÁGINA Y ESTILO
# ============================================================================
st.set_page_config(page_title="Sistema Climático SMA v2026", page_icon="🏔️", layout="wide")

st.markdown("""
<style>
    .reporte-final { 
        background-color: #1e1e1e; 
        padding: 30px; 
        border-radius: 15px; 
        font-size: 1.15rem; 
        line-height: 1.7; 
        color: #f0f2f6; 
        border: 1px solid #444; 
        white-space: pre-wrap;
        font-family: 'Helvetica Neue', sans-serif;
    }
    .raw-data-box {
        background-color: #0e1117;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #333;
        font-family: monospace;
        font-size: 0.85rem;
        height: 300px;
        overflow-y: auto;
        white-space: pre-wrap;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# 2. LÓGICA DE INTELIGENCIA ARTIFICIAL
# ============================================================================
def llamar_ia_con_fallback(prompt):
    motores = [
        "models/gemini-3-flash", 
        "models/gemini-3-pro",
        "models/gemini-2.0-flash",
        "models/gemini-1.5-flash"
    ]
    
    for motor in motores:
        try:
            model = genai.GenerativeModel(motor)
            response = model.generate_content(prompt)
            if response.text:
                return response.text, motor.replace("models/", "").upper()
        except:
            continue
                
    return "❌ Error: Ningún motor de IA pudo procesar la solicitud.", "NINGUNO"

# ============================================================================
# 3. EXTRACCIÓN DE DATOS
# ============================================================================

def obtener_datos_aic():
    try:
        url = "https://www.aic.gob.ar/sitio/extendido-pdf?id_localidad=22&id_pronostico=1"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, verify=False, timeout=25)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            texto = soup.get_text(separator=' ', strip=True)
            return texto[:3000], True, f"HTML/PDF leído ({len(texto)} chars)"
        return "Error HTTP", False, str(response.status_code)
    except Exception as e:
        return str(e), False, "Error de conexión"

def obtener_datos_smn():
    try:
        url = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=pron5d"
        r = requests.get(url, timeout=20)
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            archivo_txt = [f for f in z.namelist() if f.endswith('.txt')][0]
            with z.open(archivo_txt) as f:
                contenido = f.read().decode('utf-8', errors='ignore')
                if "CHAPELCO_AERO" in contenido:
                    bloque = contenido.split("CHAPELCO_AERO")[1].split("=")[0].strip()
                    return bloque, True, "Chapelco Aero OK"
        return "No encontrado", False, "Filtro fallido"
    except Exception as e:
        return str(e), False, "Error ZIP"

def obtener_datos_openmeteo():
    try:
        # Forzado de zona horaria local para evitar salto de día
        url = "https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35&daily=temperature_2m_max,temperature_2m_min,windspeed_10m_max,precipitation_sum&timezone=America%2FArgentina%2FBuenos_Aires"
        res = requests.get(url, timeout=15).json()
        return res, True, "API Global OK"
    except Exception as e:
        return None, False, str(e)

# ============================================================================
# 4. INTERFAZ Y PROCESAMIENTO
# ============================================================================

with st.sidebar:
    st.header("⚙️ Configuración")
    fecha_base = st.date_input("Fecha Base", datetime.now())
    st.markdown("---")
    st.info("Ponderación: 40% AIC/SMN | 60% Satelital")

st.title("🏔️ Sistema Meteorológico SMA")

if st.button("🚀 GENERAR PRONÓSTICO AVANZADO", type="primary", use_container_width=True):
    
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    except:
        st.error("API Key no configurada en Secrets.")
        st.stop()
    
    with st.status("Analizando fuentes y cruzando datos...") as status:
        datos_aic, aic_ok, debug_aic = obtener_datos_aic()
        datos_smn, smn_ok, debug_smn = obtener_datos_smn()
        datos_om, om_ok, debug_om = obtener_datos_openmeteo()
        
        # PROMPT MEJORADO PARA FORZAR INICIO HOY
        prompt = f"""
        FECHA DE REFERENCIA: {fecha_base.strftime('%A %d de %B de %Y')}
        UBICACIÓN: San Martín de los Andes, Neuquén.

        DATOS CRUDOS AIC: {datos_aic if aic_ok else 'No disp.'}
        DATOS CRUDOS SMN: {datos_smn if smn_ok else 'No disp.'}
        DATOS CRUDOS SATELITALES: {datos_om if om_ok else 'No disp.'}

        INSTRUCCIONES CRÍTICAS:
        1. Generar pronóstico para 6 días EMPEZANDO DESDE HOY {fecha_base.strftime('%d/%m')}.
        2. Seguir estrictamente este formato: [Día de la semana] [Día] de [Mes] – San Martín de los Andes: [condiciones] con [cielo], y máxima esperada de [temp] °C, mínima de [temp] °C. Viento del [dir] entre [min] y [max] km/h, [lluvias].
        3. Usar los hashtags solicitados: #SanMartínDeLosAndes #ClimaSMA #[Condicion]
        4. Aplicar ponderación 40/60.
        """

        sintesis, motor_ia = llamar_ia_con_fallback(prompt)
        status.update(label="✅ Análisis Meteorológico Completo", state="complete")

    # --- NUEVA SECCIÓN DE AUDITORÍA ---
    st.markdown("### 🔍 Auditoría de Datos Extraídos")
    st.info("Revisa aquí abajo qué información real se envió a la IA para el análisis.")
    tab1, tab2, tab3 = st.tabs(["📡 Datos AIC (Neuquén)", "🏔️ Datos SMN (Chapelco)", "🛰️ Datos Globales (JSON)"])
    
    with tab1:
        st.markdown(f'<div class="raw-data-box">{datos_aic}</div>', unsafe_allow_html=True)
    with tab2:
        st.markdown(f'<div class="raw-data-box">{datos_smn}</div>', unsafe_allow_html=True)
    with tab3:
        st.json(datos_om)

    # --- RESULTADO FINAL ---
    st.markdown("---")
    st.markdown("### 📋 PRONÓSTICO GENERADO")
    st.markdown(f'<div class="reporte-final">{sintesis}</div>', unsafe_allow_html=True)

    # Panel de métricas rápidas
    col1, col2, col3 = st.columns(3)
    col1.metric("AIC", "ONLINE" if aic_ok else "OFFLINE", debug_aic)
    col2.metric("SMN", "ONLINE" if smn_ok else "OFFLINE", debug_smn)
    col3.metric("Motor IA", motor_ia)
