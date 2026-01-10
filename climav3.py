import streamlit as st
import requests
import pdfplumber
import io
import json
from datetime import datetime, timedelta

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Weather Aggregator SMA", layout="wide")

def get_aic_data():
    url = "https://www.aic.gob.ar/sitio/extendido-pdf?a=1029&z=1750130550"
    try:
        response = requests.get(url, timeout=15)
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            pagina = pdf.pages[0]
            tabla = pagina.extract_table({"vertical_strategy": "lines", "horizontal_strategy": "lines"})
            
            # Ajuste de índices para evitar el desfase de días
            fechas_fila = [f.replace("\n", "") for f in tabla[0] if f]
            cielos = [c.replace("\n", " ") for c in tabla[2][1:] if c]
            temps = [t.replace("\n", "").replace(" ºC", "").strip() for t in tabla[3][1:] if t]
            vientos = [v.replace("\n", "").replace(" km/h", "").strip() for v in tabla[4][1:] if v]
            rafagas = [r.replace("\n", "").replace(" km/h", "").strip() for r in tabla[5][1:] if r]
            dirs = [d.replace("\n", "") for d in tabla[6][1:] if d]
            
            texto = pagina.extract_text()
            sintesis = texto.split("hPa")[-1].split("www.aic.gob.ar")[0].strip() if "hPa" in texto else ""

            dias_dict = []
            # Iteramos de 2 en 2 para agrupar Día y Noche correctamente
            for i in range(0, min(10, len(cielos)), 2):
                idx_fecha = i // 2
                dias_dict.append({
                    "fecha": fechas_fila[idx_fecha] if idx_fecha < len(fechas_fila) else "S/D",
                    "cielo_dia": cielos[i],
                    "cielo_noche": cielos[i+1],
                    "temp_max": temps[i],
                    "temp_min": temps[i+1],
                    "viento": vientos[i],
                    "rafaga": rafagas[i],
                    "dir": dirs[i]
                })
            return {"status": "OK", "datos": dias_dict, "sintesis_original": sintesis}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

def get_open_meteo_data():
    url = "https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35&daily=temperature_2m_max,temperature_2m_min,windspeed_10m_max,windgusts_10m_max&timezone=America%2FArgentina%2FSalta&forecast_days=5"
    try:
        r = requests.get(url, timeout=15)
        d = r.json()["daily"]
        procesados = []
        for i in range(len(d["time"])):
            procesados.append({
                "fecha": d["time"][i],
                "temp_max": d["temperature_2m_max"][i],
                "temp_min": d["temperature_2m_min"][i],
                "viento": d["windspeed_10m_max"][i],
                "rafaga": d["windgusts_10m_max"][i]
            })
        return {"status": "OK", "datos": procesados}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

def consultar_ia_con_fallback(prompt):
    api_key = st.secrets.get("OPENROUTER_API_KEY")
    modelos = ["google/gemini-2.0-flash-exp:free", "meta-llama/llama-3.1-8b-instruct:free"]
    for modelo in modelos:
        try:
            res = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                data=json.dumps({"model": modelo, "messages": [{"role": "user", "content": prompt}]}),
                timeout=20
            )
            data = res.json()
            if "choices" in data:
                return data['choices'][0]['message']['content']
        except:
            continue
    return None

# --- INTERFAZ ---
st.sidebar.title("Fuentes de Análisis")
sel_aic = st.sidebar.checkbox("AIC (PDF)", value=True)
sel_om = st.sidebar.checkbox("Open-Meteo", value=True)

st.title("🌤️ Weather Aggregator SMA")

if st.button("🚀 GENERAR PRONÓSTICO PONDERADO"):
    with st.spinner("Procesando..."):
        data_aic = get_aic_data() if sel_aic else None
        data_om = get_open_meteo_data() if sel_om else None

        # Prompt ultra-específico para forzar el formato de las capturas
        prompt_ia = f"""
        Actúa como el sistema de la AIC. Genera el pronóstico ponderado (50% OpenMeteo, 50% AIC).
        DATOS AIC: {json.dumps(data_aic)}
        DATOS OPENMETEO: {json.dumps(data_om)}
        
        ESTRUCTURA DE SALIDA OBLIGATORIA (Copia este estilo):
        Para cada uno de los 5 días:
        [Día de la semana] [Día] de [Mes] – San Martín de los Andes: [Condición] con [Cielo], y máxima esperada de [Max] °C, mínima de [Min] °C. Viento del [Dir] entre [Vel] y [Raf] km/h, [Lluvias previstas/Sin lluvias]. #SanMartínDeLosAndes #ClimaSMA #[Condición]

        Al final, incluye una sección llamada 'SÍNTESIS' que sea un solo párrafo con el análisis general.
        """

        reporte = consultar_ia_con_fallback(prompt_ia)
        
        if reporte:
            st.markdown("### 📍 Resultado Ponderado Unificado")
            st.info(reporte) # El fondo azul imita tu captura
            st.text_area("Copiar reporte para redes:", value=reporte, height=350)
        else:
            st.error("Error al generar la síntesis.")
