import streamlit as st
import requests
import pdfplumber
import io
import json
import google.generativeai as genai
from datetime import datetime
import time

# --- 1. CONFIGURACIÓN E INTERFAZ ---
st.set_page_config(page_title="Weather Aggregator SMA", layout="wide")

# Mapeo de iconos basado en AIC
ICONOS_CIELO = {
    "Despejado": "☀️", "Mayormente Despejado": "🌤️", "Parcialmente Nublado": "⛅",
    "Nublado": "☁️", "Cubierto": "🌥️", "Inestable": "🌦️", 
    "Lluvias Débiles y Dispersas": "🌧️", "Lluvia": "🌧️", "Nieve": "❄️"
}

# --- Barra Lateral (SIDEBAR) ---
st.sidebar.title("Configuración")
fecha_inicio = st.sidebar.date_input("📅 Fecha de inicio", datetime.now().date())
usa_ia = st.sidebar.toggle("🤖 Activar Inteligencia Artificial", value=True)

if usa_ia:
    st.sidebar.info("La IA redactará el reporte final usando cascada de modelos.")
else:
    st.sidebar.warning("Modo Manual: Reporte directo con promedios redondeados.")

# --- 2. FUNCIONES TÉCNICAS (AIC, Open-Meteo e IA) ---

def get_aic_data():
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
            v_dir = [d.replace("\n", "") for d in tabla[6][1:] if d]
            sintesis = pagina.extract_text().split("hPa")[-1].split("www.aic.gob.ar")[0].strip() if "hPa" in pagina.extract_text() else ""
            
            dias_dict = []
            for i in range(len(cielos)):
                f_obj = datetime.strptime(fechas_raw[i // 2], "%d-%m-%Y").date()
                dias_dict.append({
                    "fecha_obj": f_obj, "fecha_str": fechas_raw[i // 2],
                    "cielo": cielos[i], "max": float(temps[i]), "viento": float(v_vel[i]), "dir": v_dir[i]
                })
            return {"status": "OK", "datos": dias_dict, "sintesis": sintesis}
    except Exception as e: return {"status": "ERROR", "error": str(e)}

def get_open_meteo_data():
    url = "https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35&daily=temperature_2m_max,temperature_2m_min,windspeed_10m_max,windgusts_10m_max,precipitation_probability_max&timezone=America%2FArgentina%2FSalta&forecast_days=10"
    try:
        r = requests.get(url, timeout=15).json()["daily"]
        return {"status": "OK", "datos": [{"fecha_obj": datetime.strptime(r["time"][i], "%Y-%m-%d").date(), "max": r["temperature_2m_max"][i], "min": r["temperature_2m_min"][i], "viento": r["windspeed_10m_max"][i], "rafaga": r["windgusts_10m_max"][i], "prob_lluvia": r["precipitation_probability_max"][i]} for i in range(len(r["time"]))]}
    except Exception as e: return {"status": "ERROR", "error": str(e)}

def consultar_ia_cascada(prompt):
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key: return None, "Falta API Key"
    genai.configure(api_key=api_key)
    # Orden de prioridad exacto según tu instrucción
    modelos = ["gemini-3-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemma-3-27b", "gemini-2.5-flash-native-audio-dialog"]
    for mod in modelos:
        try:
            model = genai.GenerativeModel(mod)
            response = model.generate_content(prompt)
            if response.text: return response.text, mod
        except: 
            time.sleep(1) # Delay técnico para evitar bloqueos por RPM
            continue
    return None, "Saturación total de modelos"

# --- 3. LÓGICA DE EJECUCIÓN ---
st.title("🌤️ Weather Aggregator SMA")

if st.button("🚀 PROCESAR PRONÓSTICOS"):
    with st.spinner("Sincronizando fuentes..."):
        d_aic = get_aic_data()
        d_om = get_open_meteo_data()

    if d_aic["status"] == "OK" and d_om["status"] == "OK":
        # Filtrar datos por la fecha del calendario
        aic_f = [d for d in d_aic["datos"] if d["fecha_obj"] >= fecha_inicio]
        om_f = [d for d in d_om["datos"] if d["fecha_obj"] >= fecha_inicio]
        dias_compatibles = min(len(aic_f) // 2, len(om_f))

        if dias_compatibles > 0:
            # --- VISUALIZACIÓN TABLA ESTILO AIC ---
            st.subheader("🎯 Pronóstico Ponderado (Estructura AIC)")
            meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
            
            # Columnas interactivas
            cols = st.columns(dias_compatibles)
            reporte_base_texto = ""

            for i in range(dias_compatibles):
                idx_aic = i * 2 # Fusión Día/Noche
                
                # Redondeo lógico sin decimales
                t_max = int(round((aic_f[idx_aic]['max'] + om_f[i]['max']) / 2))
                t_min = int(round((aic_f[idx_aic+1]['max'] + om_f[i]['min']) / 2))
                v_vel = int(round((aic_f[idx_aic]['viento'] + om_f[i]['viento']) / 2))
                v_raf = int(round(om_f[i]['rafaga']))
                
                icono = ICONOS_CIELO.get(aic_f[idx_aic]['cielo'], "🌡️")
                fecha_fmt = f"{aic_f[idx_aic]['fecha_obj'].strftime('%d/%m')}"
                
                with cols[i]:
                    st.markdown(f"**{fecha_fmt}**")
                    st.metric(f"{icono}", f"{t_max}° / {t_min}°")
                    st.write(f"💨 {v_vel} km/h")
                
                reporte_base_texto += f"- {fecha_fmt}: {aic_f[idx_aic]['cielo']}, {t_max}°/{t_min}°. Viento {v_vel}km/h (Ráf. {v_raf}km/h).\n"

            # --- REPORTE FINAL (IA O MANUAL) ---
            st.markdown("---")
            if usa_ia:
                with st.spinner("La IA está redactando..."):
                    prompt = f"Actúa como meteorólogo. Resume estos datos en el formato: [Día] [Fecha] de [Mes] – SMA: [Condición], [Tmax]/[Tmin]C. Viento [Dir] [Vel]km/h. #ClimaSMA. Datos: {reporte_base_texto}. Síntesis AIC: {d_aic['sintesis']}"
                    res, mod_usado = consultar_ia_cascada(prompt)
                    if res:
                        st.success(f"Generado con {mod_usado}")
                        st.info(res)
                    else:
                        st.error("IA saturada. Mostrando versión manual.")
                        st.text(reporte_base_texto + f"\nSÍNTESIS: {d_aic['sintesis']}")
            else:
                st.info(reporte_base_texto + f"\n**SÍNTESIS DIARIA:**\n{d_aic['sintesis']}")

            # --- DATOS CRUDOS EN DESPLEGABLES ---
            with st.expander("📊 Ver Datos Crudos (AIC y Open-Meteo)"):
                st.json({"AIC": aic_f[:dias_compatibles*2], "OpenMeteo": om_f[:dias_compatibles]})
        else:
            st.warning("No hay datos para la fecha seleccionada.")
