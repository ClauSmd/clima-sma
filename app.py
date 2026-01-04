import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime, timedelta
import zipfile
import io
import pdfplumber
import urllib3

# Deshabilitar advertencias de certificados de la AIC
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 1. Configuración de Estética
st.set_page_config(page_title="Sintesis Climática SMA - TEST", page_icon="🏔️")

st.markdown("""
    <style>
    .reporte-final { background-color: #1e1e1e; padding: 20px; border-radius: 10px; font-size: 1.1rem; color: #f0f2f6; border: 1px solid #444; }
    .debug-box { background-color: #0e1117; padding: 10px; border: 1px solid #262730; border-radius: 5px; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# 2. Configuración de API (Comentada para no gastar)
# api_key = st.secrets["GOOGLE_API_KEY"]
# genai.configure(api_key=api_key)

# --- FUNCIONES DE SCRAPING ---

def obtener_datos_smn():
    url = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=pron5d"
    try:
        r = requests.get(url, timeout=15)
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            nombre_txt = [f for f in z.namelist() if f.endswith('.txt')][0]
            with z.open(nombre_txt) as f:
                contenido = f.read().decode('utf-8', errors='ignore')
                if "CHAPELCO_AERO" in contenido:
                    return contenido.split("CHAPELCO_AERO")[1].split("=")[0]
        return None
    except Exception as e:
        return f"Error SMN: {e}"

def obtener_datos_aic_sync():
    # URL para San Martín de los Andes
    url = "https://www.aic.gob.ar/sitio/extendido-pdf?id_localidad=22"
    try:
        r = requests.get(url, verify=False, timeout=20)
        if r.status_code == 200:
            with pdfplumber.open(io.BytesIO(r.content)) as pdf:
                return pdf.pages[0].extract_text()
        return "Error: Status code no es 200"
    except Exception as e:
        return f"Error AIC: {e}"

def obtener_satelital(fecha_inicio):
    start = fecha_inicio.strftime("%Y-%m-%d")
    end = (fecha_inicio + timedelta(days=5)).strftime("%Y-%m-%d")
    url = (f"https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35"
           f"&daily=temperature_2m_max,temperature_2m_min,windspeed_10m_max,windgusts_10m_max"
           f"&timezone=America%2FArgentina%2FBuenos_Aires&start_date={start}&end_date={end}")
    try:
        r = requests.get(url, timeout=15)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

# --- INTERFAZ ---

st.title("🏔️ Modo Test: Verificación de Fuentes")
st.info("Este modo NO consume créditos de Gemini. Solo verifica que San Martín de los Andes tenga datos disponibles.")

st.sidebar.header("🗓️ Configuración")
fecha_base = st.sidebar.date_input("Fecha de inicio", datetime.now())

if st.button("🚀 PROBAR CONEXIONES"):
    with st.status("Verificando cables...") as status:
        
        # 1. SMN
        status.update(label="Consultando SMN...")
        smn_data = obtener_datos_smn()
        
        # 2. AIC
        status.update(label="Consultando AIC...")
        aic_data = obtener_datos_aic_sync()
        
        # 3. Satelital
        status.update(label="Consultando Satélite...")
        sat_data = obtener_satelital(fecha_base)
        
        status.update(label="¡Prueba finalizada!", state="complete")

    # --- MOSTRAR RESULTADOS CRUDOS ---
    
    st.subheader("📊 Resultados de la Sincronización")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("### 📡 SMN (Chapelco Aero)")
        if smn_data and "Error" not in smn_data:
            st.success("✅ Datos recibidos")
            st.code(smn_data[:300] + "...", language="text")
        else:
            st.error(f"❌ Falló: {smn_data}")
            
    with col2:
        st.write("### 📄 AIC (PDF)")
        if aic_data and "Error" not in aic_data:
            st.success("✅ Texto extraído correctamente")
            st.text_area("Contenido AIC:", aic_data[:500] + "...", height=150)
        else:
            st.error(f"❌ Falló: {aic_data}")

    st.write("### 🌍 Open-Meteo (Satelital)")
    if "daily" in sat_data:
        st.success("✅ API Satelital respondiendo")
        st.json(sat_data["daily"])
    else:
        st.error(f"❌ Falló: {sat_data}")

    st.warning("⚠️ La IA está desactivada en este código para ahorrar créditos. Si ves los datos arriba, la App está lista para funcionar.")
