import streamlit as st
import requests
import pdfplumber
import io
import json
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Weather Aggregator SMA", layout="wide")

# [Mantener funciones get_aic_data y get_open_meteo_data del código anterior]

def consultar_openrouter(prompt, modelos):
    """Prueba una lista de modelos en orden hasta que uno responda"""
    api_key = st.secrets.get("OPENROUTER_API_KEY")
    
    for modelo in modelos:
        try:
            st.write(f"Refinando con IA (Probando modelo: {modelo.split('/')[-1]})...")
            res = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                data=json.dumps({
                    "model": modelo,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.5
                }),
                timeout=25
            )
            response_json = res.json()
            if "choices" in response_json:
                return response_json['choices'][0]['message']['content']
        except Exception as e:
            st.warning(f"El modelo {modelo} falló. Saltando al siguiente...")
            continue
    return None

def generar_reporte_ponderado(data_payload):
    # Definimos la lista de modelos gratuitos de respaldo
    modelos_disponibles = [
        "google/gemini-2.0-flash-exp:free",
        "meta-llama/llama-3.1-8b-instruct:free",
        "mistralai/mistral-7b-instruct:free"
    ]
    
    prompt = f"""
    Eres un meteorólogo de San Martín de los Andes. 
    Analiza estos datos (Ponderación 50/50): {json.dumps(data_payload)}
    
    1. Genera 5 reportes diarios con este formato:
       [Día Semana] [Día] de [Mes] – San Martín de los Andes: [Condición] con [Cielo], máxima [Max]°C, mínima [Min]°C. Viento [Dir] [Vel]-[Raf] km/h. #SanMartínDeLosAndes #ClimaSMA
    
    2. Al final agrega una 'SÍNTESIS DIARIA' narrativa de 4 líneas (Estilo AIC).
    """
    
    resultado = consultar_openrouter(prompt, modelos_disponibles)
    
    if resultado:
        return resultado
    else:
        return "⚠️ Todas las IAs de OpenRouter fallaron. Revisa tu conexión o créditos."

# --- INTERFAZ ---
st.sidebar.title("Fuentes")
sel_aic = st.sidebar.checkbox("AIC (PDF)", value=True)
sel_om = st.sidebar.checkbox("Open-Meteo", value=True)

if st.button("🚀 GENERAR PRONÓSTICO PONDERADO"):
    data_final = {}
    if sel_aic: data_final["AIC"] = get_aic_data()
    if sel_om: data_final["OpenMeteo"] = get_open_meteo_data()
    
    with st.spinner("Ponderando datos entre múltiples IAs..."):
        reporte = generar_reporte_ponderado(data_final)
        
    st.subheader("📍 Resultado Ponderado Unificado")
    st.info(reporte)
    st.text_area("Copia el reporte aquí:", value=reporte, height=350)
