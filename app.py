import streamlit as st
import requests
from datetime import datetime, timedelta
import zipfile
import io
import pdfplumber
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 1. Configuración de Estética
st.set_page_config(page_title="Debug de Fuentes SMA", page_icon="🔍")

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
                    # Recortamos solo el bloque de Chapelco
                    bloque = contenido.split("CHAPELCO_AERO")[1].split("=")[0]
                    return bloque.strip()
        return "❌ Chapelco Aero no encontrado en el ZIP."
    except Exception as e:
        return f"❌ Error SMN: {e}"

def obtener_datos_aic_sync():
    url = "https://www.aic.gob.ar/sitio/extendido-pdf?id_localidad=22&id_pronostico=1"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        r = requests.get(url, headers=headers, verify=False, timeout=30)
        if len(r.content) < 1000: return "❌ PDF de AIC muy pequeño o vacío."
        with pdfplumber.open(io.BytesIO(r.content)) as pdf:
            return pdf.pages[0].extract_text()
    except Exception as e:
        return f"❌ Error AIC: {e}"

def obtener_satelital(fecha_inicio):
    start = fecha_inicio.strftime("%Y-%m-%d")
    end = (fecha_inicio + timedelta(days=5)).strftime("%Y-%m-%d")
    url = (f"https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35"
           f"&daily=temperature_2m_max,temperature_2m_min,windspeed_10m_max,windgusts_10m_max"
           f"&timezone=America%2FArgentina%2FBuenos_Aires&start_date={start}&end_date={end}")
    try:
        return requests.get(url).json()
    except Exception as e:
        return {"error": str(e)}

# --- INTERFAZ DE PRUEBA ---
st.title("🔍 Verificador de Datos SMA")
st.info("Esta versión es para confirmar que todas las conexiones funcionan antes de activar la IA.")

fecha_base = st.sidebar.date_input("Fecha de inicio", datetime.now())

if st.button("🧪 PROBAR TODAS LAS FUENTES"):
    with st.status("Solicitando datos oficiales...") as status:
        
        # 1. SMN
        status.update(label="Consultando SMN (Chapelco Aero)...")
        smn_res = obtener_datos_smn()
        
        # 2. AIC
        status.update(label="Consultando AIC (PDF Extendido)...")
        aic_res = obtener_datos_aic_sync()
        
        # 3. Modelos
        status.update(label="Consultando Open-Meteo (Satelital)...")
        sat_res = obtener_satelital(fecha_base)
        
        status.update(label="¡Sincronización completa!", state="complete")

    # --- RESULTADOS ---
    
    # Fila 1: SMN y AIC
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📡 SMN (Txt Oficial)")
        if "❌" not in smn_res:
            st.success("Conexión Exitosa")
            st.text_area("Bloque Chapelco:", smn_res, height=250)
        else:
            st.error(smn_res)
            
    with col2:
        st.subheader("📄 AIC (PDF Texto)")
        if "❌" not in aic_res:
            st.success("Lectura Exitosa")
            st.text_area("Texto AIC:", aic_res, height=250)
        else:
            st.error(aic_res)

    # Fila 2: Satelital
    st.divider()
    st.subheader("🌍 Modelos Globales (JSON)")
    if "daily" in sat_res:
        st.success("API Satelital funcionando correctamente")
        st.json(sat_res["daily"])
    else:
        st.error(f"Fallo Satelital: {sat_res}")

    st.write("---")
    st.caption("Si ves texto en los dos cuadros de arriba y números en el JSON de abajo, estamos listos para encender la IA.")
