import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime, timedelta
import zipfile
import io
import re

# 1. Configuración de Estética y Diseño Visual
st.set_page_config(page_title="Sintesis climatica sma", page_icon="🏔️", initial_sidebar_state="expanded")

# CSS para eliminar recuadros azules y mejorar legibilidad
st.markdown("""
    <style>
    .reporte-final { 
        background-color: transparent; 
        padding: 15px; 
        font-size: 1.1rem; 
        line-height: 1.6; 
        color: #f0f2f6; 
    }
    hr { margin: 1.5rem 0; border: 0; border-top: 1px solid #444; }
    .stSuccess { background-color: #155724; color: #d4edda; border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)

# 2. Configuración de Inteligencia (Gemini con Respaldo)
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except Exception as e:
    st.error(f"Error de configuración de API: {e}")

# --- FUNCIONES DE AUTOMATIZACIÓN Y PROCESAMIENTO ---

def obtener_datos_smn_zip():
    """Descarga y extrae el bloque de Chapelco Aero desde el ZIP del SMN."""
    url_zip = "https://ws.smn.gob.ar/export/pronostico-txt.zip"
    try:
        r = requests.get(url_zip, timeout=10)
        r.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            # Busca el archivo txt dentro del zip
            nombre_txt = [f for f in z.namelist() if f.endswith('.txt')][0]
            with z.open(nombre_txt) as f:
                contenido = f.read().decode('utf-8', errors='ignore')
                if "CHAPELCO_AERO" in contenido:
                    # Extrae solo la sección relevante
                    return contenido.split("CHAPELCO_AERO")[1].split("=")[0]
        return None
    except Exception as e:
        st.sidebar.error(f"Error descargando SMN: {e}")
        return None

def procesar_bloque_smn(bloque):
    """Convierte el texto del SMN en un diccionario de Máximas, Mínimas y Vientos."""
    if not bloque: return None
    dias_datos = {}
    lineas = bloque.strip().split('\n')
    for linea in lineas:
        # Regex para capturar: Día/Mes/Año, Temperatura y Viento (KM/H)
        match = re.search(r'(\d{2})/([A-Z]{3})/(\d{4})\s+(\d+)Hs\.\s+(\d+\.\d+)\s+(\d+)\s\|\s+(\d+)', linea)
        if match:
            fecha_key = f"{match.group(1)} {match.group(2)}"
            temp = float(match.group(5))
            viento = int(match.group(7))
            
            if fecha_key not in dias_datos:
                dias_datos[fecha_key] = {'t_max': temp, 't_min': temp, 'v_max': viento}
            else:
                dias_datos[fecha_key]['t_max'] = max(dias_datos[fecha_key]['t_max'], temp)
                dias_datos[fecha_key]['t_min'] = min(dias_datos[fecha_key]['t_min'], temp)
                dias_datos[fecha_key]['v_max'] = max(dias_datos[fecha_key]['v_max'], viento)
    return dias_datos

def ejecutar_sintesis(prompt):
    """Intenta generar contenido con Gemini 3 Flash y salta a 2.5 Flash Lite si falla."""
    modelos = ['gemini-3-flash-preview', 'gemini-2.5-flash-lite']
    for m in modelos:
        try:
            model_ai = genai.GenerativeModel(m)
            response = model_ai.generate_content(prompt)
            return response.text, m
        except Exception:
            continue
    return None, None

# --- INTERFAZ DE USUARIO ---

st.title("🏔️ Sintesis climatica sma V3.0")

# 3. Sidebar: Configuración y Referencias
st.sidebar.header("🗓️ Configuración")
fecha_base = st.sidebar.date_input("Fecha de inicio", datetime.now())

st.sidebar.divider()
st.sidebar.subheader("🔗 Calibración Local")
st.sidebar.info("El SMN Chapelco se sincroniza automáticamente vía ZIP.")

with st.sidebar.expander("📍 AIC (Autoridad Local)"):
    aic_t = st.text_input("AIC Temp (Máx/Mín)", placeholder="Ej: 28/10")
    aic_v = st.text_input("AIC Viento (Min/Max)", placeholder="Ej: 15/40")

with st.sidebar.expander("🌬️ Windguru"):
    wg_t = st.text_input("WG Temp", placeholder="Máx/Mín")
    wg_v = st.text_input("WG Viento/Ráfagas", placeholder="Ej: 20/55")

with st.sidebar.expander("☁️ AccuWeather"):
    accu_t = st.text_input("Accu Temp", placeholder="Máx/Mín")
    accu_v = st.text_input("Accu Viento", placeholder="Ej: 10/30")

# 4. Botón de Acción y Procesamiento
if st.button("Generar síntesis promediada"):
    with st.spinner("🧠 Sincronizando datos oficiales y procesando modelos..."):
        try:
            # A. Obtener y procesar datos del SMN (ZIP)
            bloque_smn = obtener_datos_smn_zip()
            smn_procesado = procesar_bloque_smn(bloque_smn)
            
            # Testigo visual de lectura exitosa
            if smn_procesado:
                st.success(f"✅ SMN Chapelco Sincronizado: {len(smn_procesado)} días detectados.")
                with st.expander("Ver datos técnicos extraídos"):
                    st.write(smn_procesado)
            else:
                st.warning("⚠️ No se pudo leer el archivo del SMN. Se usarán datos satelitales.")

            # B. Obtener datos satelitales (Open-Meteo)
            start_s = fecha_base.strftime("%Y-%m-%d")
            end_s = (fecha_base + timedelta(days=2)).strftime("%Y-%m-%d")
            url_sat = (f"https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35"
                       f"&hourly=temperature_2m,windspeed_10m,windgusts_10m,precipitation_probability"
                       f"&models=ecmwf_ifs04,gfs_seamless,icon_seamless&start_date={start_s}"
                       f"&end_date={end_s}&timezone=America%2FArgentina%2FBuenos_Aires")
            datos_sat = requests.get(url_sat).json()

            # C. Construcción del contexto de referencias manuales
            ref_list = []
            if aic_t or aic_v: ref_list.append(f"AIC: T({aic_t}) V({aic_v})")
            if wg_t or wg_v: ref_list.append(f"Windguru: T({wg_t}) V({wg_v})")
            if accu_t or accu_v: ref_list.append(f"Accu: T({accu_t}) V({accu_v})")
            contexto_manual = "\n".join(ref_list) if ref_list else "Sin datos manuales."

            # D. Prompt con Lógica de Fusión (Reglas 4 y 6)
            prompt = f"""
            ESTACIÓN: San Martín de los Andes.
            FECHA ACTUAL DE REFERENCIA: {fecha_base.strftime('%A %d de %B de %Y')}.
            
            DATOS TÉCNICOS SATELITALES: {datos_sat}
            DATOS PROCESADOS SMN (CHAPELCO): {smn_procesado}
            REFERENCIAS LOCALES MANUALES: {contexto_manual}

            TAREA:
            Genera un pronóstico para 3 días consecutivos. PROMEDIA la información disponible.
            PESO DE FUSIÓN: Satelitales 70% | SMN Chapelco 30%. Si hay datos de AIC o Windguru, úsalos para ajustar el promedio de viento.

            REGLAS DE FORMATO:
            [Emoji] [Día de la semana] [Día] de [Mes] – San Martín de los Andes: [condiciones generales] con [cielo], máxima de [max]°C, mínima de [min]°C. Viento del [dir] entre [vel. min] y [vel. max] km/h, [lluvias].
            [Emoji] ALERTA: [Solo si el promedio final de ráfagas supera 45km/h o la temperatura supera 30°C. De lo contrario, OMITE esta línea]
            #[Lugar] #ClimaSMA #[Condición1] #[Condición2] #[Condición3]
            
            Separa cada día con una línea horizontal (---).
            """

            # E. Ejecución y Salida
            resultado, modelo_usado = ejecutar_sintesis(prompt)
            
            if resultado:
                st.markdown(f'<div class="reporte-final">{resultado}</div>', unsafe_allow_html=True)
                st.divider()
                st.caption(f"Fusión Híbrida: Datos Satelitales + Sincronización Automática SMN. | Inteligencia: {modelo_usado.upper()}")
            else:
                st.warning("⚠️ Los servicios de IA están saturados. Reintentá en 60 segundos.")

        except Exception as e:
            st.error(f"Error técnico durante el procesamiento: {e}")

st.divider()
st.caption("Cerebro: Sistema de Respaldo Multi-Modelo | Integración SMN Chapelco Aero V3.0")
