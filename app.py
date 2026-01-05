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
    }
    .testigo-fuente { 
        font-size: 0.9rem; 
        color: #aaa; 
        margin-top: 25px; 
        padding: 20px;
        background-color: #121212;
        border-radius: 10px;
        border-left: 5px solid #4CAF50;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# 2. LÓGICA DE IA (GEMINI 3 - DOBLE MOTOR CON FALLBACK)
# ============================================================================
def llamar_ia_con_fallback(prompt):
    # Lista de motores prioritarios para 2026
    motores = [
        "models/gemini-3-flash",      # Motor Principal
        "models/gemini-3-flash-lite", # Respaldo veloz
        "models/gemini-2.0-flash",    # Estabilidad comprobada
        "models/gemini-1.5-flash"     # Legacy de seguridad
    ]
    
    ultimo_error = ""
    for motor in motores:
        try:
            model = genai.GenerativeModel(motor)
            response = model.generate_content(prompt)
            if response.text:
                return response.text, motor.replace("models/", "").upper()
        except Exception as e:
            ultimo_error = str(e)
            continue
            
    return f"❌ Error crítico: Ningún motor de IA respondió. Detalle: {ultimo_error}", "NINGUNO"

# ============================================================================
# 3. EXTRACCIÓN DE DATOS (AIC, SMN, OPEN-METEO)
# ============================================================================

def obtener_datos_aic():
    try:
        url = "https://www.aic.gob.ar/sitio/extendido-pdf?id_localidad=22&id_pronostico=1"
        headers = {'User-Agent': 'Mozilla/5.0'}
        session = requests.Session()
        session.get("https://www.aic.gob.ar", headers=headers, verify=False, timeout=10)
        r = session.get(url, headers=headers, verify=False, timeout=30)
        if r.content.startswith(b'%PDF'):
            with pdfplumber.open(io.BytesIO(r.content)) as pdf:
                return pdf.pages[0].extract_text(), True
        return None, False
    except: return None, False

def obtener_datos_smn():
    try:
        url = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=pron5d"
        r = requests.get(url, timeout=15)
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            nombre_txt = [f for f in z.namelist() if f.endswith('.txt')][0]
            with z.open(nombre_txt) as f:
                contenido = f.read().decode('utf-8', errors='ignore')
                if "CHAPELCO_AERO" in contenido:
                    return contenido.split("CHAPELCO_AERO")[1].split("=")[0].strip(), True
        return None, False
    except: return None, False

def obtener_datos_openmeteo():
    try:
        url = "https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35&daily=temperature_2m_max,temperature_2m_min,windspeed_10m_max,precipitation_sum&timezone=America%2FArgentina%2FBuenos_Aires"
        res = requests.get(url, timeout=15).json()
        return res, True
    except: return None, False

# ============================================================================
# 4. INTERFAZ (SIDEBAR Y DIAGNÓSTICO)
# ============================================================================
with st.sidebar:
    st.header("🏔️ Control SMA")
    fecha_base = st.date_input("Fecha Inicio", datetime.now())
    st.markdown("---")
    
    # BOTÓN DE DIAGNÓSTICO DE VERSIONES
    with st.expander("🛠️ Diagnóstico de IA"):
        if st.button("Ver modelos disponibles"):
            try:
                genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
                modelos_oficiales = genai.list_models()
                st.write("Modelos activos en tu cuenta:")
                for m in modelos_oficiales:
                    if 'generateContent' in m.supported_generation_methods:
                        st.code(m.name)
            except Exception as e:
                st.error(f"Error: {e}")
    
    st.markdown("---")
    st.caption("Ponderación: 40% Local | 60% Global")

# ============================================================================
# 5. EJECUCIÓN PRINCIPAL
# ============================================================================
st.title("🏔️ Generador de Síntesis Profesional")

if st.button("🚀 GENERAR REPORTE AHORA", type="primary", use_container_width=True):
    
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    except:
        st.error("❌ Falta GOOGLE_API_KEY en los Secrets de Streamlit.")
        st.stop()

    with st.status("Sincronizando fuentes y procesando...") as status:
        # Extracción
        datos_aic, aic_ok = obtener_datos_aic()
        datos_smn, smn_ok = obtener_datos_smn()
        datos_om, om_ok = obtener_datos_openmeteo()
        
        status.update(label="Fusión de datos con Gemini 3...", state="running")
        
        # Prompt Estructurado
        prompt = f"""
        FECHA: {fecha_base.strftime('%d/%m/%Y')}
        DATOS LOCALES (AIC/SMN): {datos_aic if aic_ok else 'No disp.'} | {datos_smn if smn_ok else 'No disp.'}
        DATOS SATELITALES: {datos_om if om_ok else 'No disp.'}

        TAREA: Generar síntesis de 6 días para San Martín de los Andes.
        PONDERACIÓN: 40% Local, 60% Global.
        FORMATO: [Día] [Día] de [Mes] – San Martín de los Andes: [condiciones] con [cielo], y máxima de [temp] °C, mínima de [temp] °C. Viento del [dir] entre [min] y [max] km/h, [lluvias].
        #[Lugar] #ClimaSMA #[Condición1] #[Condición2] #[Condición3]
        """

        sintesis, motor_ia = llamar_ia_con_fallback(prompt)
        status.update(label="✅ Reporte finalizado", state="complete")

    # SALIDA VISUAL
    st.markdown(f'<div class="reporte-final">{sintesis}</div>', unsafe_allow_html=True)

    # TESTIGO DE VERDAD
    st.markdown(f"""
    <div class="testigo-fuente">
        <strong>Testigo de Verdad:</strong><br>
        📡 AIC: {'✅ OK' if aic_ok else '❌ Falló'}<br>
        📡 SMN: {'✅ OK' if smn_ok else '❌ Falló'}<br>
        🌍 Modelos: Open-Meteo GFS/ECMWF<br>
        🧠 Motor IA: <b>{motor_ia}</b>
    </div>
    """, unsafe_allow_html=True)
