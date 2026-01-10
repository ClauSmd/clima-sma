import streamlit as st
import requests
import pdfplumber
import io
import json
from datetime import datetime

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Weather Aggregator SMA", layout="wide")

def get_aic_data():
    """Extrae datos del PDF de la AIC"""
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
            for i in range(0, min(10, len(cielos)), 2):
                idx = i // 2
                dias_dict.append({
                    "fecha": fechas_fila[idx] if idx < len(fechas_fila) else "S/D",
                    "cielo": cielos[i],
                    "max": float(temps[i]),
                    "min": float(temps[i+1]),
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

def llamar_ia_con_fallback(prompt):
    """Gestión de tokens y respaldo entre modelos de OpenRouter"""
    api_key = st.secrets.get("OPENROUTER_API_KEY")
    modelos = ["google/gemini-2.0-flash-exp:free", "meta-llama/llama-3.1-8b-instruct:free"]
    
    for modelo in modelos:
        try:
            res = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                data=json.dumps({"model": modelo, "messages": [{"role": "user", "content": prompt}]}),
                timeout=30
            )
            data = res.json()
            if "choices" in data:
                return data['choices'][0]['message']['content'], modelo
        except:
            continue
    return None, None

# --- 2. INTERFAZ ---
st.sidebar.title("Fuentes Seleccionadas")
sel_aic = st.sidebar.checkbox("AIC (PDF)", value=True)
sel_om = st.sidebar.checkbox("Open-Meteo", value=True)

st.title("🌤️ Weather Aggregator - Ponderación 50/50")

if st.button("🚀 GENERAR PRONÓSTICO PONDERADO"):
    with st.spinner("Analizando AIC y Open-Meteo..."):
        d_aic = get_aic_data() if sel_aic else None
        d_om = get_open_meteo_data() if sel_om else None

        # Mostrar tabla comparativa de control
        st.subheader("📊 Comparativa de Datos Crudos")
        col_a, col_b = st.columns(2)
        with col_a:
            st.write("**AIC (Máximas):**", [d['max'] for d in d_aic['datos']] if d_aic else "N/A")
        with col_b:
            st.write("**Open-Meteo (Máximas):**", [d['max'] for d in d_om['datos']] if d_om else "N/A")

        # Prompt para la IA con el formato exacto de tus capturas
        prompt = f"""
        Actúa como meteorólogo. Genera el pronóstico ponderado al 50/50.
        DATOS AIC: {json.dumps(d_aic)}
        DATOS OPENMETEO: {json.dumps(d_om)}
        
        FORMATO OBLIGATORIO:
        [Día Semana] [Día] de [Mes] – San Martín de los Andes: [Condición] con [Cielo], máxima [Max] °C, mínima [Min] °C. Viento del [Dir] entre [Vel] y [Raf] km/h, [Lluvias]. #SanMartínDeLosAndes #ClimaSMA
        
        SÍNTESIS DIARIA:
        [Análisis narrativo unificado]
        """

        reporte, modelo = llamar_ia_con_fallback(prompt)
        
        if reporte:
            st.markdown("---")
            st.subheader(f"📍 Resultado Ponderado (Modelo: {modelo.split('/')[-1]})")
            st.info(reporte) # Contenedor celeste como en tu captura
            st.text_area("Copia el reporte aquí:", value=reporte, height=350)
        else:
            st.error("No se pudo obtener respuesta de las IAs configuradas.")
