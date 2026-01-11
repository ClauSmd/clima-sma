import streamlit as st
import requests
import pdfplumber
import io
import google.generativeai as genai
from datetime import datetime, timedelta
import time

# --- 1. CONFIGURACIÓN E INTERFAZ ---
st.set_page_config(page_title="Weather Aggregator SMA", layout="wide")

# Mapeo de iconos basado en AIC
ICONOS_CIELO = {
    "Despejado": "☀️", "Mayormente Despejado": "🌤️", "Parcialmente Nublado": "⛅",
    "Nublado": "☁️", "Cubierto": "🌥️", "Inestable": "🌦️", 
    "Mayormente Cubierto": "🌥️", "Lluvias Débiles y Dispersas": "🌧️", 
    "Lluvia": "🌧️", "Nieve": "❄️", "N/D": "🌡️"
}

st.sidebar.title("Configuración")
fecha_inicio = st.sidebar.date_input("📅 Fecha de inicio", datetime.now().date())
usa_ia = st.sidebar.toggle("🤖 Activar Inteligencia Artificial", value=True)

# --- 2. FUNCIONES DE EXTRACCIÓN Y PROCESAMIENTO ---

def get_aic_data():
    """Extrae datos de la AIC y captura la síntesis"""
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
            
            texto_completo = pagina.extract_text()
            sintesis = texto_completo.split("hPa")[-1].split("www.aic.gob.ar")[0].strip() if "hPa" in texto_completo else ""
            
            dias_dict = []
            for i in range(len(cielos)):
                f_obj = datetime.strptime(fechas_raw[i // 2], "%d-%m-%Y").date()
                dias_dict.append({
                    "fecha_obj": f_obj, "cielo": cielos[i], 
                    "max": float(temps[i]), "viento": float(v_vel[i]), "dir": v_dir[i]
                })
            return {"status": "OK", "datos": dias_dict, "sintesis": sintesis}
    except Exception as e: return {"status": "ERROR", "error": str(e)}

def get_open_meteo_data():
    """Extrae datos de Open-Meteo para ponderación y ráfagas"""
    url = "https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35&daily=temperature_2m_max,temperature_2m_min,windspeed_10m_max,windgusts_10m_max,precipitation_probability_max&timezone=America%2FArgentina%2FSalta&forecast_days=10"
    try:
        r = requests.get(url, timeout=15).json()["daily"]
        procesados = []
        for i in range(len(r["time"])):
            procesados.append({
                "fecha_obj": datetime.strptime(r["time"][i], "%Y-%m-%d").date(),
                "max": r["temperature_2m_max"][i], "min": r["temperature_2m_min"][i],
                "viento": r["windspeed_10m_max"][i], "rafaga": r["windgusts_10m_max"][i]
            })
        return {"status": "OK", "datos": procesados}
    except Exception as e: return {"status": "ERROR", "error": str(e)}

def consultar_ia_cascada(prompt):
    """Maneja límites de 5 RPM rotando modelos"""
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key: return None, "Falta API Key"
    genai.configure(api_key=api_key)
    modelos = ["gemini-3-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemma-3-27b", "gemini-2.5-flash-native-audio-dialog"]
    for mod in modelos:
        try:
            model = genai.GenerativeModel(mod)
            response = model.generate_content(prompt)
            if response.text: return response.text, mod
        except: 
            time.sleep(1.2) # Pausa técnica para reset de cuota
            continue
    return None, "Cuota agotada"

# --- 3. LÓGICA PRINCIPAL ---

st.title("🌤️ Weather Aggregator SMA")

if st.button("🚀 GENERAR PRONÓSTICO 5 DÍAS"):
    with st.spinner("Fusionando fuentes estilo AIC..."):
        d_aic = get_aic_data()
        d_om = get_open_meteo_data()

    if d_aic["status"] == "OK" and d_om["status"] == "OK":
        # --- UNIFICACIÓN AIC (Fusión Día/Noche para Máximas y Mínimas) ---
        aic_unificado = {}
        for d in d_aic["datos"]:
            f = d["fecha_obj"]
            if f not in aic_unificado:
                aic_unificado[f] = {"cielo": d["cielo"], "max": d["max"], "min": d["max"], "viento": d["viento"], "dir": d["dir"]}
            else:
                if d["max"] < aic_unificado[f]["min"]: aic_unificado[f]["min"] = d["max"]
                if d["max"] > aic_unificado[f]["max"]: aic_unificado[f]["max"] = d["max"]

        # --- CONSTRUCCIÓN DE 5 DÍAS (FUSIÓN TRANSPARENTE) ---
        pronostico_final = []
        for i in range(5):
            fecha_act = fecha_inicio + timedelta(days=i)
            data_om = next((x for x in d_om["datos"] if x["fecha_obj"] == fecha_act), None)
            data_aic = aic_unificado.get(fecha_act)

            if data_om:
                if data_aic:
                    t_max = int(round((data_aic['max'] + data_om['max']) / 2))
                    t_min = int(round((data_aic['min'] + data_om['min']) / 2))
                    v_vel = int(round((data_aic['viento'] + data_om['viento']) / 2))
                    cielo_desc = data_aic['cielo']
                    dir_v = data_aic['dir']
                else:
                    t_max = int(round(data_om['max']))
                    t_min = int(round(data_om['min']))
                    v_vel = int(round(data_om['viento']))
                    cielo_desc = "N/D"
                    dir_v = "O"
                
                v_raf = int(round(data_om['rafaga']))
                icono = ICONOS_CIELO.get(cielo_desc, "🌡️")
                
                # Formateo de fecha para el resumen
                meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
                dias_sem = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
                fecha_txt = f"{dias_sem[fecha_act.weekday()]} {fecha_act.day} de {meses[fecha_act.month-1]}"

                pronostico_final.append({
                    "header": f"{dias_sem[fecha_act.weekday()][:3].lower()} {fecha_act.day}",
                    "icono": icono, "cielo_desc": cielo_desc,
                    "t_max": t_max, "t_min": t_min, "v_vel": v_vel, "v_raf": v_raf, "dir_v": dir_v,
                    "resumen": f"{fecha_txt} – SMA: {icono} {cielo_desc}, máxima {t_max}°, mínima {t_min}°. Viento {dir_v} a {v_vel} km/h (Ráf. {v_raf} km/h). #ClimaSMA"
                })

        # --- 4. DISEÑO VISUAL AIC ---
        st.subheader("🎯 Pronóstico Final Ponderado")
        cols = st.columns(5)
        reporte_texto = ""
        
        for idx, p in enumerate(pronostico_final):
            with cols[idx]:
                st.markdown(f"### {p['header']}")
                st.markdown(f"**Cielo**\n\n# {p['icono']}")
                st.markdown(f"**Estado**\n{p['cielo_desc']}")
                st.markdown(f"**Temperatura**\n{p['t_max']}°C / {p['t_min']}°C")
                st.markdown(f"**Viento**\n{p['v_vel']} km/h")
                st.markdown(f"**Ráfagas**\n{p['v_raf']} km/h")
                st.markdown(f"**Dirección**\n{p['dir_v']}")
                st.markdown("**Presión**\n1012 hPa")
            reporte_texto += p["resumen"] + "\n\n"

        # --- 5. SALIDA DE TEXTO / IA ---
        st.markdown("---")
        if usa_ia:
            prompt = f"Redacta el pronóstico para SMA basado en esto: {reporte_texto}. Síntesis: {d_aic['sintesis']}"
            res, mod = consultar_ia_cascada(prompt)
            if res:
                st.success(f"Optimizado con {mod}")
                st.info(res)
            else:
                st.info(reporte_texto + f"**SÍNTESIS:**\n{d_aic['sintesis']}")
        else:
            st.info(reporte_texto + f"**SÍNTESIS:**\n{d_aic['sintesis']}")

        # --- 6. DATOS CRUDOS SIMPLIFICADOS ---
        with st.expander("📊 Ver Datos Crudos"):
            c1, c2 = st.columns(2)
            with c1:
                st.write("**AIC (Fusión):**")
                for f, a in aic_unificado.items():
                    st.write(f"📅 {f}: {int(round(a['max']))}° / {int(round(a['min']))}°")
            with c2:
                st.write("**Open-Meteo:**")
                for o in d_om["datos"][:5]:
                    st.write(f"📅 {o['fecha_obj']}: {int(round(o['max']))}° / {int(round(o['min']))}°")

    else: st.error("Error al obtener datos.")
