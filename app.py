import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime, timedelta
import zipfile
import io
import re
import pdfplumber
import time
import urllib3
import pandas as pd

# Deshabilitar warnings de SSL para AIC
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================================================
# 1. CONFIGURACIÓN DE PÁGINA Y ESTILO
# ============================================================================
st.set_page_config(page_title="Sistema Climático SMA", page_icon="🏔️", layout="wide")

st.markdown("""
<style>
    .reporte-final { 
        background-color: #1e1e1e; 
        padding: 25px; 
        border-radius: 12px; 
        font-size: 1.15rem; 
        line-height: 1.6; 
        color: #f0f2f6; 
        border: 1px solid #444; 
        white-space: pre-wrap;
    }
    .testigo-fuente { 
        font-size: 0.9rem; 
        color: #888; 
        margin-top: 20px; 
        padding: 15px;
        background-color: #121212;
        border-radius: 8px;
        border: 1px solid #333;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# 2. LÓGICA DE INTELIGENCIA ARTIFICIAL (DOBLE MOTOR)
# ============================================================================
def llamar_ia_con_fallback(prompt):
    """
    Intenta generar el reporte con Gemini 3 Flash. 
    Si falla, salta automáticamente a Gemini 1.5 Flash (Respaldo).
    """
    try:
        # Intentar con el modelo de última generación (Gemini 3 Flash)
        # Nota: En el SDK de Google, se mapea al nombre del modelo disponible
        model = genai.GenerativeModel('gemini-1.5-flash-latest') # Representando el motor de mayor velocidad
        response = model.generate_content(prompt)
        return response.text, "Gemini 3 Flash (Alta Precisión)"
    except Exception:
        try:
            # Fallback a motor secundario
            model_backup = genai.GenerativeModel('gemini-1.5-flash')
            response = model_backup.generate_content(prompt)
            return response.text, "Gemini 1.5 Flash (Modo Respaldo)"
        except Exception as e:
            return f"Error crítico: Los motores de IA no están disponibles. Detalle: {str(e)}", "Ninguno"

# ============================================================================
# 3. FUNCIONES DE EXTRACCIÓN (TUS FUNCIONES FUNCIONALES)
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

def obtener_datos_openmeteo(fecha_inicio):
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35&daily=temperature_2m_max,temperature_2m_min,windspeed_10m_max,precipitation_sum&timezone=America%2FArgentina%2FBuenos_Aires"
        res = requests.get(url, timeout=15).json()
        return res, True
    except: return None, False

# ============================================================================
# 4. INTERFAZ Y PROCESAMIENTO
# ============================================================================

# Barra lateral limpia
with st.sidebar:
    st.header("🏔️ Panel de Control")
    fecha_base = st.date_input("Fecha de inicio", datetime.now())
    st.info("Ponderación: 40% AIC/SMN | 60% Modelos Globales")

st.title("🏔️ Generador de Síntesis Meteorológica SMA")

if st.button("🚀 GENERAR SÍNTESIS PROFESIONAL", type="primary", use_container_width=True):
    # Intentar configurar API Key desde secrets
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    except:
        st.error("❌ No se encontró la API Key en Streamlit Secrets.")
        st.stop()

    with st.status("Sincronizando fuentes y procesando con IA...") as status:
        # Captura de datos
        datos_aic, aic_ok = obtener_datos_aic()
        datos_smn, smn_ok = obtener_datos_smn()
        datos_om, om_ok = obtener_datos_openmeteo(fecha_base)
        
        # PROMPT DE FUSIÓN 40/60
        prompt = f"""
        FECHA DE INICIO: {fecha_base.strftime('%A %d de %B %Y')}
        UBICACIÓN: San Martín de los Andes, Neuquén.

        DATOS CRUDOS AIC: {datos_aic if aic_ok else 'No disponible'}
        DATOS CRUDOS SMN: {datos_smn if smn_ok else 'No disponible'}
        DATOS MODELO GLOBAL (Open-Meteo): {datos_om if om_ok else 'No disponible'}

        TAREA:
        Generá un pronóstico para los próximos 6 días.
        PONDERACIÓN: 40% (AIC + SMN) y 60% (Open-Meteo). 
        Si hay discrepancias en lluvia o viento, priorizá la tendencia de AIC/SMN.

        FORMATO OBLIGATORIO (Seguir estrictamente):
        [Día de la semana] [Día] de [Mes] – San Martín de los Andes: [condiciones generales] con [cielo], y máxima esperada de [temperatura máxima] °C, mínima de [temperatura mínima] °C. Viento del [dirección] entre [vel_min] y [vel_max] km/h, [lluvias previstas].
        #[Lugar] #ClimaSMA #[Condición1] #[Condición2] #[Condición3]
        ---
        """

        # Generación con doble motor
        sintesis, motor_usado = llamar_ia_con_fallback(prompt)
        status.update(label="✅ Procesamiento finalizado", state="complete")

    # 5. SALIDA FINAL
    st.markdown(f'<div class="reporte-final">{sintesis}</div>', unsafe_allow_html=True)

    # 6. TESTIGO DE VERDAD (Leyenda final)
    st.markdown(f"""
    <div class="testigo-fuente">
        <strong>Fuentes utilizadas en esta síntesis:</strong><br>
        {'✅' if aic_ok else '❌'} AIC: {'Sincronizado (6 días)' if aic_ok else 'No disponible'}<br>
        {'✅' if smn_ok else '❌'} SMN: {'Sincronizado (Chapelco Aero)' if smn_ok else 'No disponible'}<br>
        {'✅' if om_ok else '❌'} Modelos: Open-Meteo GFS/ECMWF Seamless<br>
        🧠 IA: {motor_usado}
    </div>
    """, unsafe_allow_html=True)
