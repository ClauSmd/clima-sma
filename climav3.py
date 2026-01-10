import streamlit as st
import requests
import pdfplumber
import io
import json
from datetime import datetime

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Weather Aggregator SMA", layout="wide")

# --- 2. DEFINICIÓN DE FUNCIONES (DEBEN IR ANTES DEL CUERPO PRINCIPAL) ---

def get_aic_data():
    """Extrae datos del PDF de la AIC"""
    url = "https://www.aic.gob.ar/sitio/extendido-pdf?a=1029&z=1750130550"
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            pagina = pdf.pages[0]
            tabla = pagina.extract_table({"vertical_strategy": "lines", "horizontal_strategy": "lines"})
            
            # Extraemos datos saltando la columna de etiquetas
            cielos = [c.replace("\n", " ") for c in tabla[2][1:] if c]
            temps = [t.replace("\n", "").replace(" ºC", "").strip() for t in tabla[3][1:] if t]
            vientos = [v.replace("\n", "").replace(" km/h", "").strip() for v in tabla[4][1:] if v]
            rafagas = [r.replace("\n", "").replace(" km/h", "").strip() for r in tabla[5][1:] if r]
            dirs = [d.replace("\n", "") for d in tabla[6][1:] if d]
            
            texto = pagina.extract_text()
            sintesis = texto.split("hPa")[-1].split("www.aic.gob.ar")[0].strip() if "hPa" in texto else ""

            dias_dict = []
            for i in range(0, min(10, len(cielos)), 2):
                dias_dict.append({
                    "cielo": cielos[i],
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
    """Extrae datos de la API de Open-Meteo"""
    url = "https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35&daily=temperature_2m_max,temperature_2m_min,windspeed_10m_max,windgusts_10m_max&timezone=America%2FArgentina%2FSalta&forecast_days=5"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
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
    """Prueba múltiples modelos si uno falla"""
    api_key = st.secrets.get("OPENROUTER_API_KEY")
    modelos = [
        "google/gemini-2.0-flash-exp:free", 
        "meta-llama/llama-3.1-8b-instruct:free",
        "mistralai/mistral-7b-instruct:free"
    ]
    
    for modelo in modelos:
        try:
            res = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                data=json.dumps({
                    "model": modelo,
                    "messages": [{"role": "user", "content": prompt}]
                }),
                timeout=20
            )
            data = res.json()
            if "choices" in data:
                return data['choices'][0]['message']['content'], modelo
        except:
            continue
    return None, None

# --- 3. INTERFAZ Y LÓGICA PRINCIPAL ---

st.sidebar.title("Fuentes de Análisis")
sel_aic = st.sidebar.checkbox("AIC (PDF)", value=True)
sel_om = st.sidebar.checkbox("Open-Meteo", value=True)

st.title("🌤️ Weather Aggregator SMA")

if st.button("🚀 GENERAR PRONÓSTICO PONDERADO"):
    data_final = {}
    
    # Obtención de datos
    if sel_aic:
        data_final["AIC"] = get_aic_data()
    if sel_om:
        data_final["OpenMeteo"] = get_open_meteo_data()

    # Construcción del Prompt
    prompt_ia = f"""
    Eres un meteorólogo. Genera el pronóstico ponderado (50% OpenMeteo, 50% AIC) para San Martín de los Andes.
    DATOS: {json.dumps(data_final)}
    
    FORMATO REQUERIDO:
    1. Reporte de 5 días con el formato: [Día Semana] [Día] de [Mes] – San Martín de los Andes: [Condicion] con [Cielo], máxima [Max]°C, mínima [Min]°C. Viento [Dir] [Vel]-[Raf] km/h. #SanMartínDeLosAndes #ClimaSMA
    2. Al final, añade una sección 'SÍNTESIS DIARIA' con un párrafo narrativo unificado.
    """

    with st.spinner("Ponderando datos con IA..."):
        respuesta, modelo_usado = consultar_ia_con_fallback(prompt_ia)
        
        if respuesta:
            st.subheader(f"📍 Resultado Unificado (Modelo: {modelo_usado.split('/')[-1]})")
            st.info(respuesta)
            st.text_area("Copiar reporte:", value=respuesta, height=300)
        else:
            st.error("No se pudo obtener respuesta de ninguna IA. Verifica tu API Key.")

    # Desglose técnico (Abajo)
    st.divider()
    st.subheader("🔍 Desglose de Fuentes")
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Datos AIC:**", data_final.get("AIC"))
    with col2:
        st.write("**Datos Open-Meteo:**", data_final.get("OpenMeteo"))
