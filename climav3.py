import streamlit as st
import requests
import pdfplumber
import io
import json
import google.generativeai as genai
from datetime import datetime

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Weather Aggregator SMA", layout="wide")

# --- 2. DEFINICIÓN DE FUNCIONES (Deben ir ARRIBA para evitar NameError) ---

def get_aic_data():
    """Extrae datos del PDF de la AIC"""
    url = "https://www.aic.gob.ar/sitio/extendido-pdf?a=1029&z=1750130550"
    try:
        response = requests.get(url, timeout=15)
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            pagina = pdf.pages[0]
            tabla = pagina.extract_table({"vertical_strategy": "lines", "horizontal_strategy": "lines"})
            fechas_raw = [f.replace("\n", "") for f in tabla[0] if f]
            cielos = [c.replace("\n", " ") for c in tabla[2][1:] if c]
            temps = [t.replace("\n", "").replace(" ºC", "").strip() for t in tabla[3][1:] if t]
            v_vel = [v.replace("\n", "").replace(" km/h", "").strip() for v in tabla[4][1:] if v]
            v_raf = [r.replace("\n", "").replace(" km/h", "").strip() for r in tabla[5][1:] if r]
            v_dir = [d.replace("\n", "") for d in tabla[6][1:] if d]
            
            texto = pagina.extract_text()
            sintesis = texto.split("hPa")[-1].split("www.aic.gob.ar")[0].strip() if "hPa" in texto else ""

            dias_dict = []
            for i in range(0, min(10, len(cielos))):
                dias_dict.append({
                    "fecha": fechas_raw[i // 2] if (i // 2) < len(fechas_raw) else "S/D",
                    "momento": "Día" if i % 2 == 0 else "Noche",
                    "cielo": cielos[i],
                    "max": float(temps[i]),
                    "min": float(temps[i]), # En AIC cada celda es una temp
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
    """Lógica de prioridad Gemini solicitada"""
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key: return None, "Falta API Key"
    
    genai.configure(api_key=api_key)
    modelos = ["gemini-3-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemma-3-27b"]
    
    for mod_name in modelos:
        try:
            model = genai.GenerativeModel(mod_name)
            response = model.generate_content(prompt)
            if response.text: return response.text, mod_name
        except:
            continue # Salto por cuota RPM/RPD
    return None, "Error en todos los modelos"

# --- 3. INTERFAZ LATERAL ---
st.sidebar.title("Configuración")
usa_ia = st.sidebar.toggle("Activar Inteligencia Artificial", value=True)

# --- 4. EJECUCIÓN ---
st.title("🌤️ Weather Aggregator SMA")

if st.button("🚀 GENERAR REPORTE"):
    # Las funciones ya están cargadas en memoria antes de esta llamada
    d_aic = get_aic_data() 
    d_om = get_open_meteo_data()

    if d_aic["status"] == "OK" and d_om["status"] == "OK":
        if usa_ia:
            with st.spinner("IA en cascada analizando fuentes..."):
                prompt = f"Meteorólogo: Pondera 50/50 estos datos. AIC: {json.dumps(d_aic['datos'])}. OM: {json.dumps(d_om['datos'])}. Síntesis: {d_aic['sintesis']}. Formato: [Día] [Fecha] de [Mes] – San Martín de los Andes: [Condición]... #ClimaSMA"
                reporte, modelo = consultar_ia_cascada(prompt)
                if reporte:
                    st.success(f"Generado con {modelo}")
                    st.info(reporte)
                else:
                    usa_ia = False # Fallback a manual

        if not usa_ia:
            # Lógica manual sin duplicar días (salto de 2 en AIC)
            st.subheader("📍 Reporte Manual (Cálculo Directo)")
            resultado_man = ""
            for i in range(5):
                idx = i * 2
                p_max = (d_aic['datos'][idx]['max'] + d_om['datos'][i]['max']) / 2
                linea = f"Día {i+1}: {d_aic['datos'][idx]['cielo']}, Max: {p_max:.1f}°C. #ClimaSMA\n\n"
                resultado_man += linea
            st.info(resultado_man + f"\nSÍNTESIS: {d_aic['sintesis']}")
