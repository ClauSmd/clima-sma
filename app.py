import streamlit as st
import requests
import time
from datetime import datetime, timedelta
import zipfile
import io
import pdfplumber
import urllib3
import google.generativeai as genai

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 1. CONFIGURACIÓN DE PÁGINA Y API
st.set_page_config(page_title="Sintesis Climática SMA", page_icon="🏔️")

try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except:
    st.error("⚠️ Falta la GOOGLE_API_KEY en los Secrets de Streamlit.")

st.markdown("""
    <style>
    .reporte-final { background-color: #1e1e1e; padding: 25px; border-radius: 12px; font-size: 1.15rem; line-height: 1.6; color: #f0f2f6; border: 1px solid #444; white-space: pre-wrap; }
    </style>
    """, unsafe_allow_html=True)

# 2. FUNCIONES DE CAPTURA (Las que acabamos de validar)

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
        return None
    except: return None

def obtener_datos_aic_sync():
    url = "https://www.aic.gob.ar/sitio/extendido-pdf?id_localidad=22&id_pronostico=1"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    session = requests.Session()
    try:
        session.get("https://www.aic.gob.ar", headers=headers, verify=False, timeout=10)
        r = session.get(url, headers=headers, verify=False, timeout=30)
        if r.content.startswith(b'%PDF'):
            with pdfplumber.open(io.BytesIO(r.content)) as pdf:
                return pdf.pages[0].extract_text()
    except: return None
    return None

def obtener_satelital(fecha_inicio):
    start = fecha_inicio.strftime("%Y-%m-%d")
    end = (fecha_inicio + timedelta(days=5)).strftime("%Y-%m-%d")
    url = (f"https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35"
           f"&daily=temperature_2m_max,temperature_2m_min,windspeed_10m_max,windgusts_10m_max"
           f"&timezone=America%2FArgentina%2FBuenos_Aires&start_date={start}&end_date={end}")
    try:
        return requests.get(url, timeout=15).json()
    except: return None

# 3. INTERFAZ DE USUARIO
st.title("🏔️ Síntesis Climática SMA")
st.write("Generador de pronóstico profesional para San Martín de los Andes.")

fecha_base = st.sidebar.date_input("Fecha de inicio", datetime.now())

if st.button("🚀 GENERAR REPORTE AHORA"):
    with st.status("Sincronizando fuentes oficiales...") as status:
        smn = obtener_datos_smn()
        aic = obtener_datos_aic_sync()
        sat = obtener_satelital(fecha_base)
        status.update(label="Datos obtenidos. Redactando síntesis con Gemini IA...", state="running")

        # --- PROMPT PERSONALIZADO ---
        prompt = f"""
        FECHA: {fecha_base.strftime('%A %d de %B de %Y')}.
        DATOS AIC: {aic}
        DATOS SMN: {smn}
        DATOS SATELITALES: {sat}

        TAREA: Genera un pronóstico para San Martín de los Andes de los próximos 6 días.
        PONDERACIÓN: Dale 40% de importancia a AIC/SMN y 60% al modelo satelital.

        ESTRUCTURA OBLIGATORIA POR DÍA:
        [Día de la semana] [Día] de [Mes] – San Martín de los Andes: [condiciones generales] con [cielo], y máxima esperada de [temperatura máxima] °C, mínima de [temperatura mínima] °C. Viento del [dirección del viento] entre [velocidad] y [velocidad máxima] km/h, [lluvias previstas].
        #[Lugar] #ClimaSMA #[Condición1] #[Condición2] #[Condición3]
        --- (separador de línea)

        ESTILO:
        - Si hay viento > 40km/h menciona "Precaución por ráfagas".
        - Si la temperatura es baja, usa "condiciones de frío".
        - Si hay tormentas eléctricas (como indica AIC ahora), menciónalo claramente.
        """

        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            
            status.update(label="¡Reporte generado!", state="complete")
            
            st.markdown(f'<div class="reporte-final">{response.text}</div>', unsafe_allow_html=True)
            
            # Botón para copiar (opcional)
            st.button("📋 Copiar reporte", on_click=lambda: st.write("Copiado al portapapeles (Simulado)"))
            
        except Exception as e:
            st.error(f"Error en Gemini: {e}")

    # Mostrar estado de fuentes para tranquilidad del usuario
    with st.expander("Ver estado de las conexiones"):
        st.write(f"📡 SMN: {'✅ Conectado' if smn else '❌ Falló'}")
        st.write(f"📄 AIC: {'✅ Conectado' if aic else '❌ Falló'}")
        st.write(f"🌍 Satélite: {'✅ Conectado' if sat else '❌ Falló'}")
