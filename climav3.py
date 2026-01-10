import streamlit as st
import requests
import pdfplumber
import io
import json

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Weather Aggregator SMA", layout="wide")

# [Funciones get_aic_data y get_open_meteo_data se mantienen igual para extraer los datos]
# Estas funciones aseguran que se analicen ambas fuentes como en tus capturas

def consultar_ia_extrema(prompt):
    api_key = st.secrets.get("OPENROUTER_API_KEY")
    # LISTA DE MODELOS: Si falla uno, pasa al siguiente automáticamente
    modelos_a_probar = [
        "google/gemini-2.0-flash-exp:free", 
        "meta-llama/llama-3.1-8b-instruct:free", 
        "mistralai/mistral-7b-instruct:free",
        "google/gemini-flash-1.5-8b" # Modelo muy estable de bajo costo/gratis
    ]
    
    for modelo in modelos_a_probar:
        try:
            # Mensaje de progreso para que veas qué modelo está intentando
            st.write(f"🔄 Intentando síntesis con: {modelo.split('/')[-1]}...")
            res = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                data=json.dumps({
                    "model": modelo,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3
                }),
                timeout=20
            )
            data = res.json()
            if "choices" in data:
                return data['choices'][0]['message']['content'], modelo
        except:
            continue # Si falla, el bucle 'for' pasa al siguiente modelo
    return None, None

# --- 2. INTERFAZ ---
st.sidebar.title("Fuentes de Datos")
sel_aic = st.sidebar.checkbox("AIC (PDF)", value=True)
sel_om = st.sidebar.checkbox("Open-Meteo", value=True)

st.title("🌤️ Pronóstico Ponderado SMA")

if st.button("🚀 GENERAR REPORTE"):
    with st.spinner("Ponderando datos (50% AIC / 50% Open-Meteo)..."):
        # Se extraen los datos de ambas fuentes para el análisis ponderado
        d_aic = get_aic_data() if sel_aic else None
        d_om = get_open_meteo_data() if sel_om else None

        # Reducimos los datos para no saturar a la IA
        datos_payload = {
            "AIC": d_aic["datos"] if d_aic else "No disponible",
            "OM": d_om["datos"] if d_om else "No disponible",
            "Sintesis_AIC": d_aic["sintesis"] if d_aic else ""
        }

        # Prompt con el formato idéntico a tus capturas
        prompt = f"""
        Actúa como meteorólogo. Genera el pronóstico ponderado al 50/50 basado en: {json.dumps(datos_payload)}
        
        FORMATO OBLIGATORIO:
        [Día Semana] [Día] de [Mes] – San Martín de los Andes: [Condición] con [Cielo], máxima [Max] °C, mínima [Min] °C. Viento del [Dir] entre [Vel] y [Raf] km/h, [Lluvias]. #SanMartínDeLosAndes #ClimaSMA
        
        SÍNTESIS DIARIA:
        [Un párrafo narrativo analizando la tendencia]
        """

        reporte, modelo_exitoso = consultar_ia_extrema(prompt)
        
        if reporte:
            st.success(f"✅ Reporte generado con éxito usando {modelo_exitoso}")
            st.info(reporte) # Contenedor azulado como en tus capturas
            st.text_area("Copiar para publicar:", value=reporte, height=350)
        else:
            st.error("❌ Todos los modelos de IA fallaron. Verifica tu API Key en los Secrets de Streamlit.")
