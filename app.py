import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime, timedelta
import zipfile
import io
import pdfplumber
import urllib3

# Deshabilitar advertencias de certificados (AIC usa uno viejo)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ... (Configuración estética y API Key igual a lo anterior) ...

def obtener_datos_smn():
    url = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=pron5d"
    try:
        r = requests.get(url, timeout=15)
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            nombre_txt = [f for f in z.namelist() if f.endswith('.txt')][0]
            with z.open(nombre_txt) as f:
                contenido = f.read().decode('utf-8', errors='ignore')
                return contenido.split("CHAPELCO_AERO")[1].split("=")[0]
    except Exception as e:
        st.sidebar.warning(f"SMN no disponible: {e}")
        return None

def obtener_datos_aic_sync():
    # URL exacta para San Martín de los Andes
    url = "https://www.aic.gob.ar/sitio/extendido-pdf?id_localidad=22"
    try:
        # Importante: verify=False para que no falle en el servidor de Streamlit
        r = requests.get(url, verify=False, timeout=20)
        if r.status_code == 200:
            with pdfplumber.open(io.BytesIO(r.content)) as pdf:
                return pdf.pages[0].extract_text()
        return None
    except Exception as e:
        st.sidebar.warning(f"AIC no disponible: {e}")
        return None

# --- BOTÓN DE GENERACIÓN CON LOGS ---
if st.button("Generar Reporte Automático"):
    progreso = st.status("🚀 Iniciando sincronización...")
    
    progreso.update(label="📡 Consultando SMN...")
    smn_raw = obtener_datos_smn()
    
    progreso.update(label="📄 Descargando PDF de AIC...")
    aic_raw = obtener_datos_aic_sync()
    
    progreso.update(label="🌍 Consultando Modelos Satelitales...")
    sat_raw = obtener_satelital(fecha_base)
    
    progreso.update(label="🧠 Gemini procesando síntesis...")
    
    # ... (Aquí va el resto del código del Prompt y ejecutar_sintesis igual al anterior) ...
    
    resultado, modelo_usado = ejecutar_sintesis(prompt)
    
    if resultado:
        progreso.update(label="✅ ¡Listo!", state="complete")
        st.markdown(f'<div class="reporte-final">{resultado}</div>', unsafe_allow_html=True)
    else:
        progreso.update(label="❌ Falló la IA", state="error")
        st.error("Gemini no pudo generar el texto. Revisa tu API Key en Secrets.")
