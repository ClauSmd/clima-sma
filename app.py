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
    .reporte-final { background-color: transparent; padding: 10px; font-size: 1.1rem; line-height: 1.6; color: #f0f2f6; }
    hr { margin: 1.5rem 0; border: 0; border-top: 1px solid #444; }
    </style>
    """, unsafe_allow_html=True)

# 2. Configuración de Inteligencia
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except Exception as e:
    st.error(f"Error de API: {e}")

# --- FUNCIONES DE AUTOMATIZACIÓN SMN ---

def obtener_datos_smn_zip():
    # URL estática del pronóstico de 5 días en texto (ZIP)
    url_zip = "https://ws.smn.gob.ar/export/pronostico-txt.zip"
    try:
        r = requests.get(url_zip, timeout=10)
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            nombre = [f for f in z.namelist() if f.endswith('.txt')][0]
            with z.open(nombre) as f:
                contenido = f.read().decode('utf-8', errors='ignore')
                if "CHAPELCO_AERO" in contenido:
                    return contenido.split("CHAPELCO_AERO")[1].split("=")[0]
        return None
    except:
        return None

def procesar_bloque_smn(bloque):
    if not bloque: return "No se pudo obtener el dato oficial del SMN."
    dias = {}
    lineas = bloque.strip().split('\n')
    for linea in lineas:
        match = re.search(r'(\d{2})/([A-Z]{3})/(\d{4})\s+(\d+)Hs\.\s+(\d+\.\d+)\s+(\d+)\s\|\s+(\d+)', linea)
        if match:
            fecha_str = f"{match.group(1)}/{match.group(2)}"
            temp = float(match.group(5))
            viento = int(match.group(7))
            if fecha_str not in dias:
                dias[fecha_str] = {'max': temp, 'min': temp, 'viento_max': viento}
            else:
                dias[fecha_str]['max'] = max(dias[fecha_str]['max'], temp)
                dias[fecha_str]['min'] = min(dias[fecha_str]['min'], temp)
                dias[fecha_str]['viento_max'] = max(dias[fecha_str]['viento_max'], viento)
    return dias

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

# 3. Sidebar: Calibración Manual (SMN ELIMINADO POR AUTOMATIZACIÓN)
st.sidebar.header("🗓️ Configuración")
fecha_base = st.sidebar.date_input("Fecha de inicio", datetime.now())

st.sidebar.divider()
st.sidebar.subheader("🔗 Otras Referencias")
st.sidebar.caption("El SMN se sincroniza automáticamente al generar.")

with st.sidebar.expander("📍 AIC"):
    aic_t = st.text_input("AIC Temp (Máx/Mín)", key="at")
    aic_v = st.text_input("AIC Viento (Min/Max)", key="av")

with st.sidebar.expander("🌬️ Windguru"):
    wg_t = st.text_input("WG Temp", key="wt")
    wg_v = st.text_input("WG Viento/Ráfagas", key="wv")

with st.sidebar.expander("☁️ AccuWeather"):
    accu_t = st.text_input("Accu Temp", key="act")
    accu_v = st.text_input("Accu Viento", key="acv")

# 4. Procesamiento
if st.button("Generar síntesis promediada"):
    with st.spinner("🧠 Sincronizando SMN y cruzando modelos..."):
        try:
            # Sincronización automática SMN
            bloque_txt = obtener_datos_smn_zip()
            smn_info = procesar_bloque_smn(bloque_txt)
            
            # Datos Satelitales
            start_s = fecha_base.strftime("%Y-%m-%d")
            end_s = (fecha_base + timedelta(days=2)).strftime("%Y-%m-%d")
            url = (f"https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35"
                   f"&hourly=temperature_2m,windspeed_10m,windgusts_10m&models=ecmwf_ifs04,gfs_seamless"
                   f"&start_date={start_s}&end_date={end_s}&timezone=America%2FArgentina%2FBuenos_Aires")
            datos_sat = requests.get(url).json()

            # Referencias manuales restantes
            ref_list = []
            if aic_t or aic_v: ref_list.append(f"AIC: T({aic_t}) V({aic_v})")
            if wg_t or wg_v: ref_list.append(f"Windguru: T({wg_t}) V({wg_v})")
            if accu_t or accu_v: ref_list.append(f"Accu: T({accu_t}) V({accu_v})")
            contexto_manual = "\n".join(ref_list) if ref_list else "Sin datos adicionales."

            prompt = f"""
            ESTACIÓN: San Martín de los Andes.
            FECHA: {fecha_base.strftime('%A %d de %B %Y')}.
            
            DATOS SATELITALES: {datos_sat}
            DATOS OFICIALES SMN (Chapelco Aero): {smn_info}
            OTRAS REFERENCIAS: {contexto_manual}

            TAREA: Genera el pronóstico para 3 días promediando toda la información. 
            IMPORTANTE: Los Datos Oficiales SMN tienen prioridad 30% sobre el satélite.
            
            FORMATO:
            [Emoji] [Día] de [Mes] – San Martín de los Andes: [condiciones], máxima de [max]°C, mínima de [min]°C. Viento del [dir] entre [min] y [max] km/h.
            [Emoji] ALERTA: [Solo si ráfagas >45km/h o calor >30°C]
            #[Lugar] #ClimaSMA #[Tags]
            ---
            """

            resultado, modelo_usado = ejecutar_sintesis(prompt)
            if resultado:
                st.markdown(f'<div class="reporte-final">{resultado}</div>', unsafe_allow_html=True)
                st.caption(f"Sincronización automática SMN Exitosa | Motor: {modelo_usado.upper()}")
                
        except Exception as e:
            st.error(f"Error técnico: {e}")
