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
        font-family: 'Helvetica Neue', sans-serif;
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
# 2. LÓGICA DE INTELIGENCIA ARTIFICIAL (GEMINI 3 - DOBLE MOTOR)
# ============================================================================
def llamar_ia_con_fallback(prompt):
    """
    Intenta ejecutar la síntesis con la Generación 3 de Gemini.
    Si falla el modelo principal, rota automáticamente al modelo Lite.
    """
    motores = [
        "models/gemini-3-flash",      # Motor Principal solicitado
        "models/gemini-3-flash-lite", # Respaldo veloz
        "models/gemini-1.5-flash"     # Última instancia de seguridad
    ]
    
    ultimo_error = ""
    for motor in motores:
        try:
            model = genai.GenerativeModel(motor)
            # Configuración para evitar filtros innecesarios en clima
            response = model.generate_content(prompt)
            if response.text:
                return response.text, motor.replace("models/", "").upper()
        except Exception as e:
            ultimo_error = str(e)
            continue
            
    return f"❌ Error crítico de conexión con Gemini 3: {ultimo_error}", "NINGUNO"

# ============================================================================
# 3. FUNCIONES DE EXTRACCIÓN (MOTORES DE DATOS)
# ============================================================================

def obtener_datos_aic():
    try:
        # URL disparadora del pronóstico extendido
        url = "https://www.aic.gob.ar/sitio/extendido-pdf?id_localidad=22&id_pronostico=1"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
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
                    # Extraer solo el bloque relevante
                    return contenido.split("CHAPELCO_AERO")[1].split("=")[0].strip(), True
        return None, False
    except: return None, False

def obtener_datos_openmeteo(fecha):
    try:
        # Modelo global satelital
        url = (f"https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35"
               f"&daily=temperature_2m_max,temperature_2m_min,windspeed_10m_max,precipitation_sum"
               f"&timezone=America%2FArgentina%2FBuenos_Aires")
        res = requests.get(url, timeout=15).json()
        return res, True
    except: return None, False

# ============================================================================
# 4. INTERFAZ PRINCIPAL
# ============================================================================

# Barra lateral (Sidebar) limpia: Solo controles esenciales
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/869/869869.png", width=80)
    st.header("Configuración")
    fecha_base = st.date_input("Fecha del Reporte", datetime.now())
    st.markdown("---")
    st.write("**Lógica aplicada:**")
    st.write("🔹 40% AIC/SMN (Local)")
    st.write("🔹 60% Satelital (Global)")

st.title("🏔️ Generador de Síntesis Meteorológica SMA")
st.subheader("San Martín de los Andes, Neuquén")

if st.button("🚀 GENERAR PRONÓSTICO COMPLETO", type="primary", use_container_width=True):
    
    # 1. Configurar API
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    except:
        st.error("🔑 Error: No se encontró la API Key en Streamlit Secrets.")
        st.stop()

    with st.status("Sincronizando fuentes oficiales y modelos...") as status:
        # 2. Captura de datos en paralelo
        datos_aic, aic_ok = obtener_datos_aic()
        datos_smn, smn_ok = obtener_datos_smn()
        datos_om, om_ok = obtener_datos_openmeteo(fecha_base)
        
        status.update(label="Analizando datos con Gemini 3...", state="running")
        
        # 3. Prompt con tu Estructura de Memoria y Ponderación 40/60
        prompt = f"""
        FECHA DE REFERENCIA: {fecha_base.strftime('%A %d de %B de %Y')}
        LUGAR: San Martín de los Andes.

        FUENTES OFICIALES (PONDERACIÓN 40% - PRIORIDAD EN ALERTAS):
        - AIC (PDF Local): {datos_aic if aic_ok else 'SIN DATOS'}
        - SMN (Chapelco): {datos_smn if smn_ok else 'SIN DATOS'}

        MODELO GLOBAL (PONDERACIÓN 60% - TENDENCIA):
        - Open-Meteo: {datos_om if om_ok else 'SIN DATOS'}

        INSTRUCCIONES PARA LA SÍNTESIS:
        1. Generá el pronóstico para los próximos 6 días.
        2. Usá la ponderación 40/60: los datos locales (AIC/SMN) definen los fenómenos (lluvia, tormenta, ráfagas), el modelo global ajusta la curva de temperatura.
        3. Formato obligatorio por cada día (mantener hashtags):
        [Día de la semana] [Día] de [Mes] – San Martín de los Andes: [condiciones generales] con [cielo], y máxima esperada de [temperatura máxima] °C, mínima de [temperatura mínima] °C. Viento del [dirección] entre [vel_min] y [vel_max] km/h, [lluvias previstas].
        #[Lugar] #ClimaSMA #[Condición1] #[Condición2] #[Condición3]
        ---
        """

        # 4. Ejecución con Doble Motor
        sintesis, motor_ia = llamar_ia_con_fallback(prompt)
        status.update(label="✅ Síntesis generada", state="complete")

    # 5. RESULTADO FINAL (Pantalla principal)
    st.markdown(f'<div class="reporte-final">{sintesis}</div>', unsafe_allow_html=True)

    # 6. TESTIGO DE VERDAD (Leyenda de fuentes al final)
    st.markdown(f"""
    <div class="testigo-fuente">
        <strong>Fuentes utilizadas en esta síntesis:</strong><br>
        {'✅' if aic_ok else '❌'} <b>AIC:</b> {'Sincronizado' if aic_ok else 'No disponible'}<br>
        {'✅' if smn_ok else '❌'} <b>SMN:</b> {'Sincronizado (Chapelco Aero)' if smn_ok else 'No disponible'}<br>
        {'✅' if om_ok else '❌'} <b>Modelos:</b> Satelital GFS/ECMWF<br>
        🧠 <b>IA:</b> {motor_ia}
    </div>
    """, unsafe_allow_html=True)

# Información de pie de página
st.markdown("---")
st.caption(f"Sistema optimizado para Gemini 3 Flash | Versión 2026 | Última ejecución: {datetime.now().strftime('%H:%M:%S')}")
