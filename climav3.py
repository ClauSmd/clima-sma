import streamlit as st
import requests
import pdfplumber
import io
import json
import google.generativeai as genai
from datetime import datetime, timedelta

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Weather Aggregator SMA", layout="wide")

MODELOS_DISPONIBLES = [
    "gemini-3-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite", 
    "gemma-3-27b", "gemini-2.5-flash-native-audio-dialog"
]

# --- 2. FUNCIONES DE EXTRACCIÓN ---

def get_aic_data():
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
            for i in range(len(cielos)):
                # Convertimos la fecha del PDF (DD-MM-YYYY) a objeto date para filtrar
                f_str = fechas_fila[i // 2]
                f_obj = datetime.strptime(f_str, "%d-%m-%Y").date()
                dias_dict.append({
                    "fecha_obj": f_obj, "fecha_str": f_str, "cielo": cielos[i], 
                    "max": float(temps[i]), "min": float(temps[i]),
                    "viento": float(v_vel[i]), "rafaga": float(v_raf[i]), "dir": v_dir[i]
                })
            return {"status": "OK", "datos": dias_dict, "sintesis": sintesis}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

def get_open_meteo_data():
    url = "https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35&daily=temperature_2m_max,temperature_2m_min,windspeed_10m_max,windgusts_10m_max&timezone=America%2FArgentina%2FSalta&forecast_days=10"
    try:
        r = requests.get(url, timeout=15)
        d = r.json()["daily"]
        procesados = []
        for i in range(len(d["time"])):
            procesados.append({
                "fecha_obj": datetime.strptime(d["time"][i], "%Y-%m-%d").date(),
                "max": d["temperature_2m_max"][i], "min": d["temperature_2m_min"][i],
                "viento": d["windspeed_10m_max"][i], "rafaga": d["windgusts_10m_max"][i]
            })
        return {"status": "OK", "datos": procesados}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

def consultar_ia_cascada(prompt):
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key: return None, "Falta API Key"
    genai.configure(api_key=api_key)
    for mod in MODELOS_DISPONIBLES:
        try:
            model = genai.GenerativeModel(mod)
            response = model.generate_content(prompt)
            if response.text: return response.text, mod
        except: continue
    return None, "Error en IA"

# --- 3. INTERFAZ ---
st.sidebar.title("Configuración")
fecha_inicio = st.sidebar.date_input("Fecha de inicio del reporte", datetime.now().date())
usa_ia = st.sidebar.toggle("Activar Inteligencia Artificial", value=True)

st.title("🌤️ Weather Aggregator SMA")

if st.button("🚀 GENERAR PRONÓSTICO"):
    with st.spinner("Obteniendo datos..."):
        d_aic = get_aic_data()
        d_om = get_open_meteo_data()

    if d_aic["status"] == "OK" and d_om["status"] == "OK":
        # FILTRADO: Solo tomamos días desde la fecha seleccionada
        datos_aic_filtrados = [d for d in d_aic["datos"] if d["fecha_obj"] >= fecha_inicio]
        datos_om_filtrados = [d for d in d_om["datos"] if d["fecha_obj"] >= fecha_inicio]

        # Determinamos cuántos días podemos procesar (el mínimo común entre fuentes)
        # AIC tiene 2 registros por día (Día/Noche), OpenMeteo tiene 1.
        dias_disponibles = min(len(datos_aic_filtrados) // 2, len(datos_om_filtrados))
        
        if dias_disponibles == 0:
            st.error("No hay datos disponibles para la fecha seleccionada en las fuentes.")
        else:
            # Recortamos los datos para que coincidan en cantidad de días
            datos_ia_aic = datos_aic_filtrados[:dias_disponibles * 2]
            datos_ia_om = datos_om_filtrados[:dias_disponibles]

            if usa_ia:
                with st.spinner(f"IA procesando {dias_disponibles} días..."):
                    prompt = f"Meteorólogo: Pondera 50/50. Datos: AIC={json.dumps(datos_ia_aic, default=str)}, OM={json.dumps(datos_ia_om, default=str)}. Síntesis: {d_aic['sintesis']}. FORMATO: [Día Semana] [Día] de [Mes] – San Martín de los Andes: [Condición] con [Cielo], máxima [Max] °C, mínima [Min] °C. #SanMartínDeLosAndes"
                    reporte, modelo = consultar_ia_cascada(prompt)
                    if reporte:
                        st.success(f"Generado con {modelo}")
                        st.info(reporte)
                    else:
                        st.error("Fallo IA, use modo manual.")
            else:
                # REPORTE MANUAL CON FECHAS DINÁMICAS
                meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
                dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
                reporte_manual = ""
                for i in range(dias_disponibles):
                    idx = i * 2
                    p_max = (datos_ia_aic[idx]['max'] + datos_ia_om[i]['max']) / 2
                    f_dt = datos_ia_aic[idx]['fecha_obj']
                    fecha_txt = f"{dias_semana[f_dt.weekday()]} {f_dt.day} de {meses[f_dt.month-1]}"
                    reporte_manual += f"**{fecha_txt} – SMA:** {datos_ia_aic[idx]['cielo']}, Max {p_max:.1f}°C. #ClimaSMA\n\n"
                st.info(reporte_manual + f"**SÍNTESIS:**\n{d_aic['sintesis']}")
    else:
        st.error("Error de conexión con fuentes.")
