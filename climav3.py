import streamlit as st
import requests
import pdfplumber
import io
import json
import google.generativeai as genai
from datetime import datetime

# --- 1. CONFIGURACIÓN Y MODELOS ---
st.set_page_config(page_title="Weather Aggregator SMA", layout="wide")

# Configuración de modelos según tu prioridad y acceso en AI Studio
MODELOS_PRIORIDAD = [
    "gemini-3-flash", 
    "gemini-2.5-flash", 
    "gemini-2.5-flash-lite", 
    "gemini-2.5-flash-native-audio-dialog", 
    "gemma-3-27b"
]

# --- 2. FUNCIONES TÉCNICAS ---

def consultar_gemini_cascada(prompt):
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key:
        return None, "Error: No se encontró GOOGLE_API_KEY en Secrets."
    
    genai.configure(api_key=api_key)
    
    for nombre_modelo in MODELOS_PRIORIDAD:
        try:
            model = genai.GenerativeModel(nombre_modelo)
            # Ajuste de seguridad para permitir contenido meteorológico sin filtros
            response = model.generate_content(prompt)
            if response.text:
                return response.text, nombre_modelo
        except Exception as e:
            continue # Si falla (por cuota o error), salta al siguiente
    return None, "Todos los modelos fallaron o agotaron su cuota."

# [Aquí van tus funciones get_aic_data() y get_open_meteo_data() ya optimizadas]

# --- 3. INTERFAZ LATERAL (SIDEBAR) ---
st.sidebar.title("Configuración")
usa_ia = st.sidebar.toggle("Activar Inteligencia Artificial", value=True)
if usa_ia:
    st.sidebar.info("La IA redactará el reporte y promediará los datos.")
else:
    st.sidebar.warning("Modo Manual: El sistema promediará matemáticamente.")

# --- 4. LÓGICA PRINCIPAL ---
st.title("🌤️ Pronóstico Ponderado SMA")

if st.button("🚀 GENERAR REPORTE"):
    d_aic = get_aic_data() # Esta función extrae los datos de la tabla AIC
    d_om = get_open_meteo_data()

    if d_aic["status"] == "OK" and d_om["status"] == "OK":
        
        if usa_ia:
            # --- MODO IA: PROCESAMIENTO CON GEMINI ---
            with st.spinner("IA analizando y ponderando modelos..."):
                prompt = f"""
                Actúa como meteorólogo profesional. Genera el pronóstico ponderado al 50/50.
                DATOS AIC (Día/Noche): {json.dumps(d_aic['datos'])}
                DATOS OPENMETEO: {json.dumps(d_om['datos'])}
                SÍNTESIS AIC: {d_aic['sintesis']}
                
                FORMATO OBLIGATORIO:
                [Día Semana] [Día] de [Mes] – San Martín de los Andes: [Condición] con [Cielo], máxima [Max] °C, mínima [Min] °C. Viento del [Dir] entre [Vel] y [Raf] km/h. #SanMartínDeLosAndes #ClimaSMA
                
                SÍNTESIS DIARIA:
                [Un párrafo narrativo analizando la tendencia basado en la síntesis de la AIC]
                """
                reporte, modelo_usado = consultar_gemini_cascada(prompt)
                
                if reporte:
                    st.success(f"✅ Reporte generado con {modelo_usado}")
                    st.info(reporte)
                else:
                    st.error("La IA no pudo procesar el pedido. Cambiando a modo manual...")
                    usa_ia = False # Fallback automático si la IA falla

        if not usa_ia:
            # --- MODO MANUAL: ESTRUCTURA MATEMÁTICA ---
            st.subheader("📍 Reporte Estructurado (Modo Manual)")
            meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
            dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            
            reporte_final = ""
            # Combinamos datos para no duplicar días (paso de 2 en AIC)
            for i in range(5):
                idx_aic = i * 2
                if idx_aic < len(d_aic['datos']):
                    # Promedio matemático 50/50
                    p_max = (d_aic['datos'][idx_aic]['max'] + d_om['datos'][i]['max']) / 2
                    p_min = (d_aic['datos'][idx_aic]['min'] + d_om['datos'][i]['min']) / 2
                    
                    f_dt = datetime.strptime(d_aic['datos'][idx_aic]['fecha'], "%d-%m-%Y")
                    linea = (f"**{dias_semana[f_dt.weekday()]} {f_dt.day} de {meses[f_dt.month-1]} – San Martín de los Andes:** "
                             f"{d_aic['datos'][idx_aic]['cielo']}, máxima {p_max:.1f} °C, mínima {p_min:.1f} °C. "
                             f"Viento {d_aic['datos'][idx_aic]['dir']} a {d_aic['datos'][idx_aic]['viento']} km/h. "
                             f"#SanMartínDeLosAndes #ClimaSMA\n\n")
                    reporte_final += linea
            
            reporte_final += f"**SÍNTESIS DIARIA:**\n{d_aic['sintesis']}"
            st.info(reporte_final)
            st.text_area("Copiar reporte:", value=reporte_final, height=300)
