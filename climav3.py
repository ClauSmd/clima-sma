import streamlit as st
import requests
import pdfplumber
import io
import json

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Weather Aggregator SMA", layout="wide")

# --- FUNCIONES DE EXTRACCIÓN (AIC y OpenMeteo se mantienen igual) ---
# [Asumimos las funciones get_aic_data y get_open_meteo_data definidas anteriormente]

def generar_sintesis_ia(data_payload):
    api_key = st.secrets.get("OPENROUTER_API_KEY")
    if not api_key: return "Error: API Key no configurada."
    
    # PROMPT MEJORADO PARA COPIAR EL ESTILO DE LAS CAPTURAS
    prompt = f"""
    Eres un meteorólogo de San Martín de los Andes. 
    Analiza estos datos (OpenMeteo 50%, AIC 50%): {json.dumps(data_payload)}
    
    INSTRUCCIONES DE SALIDA:
    1. Primero, genera el reporte diario para 5 días EXACTAMENTE con este estilo (uno debajo del otro):
       [Día de la semana] [Día] de [Mes] – San Martín de los Andes: [Condición] con [Cielo], y máxima esperada de [Max] °C, mínima de [Min] °C. Viento del [Dir] entre [Vel] y [Raf] km/h, [Lluvias]. #SanMartínDeLosAndes #ClimaSMA #[HashtagCondicion]
    
    2. Al final, escribe una SÍNTESIS DIARIA ÚNICA de 4 a 5 líneas que unifique el análisis general de la región (estilo narrativo AIC).
    
    RECUERDA: Los valores de Max, Min y Viento deben ser el PROMEDIO de las fuentes enviadas.
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
        return "Error en la conexión con la IA."

# --- INTERFAZ ---
st.sidebar.title("Fuentes de Análisis")
sel_aic = st.sidebar.checkbox("AIC (PDF)", value=True)
sel_om = st.sidebar.checkbox("Open-Meteo (API)", value=True)

st.title("🌤️ Reporte Meteorológico SMA")

if st.button("🚀 GENERAR PRONÓSTICO UNIFICADO"):
    data_final = {}
    with st.spinner("Ponderando datos..."):
        if sel_aic: data_final["AIC"] = get_aic_data() # Esta función debe estar definida arriba
        if sel_om: data_final["OpenMeteo"] = get_open_meteo_data()

        # RESULTADO PONDERADO
        reporte = generar_sintesis_ia(data_final)
        
        st.subheader("📍 Resultado Ponderado Unificado")
        st.info(reporte) # El componente 'info' le da un fondo similar a tus capturas
        
        # BOTÓN PARA COPIAR
        st.text_area("Copia el reporte aquí:", value=reporte, height=300)

    st.divider()
    # DESGLOSE INDIVIDUAL (Sección inferior para comparar)
    st.subheader("🔍 Datos Originales por Fuente")
    c1, c2 = st.columns(2)
    with c1: 
        st.markdown("**AIC (Crudo)**")
        st.write(data_final.get("AIC"))
    with c2: 
        st.markdown("**Open-Meteo (Crudo)**")
        st.write(data_final.get("OpenMeteo"))
