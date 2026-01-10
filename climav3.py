import streamlit as st
import requests
import pdfplumber
import io
import json
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Weather Aggregator SMA", layout="wide")

# --- 1. FUNCIONES DE EXTRACCIÓN (CORREGIDAS Y COMPLETAS) ---

def get_aic_data():
    url = "https://www.aic.gob.ar/sitio/extendido-pdf?a=1029&z=1750130550"
    try:
        response = requests.get(url, timeout=10)
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            pagina = pdf.pages[0]
            tabla = pagina.extract_table({"vertical_strategy": "lines", "horizontal_strategy": "lines"})
            
            # Limpieza: ignoramos la columna de etiquetas [1:]
            fechas_raw = [f.replace("\n", "") for f in tabla[0] if f]
            cielos = [c.replace("\n", " ") for c in tabla[2][1:] if c]
            temps = [t.replace("\n", "").replace(" ºC", "").strip() for t in tabla[3][1:] if t]
            vientos = [v.replace("\n", "").replace(" km/h", "").strip() for v in tabla[4][1:] if v]
            rafagas = [r.replace("\n", "").replace(" km/h", "").strip() for r in tabla[5][1:] if r]
            dirs = [d.replace("\n", "") for d in tabla[6][1:] if d]
            
            # Captura de la síntesis original del PDF
            texto_completo = pagina.extract_text()
            sintesis_orig = ""
            if "hPa" in texto_completo:
                sintesis_orig = texto_completo.split("hPa")[-1].split("www.aic.gob.ar")[0].strip()
                sintesis_orig = " ".join(sintesis_orig.split())

            dias_procesados = []
            for i in range(0, min(10, len(cielos)), 2):
                dias_procesados.append({
                    "fecha": fechas_raw[i // 2] if i // 2 < len(fechas_raw) else "S/D",
                    "momento": "Día/Noche",
                    "cielo": f"Día: {cielos[i]} - Noche: {cielos[i+1]}",
                    "temp_max": temps[i],
                    "temp_min": temps[i+1],
                    "viento_prom": vientos[i],
                    "rafaga_max": rafagas[i],
                    "direccion": dirs[i]
                })
            return {"status": "OK", "datos": dias_procesados, "sintesis_original": sintesis_orig}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

def get_open_meteo_data():
    # Coordenadas San Martín de los Andes
    url = "https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35&daily=temperature_2m_max,temperature_2m_min,windspeed_10m_max,windgusts_10m_max&timezone=America%2FArgentina%2FSalta&forecast_days=5"
    try:
        r = requests.get(url, timeout=10)
        d = r.json()["daily"]
        procesados = []
        for i in range(len(d["time"])):
            procesados.append({
                "fecha": d["time"][i],
                "temp_max": d["temperature_2m_max"][i],
                "temp_min": d["temperature_2m_min"][i],
                "viento_max": d["windspeed_10m_max"][i],
                "rafaga_max": d["windgusts_10m_max"][i]
            })
        return {"status": "OK", "datos": procesados}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

# --- 2. NÚCLEO DE INTELIGENCIA (OPENROUTER) ---

def generar_reporte_ponderado(data_payload):
    api_key = st.secrets.get("OPENROUTER_API_KEY")
    if not api_key:
        return "⚠️ Error: Configura la API Key en Streamlit Secrets."
    
    prompt = f"""
    Eres un experto meteorólogo. Genera el pronóstico para San Martín de los Andes basándote en: {json.dumps(data_payload)}.
    
    REGLAS DE NEGOCIO:
    1. Open-Meteo tiene peso 50%. AIC tiene peso 50%. Promedia temperaturas y vientos.
    2. FORMATO DE SALIDA (Imita las capturas enviadas):
       Genera una lista de 5 días con este formato exacto:
       [Día Semana] [Día] de [Mes] – San Martín de los Andes: [Condición] con [Cielo], y máxima esperada de [Max] °C, mínima de [Min] °C. Viento del [Dir] entre [Vel] y [Raf] km/h, [Lluvias]. #SanMartínDeLosAndes #ClimaSMA #[Hashtag]
    
    3. SÍNTESIS FINAL:
       Luego de los 5 días, añade una sección titulada "SÍNTESIS DIARIA" con un párrafo narrativo (estilo AIC) de 4 líneas que resuma la situación climática general.
    """
    
    try:
        res = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            data=json.dumps({
                "model": "google/gemini-2.0-flash-exp:free",
                "messages": [{"role": "user", "content": prompt}]
            })
        )
        return res.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"Error en la IA: {e}"

# --- 3. INTERFAZ DE USUARIO ---

st.sidebar.title("Fuentes de Análisis")
sel_aic = st.sidebar.checkbox("AIC (PDF)", value=True)
sel_om = st.sidebar.checkbox("Open-Meteo (API)", value=True)

st.title("🌤️ Weather Aggregator SMA")

if st.button("🚀 GENERAR PRONÓSTICO PONDERADO"):
    data_final = {}
    
    with st.spinner("Procesando datos y ponderando..."):
        # Ejecución de las funciones definidas arriba
        if sel_aic:
            data_final["AIC"] = get_aic_data()
        if sel_om:
            data_final["OpenMeteo"] = get_open_meteo_data()

        # Llamada a la IA
        reporte_final = generar_reporte_ponderado(data_final)
        
        st.subheader("📍 Resultado Ponderado Unificado")
        # Mostramos el resultado con formato
        st.info(reporte_final)
        
        # Área de copiado
        st.text_area("Selecciona y copia para publicar:", value=reporte_final, height=400)

    # Desglose comparativo abajo
    st.divider()
    st.subheader("🔍 Desglose Técnico")
    c1, c2 = st.columns(2)
    with c1:
        st.write("**Datos AIC Obtenidos:**")
        st.json(data_final.get("AIC", {}))
    with c2:
        st.write("**Datos Open-Meteo Obtenidos:**")
        st.json(data_final.get("OpenMeteo", {}))
