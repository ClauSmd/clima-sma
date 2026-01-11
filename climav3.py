import streamlit as st
import requests
import pdfplumber
import io
import json
import google.generativeai as genai
from datetime import datetime

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Weather Aggregator SMA", layout="wide")

# --- 2. FUNCIONES DE EXTRACCIÓN (ARRIBA PARA EVITAR NAMEERROR) ---

def get_aic_data():
    """Extrae datos del PDF de la AIC y captura la síntesis original"""
    url = "https://www.aic.gob.ar/sitio/extendido-pdf?a=1029&z=1750130550"
    try:
        response = requests.get(url, timeout=15)
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            pagina = pdf.pages[0]
            tabla = pagina.extract_table({"vertical_strategy": "lines", "horizontal_strategy": "lines"})
            
            fechas_fila = [f.replace("\n", "") for f in tabla[0] if f]
            cielos = [c.replace("\n", " ") for c in tabla[2][1:] if c]
            temps = [t.replace("\n", "").replace(" ºC", "").strip() for t in tabla[3][1:] if t]
            v_vel = [v.replace("\n", "").replace(" km/h", "").strip() for v in tabla[4][1:] if v]
            v_raf = [r.replace("\n", "").replace(" km/h", "").strip() for r in tabla[5][1:] if r]
            v_dir = [d.replace("\n", "") for d in tabla[6][1:] if d]
            
            texto = pagina.extract_text()
            sintesis = texto.split("hPa")[-1].split("www.aic.gob.ar")[0].strip() if "hPa" in texto else ""

            dias_dict = []
            # Guardamos cada bloque (Día y Noche) para procesarlos luego
            for i in range(len(cielos)):
                dias_dict.append({
                    "fecha": fechas_fila[i // 2] if (i // 2) < len(fechas_fila) else "S/D",
                    "cielo": cielos[i], 
                    "max": float(temps[i]), 
                    "min": float(temps[i]),
                    "viento": float(v_vel[i]), 
                    "rafaga": float(v_raf[i]), 
                    "dir": v_dir[i]
                })
            return {"status": "OK", "datos": dias_dict, "sintesis": sintesis}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

def get_open_meteo_data():
    """Extrae datos de la API de Open-Meteo"""
    url = "https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35&daily=temperature_2m_max,temperature_2m_min,windspeed_10m_max,windgusts_10m_max&timezone=America%2FArgentina%2FSalta&forecast_days=5"
    try:
        r = requests.get(url, timeout=15)
        d = r.json()["daily"]
        procesados = []
        for i in range(len(d["time"])):
            procesados.append({
                "fecha": d["time"][i], 
                "max": d["temperature_2m_max"][i],
                "min": d["temperature_2m_min"][i], 
                "viento": d["windspeed_10m_max"][i],
                "rafaga": d["windgusts_10m_max"][i]
            })
        return {"status": "OK", "datos": procesados}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

def consultar_ia_cascada(prompt):
    """Prioriza los modelos según tu acceso en AI Studio"""
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key: return None, "No API Key"
    genai.configure(api_key=api_key)
    
    # Orden de prioridad exacto solicitado
    modelos = ["gemini-3-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemma-3-27b"]
    
    for mod in modelos:
        try:
            model = genai.GenerativeModel(mod)
            response = model.generate_content(prompt)
            if response.text: return response.text, mod
        except:
            continue
    return None, "Error en todos los modelos"

# --- 3. INTERFAZ Y SIDEBAR ---
st.sidebar.title("Opciones")
usa_ia = st.sidebar.toggle("Activar Inteligencia Artificial", value=True)

st.title("🌤️ Weather Aggregator SMA")
st.markdown("---")

# --- 4. LÓGICA DE EJECUCIÓN ---
if st.button("🚀 GENERAR PRONÓSTICO"):
    with st.spinner("Analizando fuentes..."):
        d_aic = get_aic_data()
        d_om = get_open_meteo_data()

    if d_aic["status"] == "OK" and d_om["status"] == "OK":
        if usa_ia:
            prompt = f"Meteorólogo: Pondera 50/50. AIC: {json.dumps(d_aic['datos'])}. OM: {json.dumps(d_om['datos'])}. Sintesis: {d_aic['sintesis']}. Formato: [Día Semana] [Día] de [Mes] – San Martín de los Andes: [Condición] con [Cielo], máxima [Max] °C, mínima [Min] °C. Viento [Dir] [Vel]-[Raf] km/h. #SanMartínDeLosAndes #ClimaSMA"
            reporte, modelo_usado = consultar_ia_cascada(prompt)
            if reporte:
                st.success(f"Generado con {modelo_usado}")
                st.info(reporte)
            else:
                st.error("IA falló. Iniciando modo manual...")
                usa_ia = False

        if not usa_ia:
            # MODO MANUAL CON FECHAS EXACTAS
            meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
            dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            
            reporte_manual = ""
            for i in range(5):
                idx = i * 2 # Salto para evitar duplicados Día/Noche
                p_max = (d_aic['datos'][idx]['max'] + d_om['datos'][i]['max']) / 2
                p_min = (d_aic['datos'][idx]['min'] + d_om['datos'][i]['min']) / 2
                
                # Procesar fecha técnica a texto
                f_dt = datetime.strptime(d_aic['datos'][idx]['fecha'], "%d-%m-%Y")
                fecha_txt = f"{dias_semana[f_dt.weekday()]} {f_dt.day} de {meses[f_dt.month-1]}"
                
                linea = (f"**{fecha_txt} – San Martín de los Andes:** "
                         f"{d_aic['datos'][idx]['cielo']}, máxima {p_max:.1f} °C, mínima {p_min:.1f} °C. "
                         f"Viento {d_aic['datos'][idx]['dir']} a {d_aic['datos'][idx]['viento']} km/h. "
                         f"#SanMartínDeLosAndes #ClimaSMA\n\n")
                reporte_manual += linea
            
            reporte_manual += f"**SÍNTESIS DIARIA:**\n{d_aic['sintesis']}"
            st.info(reporte_manual)
            st.text_area("Copiar:", value=reporte_manual, height=350)
    else:
        st.error("Error al obtener datos.")
