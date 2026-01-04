import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime, timedelta
import zipfile
import io
import pdfplumber
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 1. Configuración de Estética
st.set_page_config(page_title="Sintesis Climática SMA", page_icon="🏔️")

# 2. Configuración de API - DESCOMENTA ESTO PARA USAR LA IA
# genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

def obtener_datos_smn():
    url = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=pron5d"
    try:
        r = requests.get(url, timeout=15)
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            nombre_txt = [f for f in z.namelist() if f.endswith('.txt')][0]
            with z.open(nombre_txt) as f:
                return f.read().decode('utf-8', errors='ignore').split("CHAPELCO_AERO")[1].split("=")[0]
    except: return None

def obtener_datos_aic_sync():
    # CAMBIO CRÍTICO: Nueva URL con parámetros de sesión simulados
    url = "https://www.aic.gob.ar/sitio/extendido-pdf?id_localidad=22&id_pronostico=1"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        r = requests.get(url, headers=headers, verify=False, timeout=25)
        if len(r.content) < 500: # Si es muy chico, no es un PDF
            return "Error: El servidor de AIC entregó un archivo vacío o corrupto."
        
        with pdfplumber.open(io.BytesIO(r.content)) as pdf:
            return pdf.pages[0].extract_text()
    except Exception as e:
        return f"Error AIC: {e}"

def obtener_satelital(fecha_inicio):
    start = fecha_inicio.strftime("%Y-%m-%d")
    end = (fecha_inicio + timedelta(days=5)).strftime("%Y-%m-%d")
    url = (f"https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35"
           f"&daily=temperature_2m_max,temperature_2m_min,windspeed_10m_max,windgusts_10m_max"
           f"&timezone=America%2FArgentina%2FBuenos_Aires&start_date={start}&end_date={end}")
    return requests.get(url).json()

# --- INTERFAZ ---
st.title("🏔️ Síntesis Climática SMA")
fecha_base = st.sidebar.date_input("Fecha de inicio", datetime.now())

if st.button("🚀 Generar Reporte"):
    with st.status("Sincronizando fuentes locales...") as status:
        smn = obtener_datos_smn()
        aic = obtener_datos_aic_sync()
        sat = obtener_satelital(fecha_base)
        status.update(label="Datos obtenidos. Procesando...", state="complete")

    # MODO TEST: Si quieres ver los datos crudos antes de gastar IA
    st.expander("Ver datos crudos (Debug)").write({"SMN": smn, "AIC": aic, "SAT": sat})

    # --- BLOQUE DE IA (DESCOMENTAR CUANDO AIC DE 'OK') ---
    # prompt = f"FECHA: {fecha_base}. DATOS: AIC:{aic}, SMN:{smn}, SAT:{sat}. TAREA: Generar sintesis de 6 días estilo: 'Sábado 20 de Diciembre – San Martín de los Andes: tiempo estable...'"
    # model = genai.GenerativeModel('gemini-1.5-flash')
    # res = model.generate_content(prompt)
    # st.markdown(res.text)
