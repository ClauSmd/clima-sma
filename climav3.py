import streamlit as st
import requests
import pdfplumber
import io
import json
import google.generativeai as genai
from datetime import datetime

# --- 1. CONFIGURACIÓN E INTERFAZ ---
st.set_page_config(page_title="Weather Aggregator SMA", layout="wide")

st.sidebar.title("Configuración")
fecha_inicio = st.sidebar.date_input("Fecha de inicio", datetime.now().date())
usa_ia = st.sidebar.toggle("Activar Inteligencia Artificial", value=True)

st.title("🌤️ Sistema Meteorológico SMA")
st.markdown("---")

# --- 2. FUNCIONES DE EXTRACCIÓN ---

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
            v_raf = [r.replace("\n", "").replace(" km/h", "").strip() for r in tabla[5][1:] if r]
            v_dir = [d.replace("\n", "") for d in tabla[6][1:] if d]
            
            dias_dict = []
            for i in range(len(cielos)):
                f_obj = datetime.strptime(fechas_raw[i // 2], "%d-%m-%Y").date()
                dias_dict.append({
                    "fecha_obj": f_obj, "fecha_str": fechas_raw[i // 2],
                    "cielo": cielos[i], "max": float(temps[i]), 
                    "viento": float(v_vel[i]), "rafaga": float(v_raf[i]), "dir": v_dir[i]
                })
            texto = pagina.extract_text()
            sintesis = texto.split("hPa")[-1].split("www.aic.gob.ar")[0].strip() if "hPa" in texto else ""
            return {"status": "OK", "datos": dias_dict, "sintesis": sintesis}
    except Exception as e: return {"status": "ERROR", "error": str(e)}

def get_open_meteo_data():
    url = "https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35&daily=temperature_2m_max,temperature_2m_min,windspeed_10m_max,windgusts_10m_max,precipitation_probability_max&timezone=America%2FArgentina%2FSalta&forecast_days=10"
    try:
        r = requests.get(url, timeout=15).json()["daily"]
        procesados = []
        for i in range(len(r["time"])):
            procesados.append({
                "fecha_obj": datetime.strptime(r["time"][i], "%Y-%m-%d").date(),
                "max": r["temperature_2m_max"][i], "min": r["temperature_2m_min"][i],
                "viento": r["windspeed_10m_max"][i], "rafaga": r["windgusts_10m_max"][i],
                "prob_lluvia": r["precipitation_probability_max"][i]
            })
        return {"status": "OK", "datos": procesados}
    except Exception as e: return {"status": "ERROR", "error": str(e)}

# --- 3. LÓGICA PRINCIPAL ---

if st.button("🚀 PROCESAR PRONÓSTICOS"):
    with st.spinner("Obteniendo información de fuentes..."):
        d_aic = get_aic_data()
        d_om = get_open_meteo_data()

    if d_aic["status"] == "OK" and d_om["status"] == "OK":
        # Filtrado por fecha seleccionada
        aic_f = [d for d in d_aic["datos"] if d["fecha_obj"] >= fecha_inicio]
        om_f = [d for d in d_om["datos"] if d["fecha_obj"] >= fecha_inicio]
        dias_compatibles = min(len(aic_f) // 2, len(om_f))

        # --- SECCIÓN: VISTA DE DATOS POR SEPARADO ---
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📊 Datos Crudos: Open-Meteo")
            for i in range(dias_compatibles):
                d = om_f[i]
                st.code(f"{d['fecha_obj'].strftime('%A %d')} – SMA: {d['max']}°C / {d['min']}°C | Viento: {d['viento']}km/h | Prob. Lluvia: {d['prob_lluvia']}%")

        with col2:
            st.subheader("📄 Datos Crudos: AIC (PDF)")
            for i in range(dias_compatibles * 2): # AIC tiene Día y Noche
                d = aic_f[i]
                st.code(f"{d['fecha_str']} ({'Día' if i%2==0 else 'Noche'}): {d['cielo']} | Max: {d['max']}°C | Viento: {d['viento']}km/h")

        st.markdown("---")

        # --- SECCIÓN: RESULTADO FINAL (FUSIONADO) ---
        st.subheader("🎯 Pronóstico Final Ponderado")
        
        meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
        dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        
        reporte_final = ""
        for i in range(dias_compatibles):
            idx_aic = i * 2 # Fusión de un solo día
            p_max = (aic_f[idx_aic]['max'] + om_f[i]['max']) / 2
            p_min = (aic_f[idx_aic + 1]['max'] + om_f[i]['min']) / 2 # Min de OM con Noche de AIC
            p_viento = (aic_f[idx_aic]['viento'] + om_f[i]['viento']) / 2
            
            f_dt = aic_f[idx_aic]['fecha_obj']
            fecha_txt = f"{dias_semana[f_dt.weekday()]} {f_dt.day} de {meses[f_dt.month-1]}"
            
            prob = f", prob. precipitación ({om_f[i]['prob_lluvia']}%)" if om_f[i]['prob_lluvia'] > 0 else ", sin lluvias previstas"
            
            linea = (f"{fecha_txt} – San Martín de los Andes: {aic_f[idx_aic]['cielo']}, "
                     f"máxima esperada de {p_max:.1f} °C, mínima de {p_min:.1f} °C. "
                     f"Viento del {aic_f[idx_aic]['dir']} a {p_viento:.1f} km/h con ráfagas de {om_f[i]['rafaga']:.1f} km/h{prob}. "
                     f"#SanMartinDeLosAndes #ClimaSMA\n" + "-"*80 + "\n")
            reporte_final += linea

        if usa_ia:
            # Enviar este reporte estructurado a Gemini para pulir la redacción
            genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
            model = genai.GenerativeModel("gemini-3-flash")
            prompt = f"Mejora la redacción de este pronóstico meteorológico manteniendo este formato exacto:\n{reporte_final}\n\nSÍNTESIS DIARIA: {d_aic['sintesis']}"
            try:
                res = model.generate_content(prompt)
                st.info(res.text)
            except:
                st.warning("Fallo en IA, mostrando versión fusionada manual:")
                st.text(reporte_final + f"\nSÍNTESIS DIARIA:\n{d_aic['sintesis']}")
        else:
            st.text(reporte_final + f"\nSÍNTESIS DIARIA:\n{d_aic['sintesis']}")

    else: st.error("No se pudieron cargar las fuentes.")
