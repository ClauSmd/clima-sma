import streamlit as st
import requests
import pdfplumber
import io
import json
import pandas as pd
from datetime import datetime

# --- CONFIGURACIÓN Y ESTILOS ---
st.set_page_config(page_title="Weather Aggregator SMA", layout="wide")

# Estilo para botones y contenedores
st.markdown("""
    <style>
    .report-container { background-color: #f0f2f6; padding: 20px; border-radius: 10px; border-left: 5px solid #007bff; }
    .source-header { color: #555; font-weight: bold; border-bottom: 1px solid #ddd; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIONES DE EXTRACCIÓN ---

def get_aic_data():
    url = "https://www.aic.gob.ar/sitio/extendido-pdf?a=1029&z=1750130550"
    try:
        response = requests.get(url, timeout=10)
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            tabla = pdf.pages[0].extract_table({"vertical_strategy": "lines", "horizontal_strategy": "lines"})
            
            # Limpieza omitiendo la columna de etiquetas [1:]
            fechas_raw = [f.replace("\n", "") for f in tabla[0] if f]
            cielos = [c.replace("\n", " ") for c in tabla[2][1:] if c]
            temps = [t.replace("\n", "").replace(" ºC", "").strip() for t in tabla[3][1:] if t]
            vientos = [v.replace("\n", "").replace(" km/h", "").strip() for v in tabla[4][1:] if v]
            rafagas = [r.replace("\n", "").replace(" km/h", "").strip() for r in tabla[5][1:] if r]
            dirs = [d.replace("\n", "") for d in tabla[6][1:] if d]
            
            texto_completo = pdf.pages[0].extract_text()
            sintesis_orig = texto_completo.split("hPa")[-1].split("www.aic.gob.ar")[0].strip() if "hPa" in texto_completo else ""

            # Estructuramos por día (pares de columnas)
            dias_procesados = []
            for i in range(0, min(10, len(cielos)), 2):
                dias_procesados.append({
                    "fecha": fechas_raw[i],
                    "cielo_dia": cielos[i],
                    "temp_max": temps[i],
                    "temp_min": temps[i+1],
                    "viento": vientos[i],
                    "rafaga": rafagas[i],
                    "dir": dirs[i]
                })
            return {"status": "OK", "datos": dias_procesados, "sintesis": sintesis_orig}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

def get_open_meteo_data():
    url = "https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35&daily=temperature_2m_max,temperature_2m_min,windspeed_10m_max,windgusts_10m_max,weathercode&timezone=America%2FArgentina%2FSalta&forecast_days=5"
    try:
        r = requests.get(url, timeout=10)
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

# --- NÚCLEO DE INTELIGENCIA (OPENROUTER) ---

def generar_sintesis_ia(data_payload):
    api_key = st.secrets.get("OPENROUTER_API_KEY")
    if not api_key: return "Error: API Key no configurada."
    
    prompt = f"""
    Actúa como meteorólogo profesional para San Martín de los Andes.
    Analiza estos datos técnicos: {json.dumps(data_payload)}
    
    TAREAS:
    1. PONDERACIÓN: Open-Meteo tiene un peso del 50%. El resto de las fuentes (AIC) se reparten el 50% restante.
    2. SÍNTESIS: Escribe un párrafo inicial descriptivo (estilo AIC) unificando las fuentes.
    3. FORMATO DIARIO (5 días):
       [Día de la semana] [Día] de [Mes] – San Martín de los Andes: [Condición] con [Cielo], y máxima esperada de [Max] °C, mínima de [Min] °C. Viento del [Dir] entre [Vel] y [Raf] km/h, [Lluvias prevista/sin lluvias]. #SanMartínDeLosAndes #ClimaSMA #[Condicion]
    
    Sé preciso con las temperaturas ponderadas.
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
    except:
        return "La IA no pudo procesar la síntesis en este momento."

# --- INTERFAZ DE USUARIO (SIDEBAR) ---

st.sidebar.image("https://www.aic.gob.ar/sitio/img/logo-aic.png", width=100)
st.sidebar.title("Fuentes de Análisis")
sel_aic = st.sidebar.checkbox("AIC (PDF)", value=True)
sel_om = st.sidebar.checkbox("Open-Meteo (API)", value=True)
sel_smn = st.sidebar.checkbox("SMN (Próximamente)", value=False, disabled=True)

st.sidebar.divider()
st.sidebar.info("Peso configurado:\n- OpenMeteo: 50%\n- Otras: 50% (repartido)")

# --- CUERPO PRINCIPAL ---

st.title("🌤️ Weather Aggregator - San Martín de los Andes")

if st.button("🚀 GENERAR PRONÓSTICO PONDERADO"):
    fuentes_activas = []
    
    with st.spinner("Consultando fuentes seleccionadas..."):
        # 1. Obtención de datos individuales
        data_final = {}
        if sel_aic:
            res_aic = get_aic_data()
            data_final["AIC"] = res_aic
        if sel_om:
            res_om = get_open_meteo_data()
            data_final["OpenMeteo"] = res_om

        # 2. Generación de Resultado Ponderado vía IA
        st.subheader("📍 Resultado Ponderado Unificado")
        reporte_ia = generar_sintesis_ia(data_final)
        
        st.markdown(f'<div class="report-container">{reporte_ia}</div>', unsafe_allow_html=True)
        
        # Botón de copiar (simulado con text_area para facilitar selección)
        st.text_area("Copiar Reporte:", value=reporte_ia, height=200)

        st.divider()

        # 3. Desglose Individual (Comparativa)
        st.subheader("🔍 Desglose Técnico por Fuente")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if sel_aic:
                st.markdown('<p class="source-header">AIC DATOS OBTENIDOS</p>', unsafe_allow_html=True)
                if res_aic["status"] == "OK":
                    for d in res_aic["datos"]:
                        st.write(f"**{d['fecha']}**: {d['cielo_dia']} | Max: {d['temp_max']}° | Viento: {d['viento']}km/h")
                    st.caption(f"SÍNTESIS AIC: {res_aic['sintesis']}")
                else:
                    st.error("Error al obtener AIC")

        with col2:
            if sel_om:
                st.markdown('<p class="source-header">OPEN-METEO DATOS OBTENIDOS</p>', unsafe_allow_html=True)
                if res_om["status"] == "OK":
                    for d in res_om["datos"]:
                        st.write(f"**{d['fecha']}**: Max: {d['temp_max']}° | Min: {d['temp_min']}° | Viento: {d['viento']}km/h")
                else:
                    st.error("Error al obtener Open-Meteo")

else:
    st.write("Selecciona las fuentes en la barra lateral y presiona el botón para comenzar.")
