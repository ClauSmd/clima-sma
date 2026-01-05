import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime, timedelta
import zipfile
import io
import re
import pdfplumber
import urllib3
import pandas as pd

# Deshabilitar warnings de SSL para AIC
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================================================
# 1. CONFIGURACIÓN DE PÁGINA Y ESTILO
# ============================================================================
st.set_page_config(page_title="Sistema Climático SMA v2026", page_icon="🏔️", layout="wide")

st.markdown("""
<style>
    .reporte-final { 
        background-color: #1e1e1e; 
        padding: 30px; 
        border-radius: 15px; 
        font-size: 1.15rem; 
        line-height: 1.7; 
        color: #f0f2f6; 
        border: 1px solid #444; 
        white-space: pre-wrap;
        font-family: 'Helvetica Neue', sans-serif;
    }
    .testigo-fuente { 
        font-size: 0.9rem; 
        color: #aaa; 
        margin-top: 25px; 
        padding: 20px;
        background-color: #121212;
        border-radius: 10px;
        border-left: 5px solid #4CAF50;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# 2. LÓGICA DE INTELIGENCIA ARTIFICIAL (JERARQUÍA DE MODELOS)
# ============================================================================
def llamar_ia_con_fallback(prompt):
    """
    Intenta ejecutar la síntesis con modelos disponibles.
    Jerarquía: 1) Más nuevo y rápido → 2) Moderadamente nuevo → 3) Muchos usos
    """
    
    motores = [
        # 1. MÁS NUEVO Y RÁPIDO (20-30 usos/día aprox.)
        "models/gemini-3-flash-preview",
        
        # 2. MEDIANAMENTE NUEVOS (30-40 usos/día cada uno aprox.)
        "models/gemini-2.5-flash",
        "models/gemini-2.5-pro",
        
        # 3. MUCHOS USOS pero no tan viejo (50+ usos/día)
        "models/gemini-flash-latest",
        
        # 4. ALTERNATIVAS DE RESPALDO
        "models/gemini-2.0-flash-exp",
        "models/gemini-2.0-flash",
        "models/gemma-3-27b-it"
    ]
    
    ultimo_error = ""
    for motor in motores:
        try:
            model = genai.GenerativeModel(motor)
            response = model.generate_content(prompt)
            if response.text:
                return response.text, motor.replace("models/", "").upper()
        except Exception as e:
            error_msg = str(e)
            ultimo_error = f"Modelo {motor}: {error_msg}"
            
            # Si es error de límite (429) o modelo no encontrado, continuar
            if "429" in error_msg or "quota" in error_msg.lower() or "not found" in error_msg.lower():
                continue
                
    return f"❌ Todos los modelos fallaron. Último error: {ultimo_error}", "NINGUNO"

# ============================================================================
# 3. FUNCIONES DE EXTRACCIÓN (MOTORES DE DATOS)
# ============================================================================

def obtener_datos_aic():
    try:
        # URL disparadora del pronóstico extendido
        url = "https://www.aic.gob.ar/sitio/extendido-pdf?id_localidad=22&id_pronostico=1"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        session = requests.Session()
        session.get("https://www.aic.gob.ar", headers=headers, verify=False, timeout=10)
        r = session.get(url, headers=headers, verify=False, timeout=30)
        if r.content.startswith(b'%PDF'):
            with pdfplumber.open(io.BytesIO(r.content)) as pdf:
                return pdf.pages[0].extract_text(), True
        return None, False
    except Exception as e:
        return f"Error AIC: {str(e)}", False

def obtener_datos_smn():
    try:
        url = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=pron5d"
        r = requests.get(url, timeout=15)
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            nombre_txt = [f for f in z.namelist() if f.endswith('.txt')][0]
            with z.open(nombre_txt) as f:
                contenido = f.read().decode('utf-8', errors='ignore')
                if "CHAPELCO_AERO" in contenido:
                    # Extraer solo el bloque relevante
                    bloque = contenido.split("CHAPELCO_AERO")[1]
                    # Tomar hasta el próximo bloque de estación o 500 caracteres
                    siguiente = bloque.find("NOMBRE_ESTACION")
                    if siguiente > 0:
                        bloque = bloque[:siguiente]
                    return bloque[:500].strip(), True
        return None, False
    except Exception as e:
        return f"Error SMN: {str(e)}", False

def obtener_datos_openmeteo(fecha):
    try:
        # Modelo global satelital para San Martín de los Andes
        url = (f"https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35"
               f"&daily=temperature_2m_max,temperature_2m_min,windspeed_10m_max,precipitation_sum,weathercode"
               f"&timezone=America%2FArgentina%2FBuenos_Aires"
               f"&start_date={fecha}&end_date={(fecha + timedelta(days=5)).strftime('%Y-%m-%d')}")
        res = requests.get(url, timeout=15).json()
        return res, True
    except Exception as e:
        return f"Error Open-Meteo: {str(e)}", False

# ============================================================================
# 4. INTERFAZ PRINCIPAL
# ============================================================================

# Barra lateral (Sidebar) limpia: Solo controles esenciales
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/869/869869.png", width=80)
    st.header("Configuración")
    fecha_base = st.date_input("Fecha del Reporte", datetime.now())
    st.markdown("---")
    st.write("**📊 Jerarquía de Modelos:**")
    st.write("1. 🥇 Gemini 3 Flash (Nuevo/Rápido)")
    st.write("2. 🥈 Gemini 2.5 Flash/Pro")
    st.write("3. 🥉 Gemini Flash Latest (Muchos usos)")
    st.markdown("---")
    st.write("**⚖️ Lógica aplicada:**")
    st.write("🔹 40% AIC/SMN (Local)")
    st.write("🔹 60% Satelital (Global)")

st.title("🏔️ Generador de Síntesis Meteorológica SMA")
st.subheader("San Martín de los Andes, Neuquén")

if st.button("🚀 GENERAR PRONÓSTICO COMPLETO", type="primary", use_container_width=True):
    
    # 1. Configurar API
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    except:
        st.error("🔑 Error: No se encontró la API Key en Streamlit Secrets.")
        st.stop()

    with st.status("Sincronizando fuentes oficiales y modelos...") as status:
        # 2. Captura de datos en paralelo
        status.update(label="📡 Conectando con AIC...", state="running")
        datos_aic, aic_ok = obtener_datos_aic()
        
        status.update(label="📡 Conectando con SMN...", state="running")
        datos_smn, smn_ok = obtener_datos_smn()
        
        status.update(label="🛰️ Obteniendo datos satelitales...", state="running")
        datos_om, om_ok = obtener_datos_openmeteo(fecha_base)
        
        status.update(label="🧠 Analizando datos con IA...", state="running")
        
        # 3. Prompt con tu Estructura de Memoria y Ponderación 40/60
        prompt = f"""
        FECHA DE REFERENCIA: {fecha_base.strftime('%A %d de %B de %Y')}
        LUGAR: San Martín de los Andes, Neuquén, Argentina.

        FUENTES OFICIALES (PONDERACIÓN 40% - PRIORIDAD EN ALERTAS):
        - AIC (Pronóstico Extendido PDF): {datos_aic if aic_ok else 'SIN DATOS'}
        - SMN (Estación Chapelco Aero): {datos_smn if smn_ok else 'SIN DATOS'}

        MODELO GLOBAL SATELITAL (PONDERACIÓN 60% - TENDENCIA):
        - Open-Meteo (GFS/ECMWF): {str(datos_om)[:500] if om_ok else 'SIN DATOS'}

        INSTRUCCIONES PARA LA SÍNTESIS:
        1. Generá el pronóstico para los próximos 5-6 días comenzando desde la fecha de referencia.
        2. Usá la ponderación 40/60: 
           - Los datos locales (AIC/SMN) definen fenómenos específicos (lluvia, tormenta, ráfagas, alertas)
           - El modelo global ajusta la curva de temperatura y tendencia general
        3. Formato obligatorio por cada día (mantener hashtags exactamente):
        [Día de la semana] [Día] de [Mes] – San Martín de los Andes: [condiciones generales] con [cielo], y máxima esperada de [temperatura máxima] °C, mínima de [temperatura mínima] °C. Viento del [dirección] entre [vel_min] y [vel_max] km/h, [lluvias previstas].
        #[Lugar] #ClimaSMA #[Condición1] #[Condición2] #[Condición3]
        ---
        4. Sé específico con condiciones:
           - "parcialmente nublado", "mayormente despejado", "cubierto"
           - "precipitaciones débiles", "lluvias moderadas", "sin precipitaciones"
           - "viento leve", "viento moderado", "ráfagas intensas"
        5. Incluye hashtags relevantes como: #Andino #Montaña #Patagonia según corresponda
        6. Si hay datos contradictorios, prioriza los locales (AIC/SMN) para fenómenos puntuales.
        """

        # 4. Ejecución con Jerarquía de Modelos
        sintesis, motor_ia = llamar_ia_con_fallback(prompt)
        
        if "❌ Todos los modelos fallaron" in sintesis:
            status.update(label="❌ Error crítico en IA", state="error")
            st.error(sintesis)
            st.stop()
        else:
            status.update(label="✅ Síntesis generada exitosamente", state="complete")

    # 5. RESULTADO FINAL (Pantalla principal)
    st.markdown("### 📋 Pronóstico Generado")
    st.markdown(f'<div class="reporte-final">{sintesis}</div>', unsafe_allow_html=True)

    # 6. TESTIGO DE VERDAD (Leyenda de fuentes al final)
    st.markdown("### 🔍 Testigo de Fuentes")
    st.markdown(f"""
    <div class="testigo-fuente">
        <strong>📊 Métricas de esta ejecución:</strong><br><br>
        
        <strong>🌐 Fuentes de datos:</strong><br>
        {'✅' if aic_ok else '❌'} <b>AIC:</b> {'Sincronizado' if aic_ok else 'No disponible'}<br>
        {'✅' if smn_ok else '❌'} <b>SMN:</b> {'Sincronizado (Chapelco Aero)' if smn_ok else 'No disponible'}<br>
        {'✅' if om_ok else '❌'} <b>Modelos Satelitales:</b> {'GFS/ECMWF activos' if om_ok else 'No disponible'}<br><br>
        
        <strong>🤖 Motor de IA utilizado:</strong><br>
        🧠 <b>{motor_ia}</b><br>
        <small>Jerarquía aplicada: 1) Gemini 3 → 2) Gemini 2.5 → 3) Flash Latest</small><br><br>
        
        <strong>⚖️ Ponderación aplicada:</strong><br>
        🔹 <b>40%</b> Fuentes locales (AIC/SMN) - Fenómenos específicos<br>
        🔹 <b>60%</b> Modelos globales - Tendencia y temperatura
    </div>
    """, unsafe_allow_html=True)

    # 7. Descarga del reporte
    reporte_completo = f"""
    SÍNTESIS METEOROLÓGICA - SAN MARTÍN DE LOS ANDES
    Fecha de generación: {datetime.now().strftime('%d/%m/%Y %H:%M')}
    Fuente IA: {motor_ia}
    
    {sintesis}
    
    --- METADATOS ---
    Fuentes consultadas:
    - AIC: {'✅' if aic_ok else '❌'}
    - SMN: {'✅' if smn_ok else '❌'} 
    - Open-Meteo: {'✅' if om_ok else '❌'}
    
    Sistema Climático SMA v2026
    """
    
    st.download_button(
        label="📥 Descargar Reporte Completo",
        data=reporte_completo.encode('utf-8'),
        file_name=f"pronostico_sma_{fecha_base.strftime('%Y%m%d')}.txt",
        mime="text/plain"
    )

# Información de pie de página
st.markdown("---")
st.markdown("""
### 📌 Notas Importantes:
1. **Jerarquía de Modelos IA:**
   - **Gemini 3 Flash Preview:** Más nuevo y rápido (~20-30 usos/día)
   - **Gemini 2.5 Flash/Pro:** Balanceado (~30-40 usos/día)
   - **Gemini Flash Latest:** Mayor disponibilidad (50+ usos/día)

2. **Sistema automático:** Si un modelo alcanza su límite diario, pasa al siguiente.

3. **Prioridad de datos:** Los fenómenos locales (tormentas, alertas) vienen de AIC/SMN.
""")

st.caption(f"🏔️ Sistema optimizado para modelos Gemini 3/2.5 | Versión 2026.01 | Última ejecución: {datetime.now().strftime('%H:%M:%S')}")
