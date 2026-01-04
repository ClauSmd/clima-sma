import streamlit as st
import requests
import time
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
                    return contenido.split("CHAPELCO_AERO")[1].split("=")[0].strip()
        return "❌ Chapelco Aero no encontrado."
    except Exception as e:
        return f"❌ Error SMN: {e}"

def obtener_datos_aic_sync():
    # Usamos la URL que tiene más éxito (la del ID directo)
    url = "https://www.aic.gob.ar/sitio/extendido-pdf?id_localidad=22&id_pronostico=1"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Accept': 'application/pdf'
    }
    
    # Intentamos hasta 2 veces por si el servidor está lento generando el PDF
    for intento in range(2):
        try:
            r = requests.get(url, headers=headers, verify=False, timeout=30)
            if r.status_code == 200 and len(r.content) > 1000:
                with pdfplumber.open(io.BytesIO(r.content)) as pdf:
                    return pdf.pages[0].extract_text()
            time.sleep(2) # Espera un poco antes del reintento
        except Exception as e:
            if intento == 1: return f"❌ Error AIC tras reintento: {e}"
            time.sleep(2)
    return "❌ Error: El servidor de AIC no entregó un PDF válido."

def obtener_satelital(fecha_inicio):
    start = fecha_inicio.strftime("%Y-%m-%d")
    end = (fecha_inicio + timedelta(days=5)).strftime("%Y-%m-%d")
    url = (f"https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35"
           f"&daily=temperature_2m_max,temperature_2m_min,windspeed_10m_max,windgusts_10m_max"
           f"&timezone=America%2FArgentina%2FBuenos_Aires&start_date={start}&end_date={end}")
    try:
        return requests.get(url, timeout=15).json()
    except Exception as e:
        return {"error": str(e)}

# --- INTERFAZ ---
st.title("🔍 Verificador de Datos SMA")
fecha_base = st.sidebar.date_input("Fecha de inicio", datetime.now())

if st.button("🧪 PROBAR TODAS LAS FUENTES"):
    with st.status("Solicitando datos...") as status:
        smn_res = obtener_datos_smn()
        aic_res = obtener_datos_aic_sync()
        sat_res = obtener_satelital(fecha_base)
        status.update(label="Sincronización completa", state="complete")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📡 SMN")
        if "❌" not in smn_res:
            st.success("OK")
            st.text_area("Datos:", smn_res, height=200)
        else: st.error(smn_res)
            
    with col2:
        st.subheader("📄 AIC")
        if "❌" not in aic_res:
            st.success("OK")
            st.text_area("Datos:", aic_res, height=200)
        else: st.error(aic_res)

    st.subheader("🌍 Modelos Satelitales")
    if "daily" in sat_res:
        st.success("OK")
        st.json(sat_res["daily"])
    else: st.error(f"Fallo Satélite: {sat_res}")
