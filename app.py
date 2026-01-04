import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime, timedelta
import zipfile
import io
import re

# 1. Configuración de Estética y Diseño Visual
st.set_page_config(page_title="Sintesis climatica sma", page_icon="🏔️", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .reporte-final { background-color: transparent; padding: 15px; font-size: 1.1rem; line-height: 1.6; color: #f0f2f6; }
    hr { margin: 1.5rem 0; border: 0; border-top: 1px solid #444; }
    </style>
    """, unsafe_allow_html=True)

# 2. Configuración de Inteligencia
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except Exception as e:
    st.error(f"Error de API: {e}")

# --- FUNCIONES DE AUTOMATIZACIÓN SMN (PROBADAS) ---

def obtener_datos_smn_zip():
    # URL Oficial confirmada
    url = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=pron5d"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            nombre_txt = [f for f in z.namelist() if f.endswith('.txt')][0]
            with z.open(nombre_txt) as f:
                contenido = f.read().decode('utf-8', errors='ignore')
                if "CHAPELCO_AERO" in contenido:
                    # Extraemos el bloque de Chapelco
                    return contenido.split("CHAPELCO_AERO")[1].split("=")[0]
        return None
    except:
        return None

def procesar_bloque_smn(bloque):
    if not bloque: return None
    dias_datos = {}
    lineas = bloque.strip().split('\n')
    for linea in lineas:
        # Regex para capturar Fecha, Temp y Viento (según el formato que vimos en el test)
        match = re.search(r'(\d{2})/([A-Z]{3})/(\d{4}).*?(\d+\.\d+).*?\|.*?(\d+)', linea)
        if match:
            fecha_key = f"{match.group(1)} {match.group(2)}"
            temp = float(match.group(4))
            viento = int(match.group(5))
            if fecha_key not in dias_datos:
                dias_datos[fecha_key] = {'t_max': temp, 't_min': temp, 'v_max': viento}
            else:
                dias_datos[fecha_key]['t_max'] = max(dias_datos[fecha_key]['t_max'], temp)
                dias_datos[fecha_key]['t_min'] = min(dias_datos[fecha_key]['t_min'], temp)
                dias_datos[fecha_key]['v_max'] = max(dias_datos[fecha_key]['v_max'], viento)
    return dias_datos

def ejecutar_sintesis(prompt):
    modelos = ['gemini-3-flash-preview', 'gemini-2.5-flash-lite']
    for m in modelos:
        try:
            model_ai = genai.GenerativeModel(m)
            response = model_ai.generate_content(prompt)
            return response.text, m
        except: continue
    return None, None

# --- INTERFAZ ---

st.title("🏔️ Sintesis climatica sma V3.0")

st.sidebar.header("🗓️ Configuración")
fecha_base = st.sidebar.date_input("Fecha de inicio", datetime.now())

st.sidebar.divider()
st.sidebar.subheader("🔗 Calibración Local")
st.sidebar.info("✅ SMN Chapelco se sincroniza automáticamente.")

with st.sidebar.expander("📍 AIC / Windguru / Accu"):
    aic_t = st.text_input("AIC Temp (Máx/Mín)")
    aic_v = st.text_input("AIC Viento (Min/Max)")
    wg_v = st.text_input("Windguru Viento")

if st.button("Generar síntesis promediada"):
    with st.spinner("🧠 Sincronizando SMN y cruzando modelos..."):
        try:
            # 1. Obtener SMN Automático
            bloque_smn = obtener_datos_smn_zip()
            smn_info = procesar_bloque_smn(bloque_smn)
            
            if smn_info:
                st.success(f"✅ SMN Chapelco Sincronizado ({len(smn_info)} días)")
            
            # 2. Obtener Satelitales
            start_s = fecha_base.strftime("%Y-%m-%d")
            end_s = (fecha_base + timedelta(days=2)).strftime("%Y-%m-%d")
            url_sat = (f"https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35"
                       f"&hourly=temperature_2m,windspeed_10m,windgusts_10m&models=ecmwf_ifs04,gfs_seamless"
                       f"&start_date={start_s}&end_date={end_s}&timezone=America%2FArgentina%2FBuenos_Aires")
            datos_sat = requests.get(url_sat).json()

            # 3. Prompt de Fusión
            prompt = f"""
            ESTACIÓN: San Martín de los Andes.
            FECHA: {fecha_base.strftime('%A %d de %B %Y')}.
            DATOS SATELITALES: {datos_sat}
            DATOS OFICIALES SMN (Chapelco): {smn_info}
            REFERENCIAS LOCALES: AIC:{aic_t}/{aic_v}, WG:{wg_v}

            TAREA: Genera pronóstico de 3 días.
            REGLA: Promedia satélite y SMN (prioridad SMN 30%). 
            No inventes valores. Si el SMN dice 30.9°C el día 04, respétalo.

            FORMATO:
            [Emoji] [Día] de [Mes] – San Martín de los Andes: [condiciones], máxima de [max]°C, mínima de [min]°C. Viento entre [min] y [max] km/h.
            [Emoji] ALERTA: [Solo si ráfagas >45km/h o calor >30°C]
            #[Lugar] #ClimaSMA #[Tags]
            ---
            """

            resultado, modelo_usado = ejecutar_sintesis(prompt)
            if resultado:
                st.markdown(f'<div class="reporte-final">{resultado}</div>', unsafe_allow_html=True)
                st.caption(f"Motor: {modelo_usado.upper()} | Datos: Satelital + SMN Chapelco")
                
        except Exception as e:
            st.error(f"Error técnico: {e}")
