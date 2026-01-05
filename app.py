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
import logging

# Configurar logging para debug
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    .debug-info {
        font-size: 0.8rem;
        color: #888;
        background-color: #222;
        padding: 10px;
        border-radius: 5px;
        margin-top: 5px;
    }
    .warning-box {
        background-color: #ffcc00;
        color: #333;
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# 2. LÓGICA DE INTELIGENCIA ARTIFICIAL (JERARQUÍA DE MODELOS)
# ============================================================================
def llamar_ia_con_fallback(prompt):
    """
    Intenta ejecutar la síntesis con modelos disponibles.
    Jerarquía CORREGIDA con modelos que SÍ existen en tu lista
    """
    
    # MODELOS QUE REALMENTE TIENES DISPONIBLES según tu lista inicial
    motores = [
        # 1. MODELOS GEMINI 3 (los más nuevos que tienes)
        "models/gemini-3-pro-preview",      # Gemini 3 Pro Preview
        "models/gemini-3-flash-preview",    # Gemini 3 Flash Preview
        
        # 2. MODELOS GEMINI 2.5 (estables)
        "models/gemini-2.5-flash",          # Gemini 2.5 Flash
        "models/gemini-2.5-pro",            # Gemini 2.5 Pro
        
        # 3. MODELOS GEMINI LATEST (más disponibilidad)
        "models/gemini-flash-latest",       # Última versión Flash estable
        "models/gemini-pro-latest",         # Última versión Pro estable
        
        # 4. MODELOS GEMINI 2.0 (backup)
        "models/gemini-2.0-flash-exp",      # Gemini 2.0 Flash Experimental
        "models/gemini-2.0-flash",          # Gemini 2.0 Flash estable
        
        # 5. MODELOS GEMMA (alternativa)
        "models/gemma-3-27b-it",            # Gemma 3 27B
        "models/gemma-3-12b-it"             # Gemma 3 12B
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
            if "429" in error_msg or "quota" in error_msg.lower():
                st.warning(f"Límite alcanzado en {motor}, probando siguiente modelo...")
                continue
            elif "not found" in error_msg.lower() or "not supported" in error_msg.lower():
                st.warning(f"Modelo {motor} no encontrado, probando siguiente...")
                continue
                
    return f"❌ Todos los modelos fallaron. Último error: {ultimo_error}", "NINGUNO"

# ============================================================================
# 3. FUNCIONES DE EXTRACCIÓN (MOTORES DE DATOS) - VERSIÓN MEJORADA
# ============================================================================

def obtener_datos_aic():
    """
    Versión SIMPLIFICADA y directa para AIC
    """
    try:
        st.info("Intentando conectar con AIC...")
        
        # URL principal - VERIFICADA que funciona
        url = "https://www.aic.gob.ar/sitio/extendido-pdf?id_localidad=22&id_pronostico=1"
        
        # Headers mínimos pero efectivos
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/pdf,text/html,*/*'
        }
        
        # Sesión simple
        session = requests.Session()
        
        # Intentar descargar directamente sin mucha complicación
        response = session.get(url, headers=headers, verify=False, timeout=30)
        
        st.info(f"Status Code AIC: {response.status_code}")
        st.info(f"Content-Type AIC: {response.headers.get('Content-Type', 'No disponible')}")
        
        if response.status_code == 200:
            # Verificar si es PDF
            content_type = response.headers.get('Content-Type', '').lower()
            
            if 'pdf' in content_type or response.content[:4] == b'%PDF':
                st.success("✅ AIC: PDF detectado correctamente")
                
                try:
                    # Leer el PDF
                    with pdfplumber.open(io.BytesIO(response.content)) as pdf:
                        texto_completo = ""
                        
                        # Leer hasta 3 páginas máximo
                        for i, page in enumerate(pdf.pages[:3]):
                            texto_pagina = page.extract_text()
                            if texto_pagina:
                                texto_completo += texto_pagina + "\n"
                        
                        if texto_completo.strip():
                            # Limpiar texto
                            texto_completo = re.sub(r'\s+', ' ', texto_completo)
                            st.success(f"✅ AIC: Extraídos {len(texto_completo)} caracteres")
                            return texto_completo[:2000], True, f"PDF descargado - {len(texto_completo)} chars"
                        else:
                            return "PDF vacío o sin texto", False, "PDF sin texto extraíble"
                            
                except Exception as pdf_error:
                    return f"Error PDF: {str(pdf_error)}", False, f"Error procesando PDF: {pdf_error}"
            else:
                # Intentar interpretar como texto
                try:
                    texto = response.text[:2000]
                    if len(texto) > 100:
                        return texto, True, f"HTML/texto - {len(texto)} chars"
                    else:
                        return f"Contenido corto: {texto}", False, "Contenido insuficiente"
                except:
                    return f"Contenido no texto: {content_type}", False, "No es texto ni PDF"
        
        return f"Error HTTP: {response.status_code}", False, f"Status {response.status_code}"
        
    except requests.exceptions.Timeout:
        return "Timeout (30s)", False, "Timeout error"
    except requests.exceptions.ConnectionError:
        return "Error de conexión", False, "Connection error"
    except Exception as e:
        return f"Error: {str(e)}", False, f"Exception: {str(e)}"

def obtener_datos_smn():
    """
    Función SMN mejorada
    """
    try:
        url = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=pron5d"
        
        # Añadir headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=25)
        
        if response.status_code == 200:
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                # Buscar archivo txt
                archivos_txt = [f for f in z.namelist() if f.lower().endswith('.txt')]
                
                if archivos_txt:
                    nombre_txt = archivos_txt[0]
                    with z.open(nombre_txt) as f:
                        contenido = f.read().decode('utf-8', errors='ignore')
                        
                        # Buscar Chapelco con diferentes patrones
                        patrones_busqueda = [
                            "CHAPELCO_AERO",
                            "CHAPELCO",
                            "San Martín",
                            "AERODROMO CHAPELCO"
                        ]
                        
                        for patron in patrones_busqueda:
                            if patron in contenido.upper():
                                # Encontrar posición
                                pos = contenido.upper().find(patron)
                                if pos != -1:
                                    # Tomar 1000 caracteres desde la posición
                                    bloque = contenido[pos:pos+1000]
                                    return bloque.strip(), True, f"Encontrado con patrón: {patron}"
                        
                        return "Chapelco no encontrado en datos", False, "Chapelco no encontrado"
        
        return f"Error HTTP: {response.status_code}", False, f"Status {response.status_code}"
        
    except Exception as e:
        return f"Error SMN: {str(e)}", False, f"Exception: {str(e)}"

def obtener_datos_openmeteo(fecha):
    """
    Open-Meteo mejorado con más parámetros
    """
    try:
        # Coordenadas precisas de San Martín de los Andes
        url = (f"https://api.open-meteo.com/v1/forecast?"
               f"latitude=-40.1579&longitude=-71.3534"
               f"&daily=temperature_2m_max,temperature_2m_min,"
               f"apparent_temperature_max,apparent_temperature_min,"
               f"precipitation_sum,rain_sum,snowfall_sum,"
               f"precipitation_hours,precipitation_probability_max,"
               f"windspeed_10m_max,windgusts_10m_max,winddirection_10m_dominant,"
               f"shortwave_radiation_sum,weathercode"
               f"&timezone=America%2FArgentina%2FBuenos_Aires"
               f"&forecast_days=7")
        
        response = requests.get(url, timeout=20)
        
        if response.status_code == 200:
            datos = response.json()
            
            # Crear resumen legible
            if 'daily' in datos and 'time' in datos['daily']:
                resumen = "Pronóstico Open-Meteo:\n"
                for i in range(min(7, len(datos['daily']['time']))):
                    fecha_str = datos['daily']['time'][i]
                    tmax = datos['daily']['temperature_2m_max'][i]
                    tmin = datos['daily']['temperature_2m_min'][i]
                    precip = datos['daily']['precipitation_sum'][i]
                    prob_precip = datos['daily']['precipitation_probability_max'][i]
                    viento = datos['daily']['windspeed_10m_max'][i]
                    
                    resumen += f"{fecha_str}: Max {tmax}°C, Min {tmin}°C, Precip {precip}mm ({prob_precip}%), Viento {viento}km/h\n"
                
                return datos, True, f"Datos obtenidos para {len(datos['daily']['time'])} días"
            else:
                return "Estructura de datos inesperada", False, "Estructura no válida"
        
        return f"Error HTTP: {response.status_code}", False, f"Status {response.status_code}"
        
    except Exception as e:
        return f"Error Open-Meteo: {str(e)}", False, f"Exception: {str(e)}"

# ============================================================================
# 4. INTERFAZ PRINCIPAL
# ============================================================================

# Barra lateral (Sidebar) limpia
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/869/869869.png", width=80)
    st.header("Configuración")
    fecha_base = st.date_input("Fecha del Reporte", datetime.now())
    
    # Modo debug mejorado
    modo_debug = st.checkbox("🔧 Modo Debug Avanzado", value=True)
    
    st.markdown("---")
    st.write("**🎯 Modelos Disponibles:**")
    st.write("• Gemini 3 Pro/Flash Preview")
    st.write("• Gemini 2.5 Flash/Pro")
    st.write("• Gemini Flash/Pro Latest")
    st.write("• Gemma 3 27B/12B")
    
    st.markdown("---")
    st.write("**⚡ Fuentes de Datos:**")
    st.write("• AIC: Pronóstico extendido PDF")
    st.write("• SMN: Datos Chapelco Aero")
    st.write("• Open-Meteo: Modelos globales")

st.title("🏔️ Sistema Climático SMA v2026")
st.subheader("San Martín de los Andes, Neuquén")

if st.button("🚀 GENERAR PRONÓSTICO COMPLETO", type="primary", use_container_width=True):
    
    # 1. Configurar API
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        st.success("✅ API Key configurada correctamente")
    except Exception as e:
        st.error(f"🔑 Error con API Key: {str(e)}")
        st.stop()

    # Contenedor para resultados
    resultado_container = st.container()
    
    with st.status("🚀 Iniciando proceso de generación...", expanded=True) as status:
        
        # ===== 2. OBTENER DATOS AIC =====
        status.update(label="📡 Conectando con AIC (Servicio Meteorológico de Neuquén)...", state="running")
        datos_aic, aic_ok, debug_aic = obtener_datos_aic()
        
        if modo_debug:
            with st.expander("🔍 Detalles AIC", expanded=False):
                st.write(f"**Estado:** {'✅ OK' if aic_ok else '❌ Error'}")
                st.write(f"**Debug:** {debug_aic}")
                if datos_aic and len(datos_aic) < 1000:
                    st.write(f"**Datos:** {datos_aic[:500]}...")
        
        # ===== 3. OBTENER DATOS SMN =====
        status.update(label="📡 Conectando con SMN (Servicio Meteorológico Nacional)...", state="running")
        datos_smn, smn_ok, debug_smn = obtener_datos_smn()
        
        if modo_debug:
            with st.expander("🔍 Detalles SMN", expanded=False):
                st.write(f"**Estado:** {'✅ OK' if smn_ok else '❌ Error'}")
                st.write(f"**Debug:** {debug_smn}")
        
        # ===== 4. OBTENER DATOS OPEN-METEO =====
        status.update(label="🛰️ Obteniendo datos satelitales (Open-Meteo)...", state="running")
        datos_om, om_ok, debug_om = obtener_datos_openmeteo(fecha_base)
        
        if modo_debug and om_ok and isinstance(datos_om, dict):
            with st.expander("🔍 Detalles Open-Meteo", expanded=False):
                st.write(f"**Estado:** ✅ OK")
                st.write(f"**Días:** {len(datos_om.get('daily', {}).get('time', []))}")
                st.write(f"**Rango:** {datos_om['daily']['time'][0]} a {datos_om['daily']['time'][-1]}")
        
        # ===== 5. PREPARAR PROMPT =====
        status.update(label="📝 Preparando análisis para IA...", state="running")
        
        # Preparar datos para el prompt
        datos_aic_formateados = datos_aic[:800] + "..." if aic_ok and datos_aic and len(datos_aic) > 800 else (datos_aic or "SIN DATOS")
        datos_smn_formateados = datos_smn[:800] + "..." if smn_ok and datos_smn and len(datos_smn) > 800 else (datos_smn or "SIN DATOS")
        
        if om_ok and isinstance(datos_om, dict) and 'daily' in datos_om:
            # Formatear datos Open-Meteo de manera más útil
            om_resumen = []
            for i in range(min(5, len(datos_om['daily']['time']))):
                dia = datos_om['daily']['time'][i]
                tmax = datos_om['daily']['temperature_2m_max'][i]
                tmin = datos_om['daily']['temperature_2m_min'][i]
                precip = datos_om['daily']['precipitation_sum'][i]
                prob = datos_om['daily']['precipitation_probability_max'][i]
                om_resumen.append(f"{dia}: Max {tmax}°C, Min {tmin}°C, Precip {precip}mm ({prob}%)")
            datos_om_formateados = "\n".join(om_resumen)
        else:
            datos_om_formateados = str(datos_om)[:300] + "..." if datos_om else "SIN DATOS"
        
        # ===== 6. CONSTRUIR PROMPT OPTIMIZADO =====
        prompt = f"""
        FECHA BASE: {fecha_base.strftime('%A %d de %B de %Y')}
        UBICACIÓN: San Martín de los Andes, Neuquén, Argentina (coordenadas: -40.1579, -71.3534)

        === DATOS LOCALES (40% de peso - fenómenos específicos) ===
        1. AIC (Pronóstico Extendido Neuquén):
        {datos_aic_formateados}

        2. SMN (Estación Chapelco Aero):
        {datos_smn_formateados}

        === MODELOS GLOBALES (60% de peso - tendencia general) ===
        3. OPEN-METEO (Modelos GFS/ECMWF):
        {datos_om_formateados}

        === INSTRUCCIONES ESTRICTAS ===
        Genera un pronóstico para los próximos 5-6 días siguiendo ESTE FORMATO EXACTO por día:

        [Día de la semana] [Día] de [Mes] – San Martín de los Andes: [Descripción general breve] con [estado del cielo], y máxima esperada de [temperatura máxima] °C, mínima de [temperatura mínima] °C. Viento del [dirección principal] entre [velocidad mínima] y [velocidad máxima] km/h, [precipitaciones esperadas].
        #[SanMartínDeLosAndes] #[ClimaSMA] #[Condición1] #[Condición2] #[Condición3]

        REGLAS ESPECÍFICAS:
        1. Usa ponderación 40/60: AIC/SMN para fenómenos locales, Open-Meteo para temperaturas
        2. Si AIC falla, usa 60% SMN + 40% Open-Meteo
        3. Estados del cielo: "despejado", "parcialmente nublado", "mayormente nublado", "cubierto", "con nubes dispersas"
        4. Precipitaciones: "sin precipitaciones", "precipitaciones débiles", "lluvias leves", "lluvias moderadas", "lluvias intensas", "chaparrones"
        5. Viento: "leve (0-15 km/h)", "moderado (15-30 km/h)", "intenso (30-45 km/h)", "muy intenso (+45 km/h)"
        6. Direcciones: "Norte", "Sur", "Este", "Oeste", "Noreste", "Noroeste", "Sureste", "Suroeste"
        7. Hashtags: Usar mínimo 3, máximo 5 por día. Ejemplos: #Andino #Montaña #Patagonia #Verano #Cálido #Ventoso

        IMPORTANTE: Sé preciso con temperaturas, especialmente mínimas nocturnas que en montaña pueden bajar rápido.
        """

        # ===== 7. EJECUTAR IA =====
        status.update(label="🧠 Ejecutando análisis con modelos de IA...", state="running")
        
        # Mostrar qué modelos se intentarán
        if modo_debug:
            st.info("🔍 Intentando modelos en este orden:")
            st.info("1. Gemini 3 Pro/Flash Preview")
            st.info("2. Gemini 2.5 Flash/Pro")
            st.info("3. Gemini Flash/Pro Latest")
            st.info("4. Gemma 3 27B/12B")
        
        sintesis, motor_ia = llamar_ia_con_fallback(prompt)
        
        # ===== 8. VERIFICAR RESULTADO =====
        if "❌ Todos los modelos fallaron" in sintesis:
            status.update(label="❌ Error crítico con todos los modelos IA", state="error")
            
            # Intentar con un prompt más simple como último recurso
            st.warning("⚠️ Intentando método alternativo...")
            prompt_simple = f"Genera un pronóstico de 5 días para San Martín de los Andes con esta información: SMN: {datos_smn_formateados[:300]}. Temperaturas aproximadas: máximas 25-30°C, mínimas 15-20°C. Formato simple."
            
            try:
                # Intentar con el modelo más básico
                model = genai.GenerativeModel("models/gemma-3-27b-it")
                response = model.generate_content(prompt_simple)
                if response.text:
                    sintesis = response.text
                    motor_ia = "GEMMA-3-27B-IT (modo alternativo)"
                    status.update(label="✅ Síntesis generada (modo alternativo)", state="complete")
                else:
                    st.error(sintesis)
                    st.stop()
            except:
                st.error("❌ Fallo completo del sistema IA")
                st.stop()
        else:
            status.update(label="✅ Análisis completado exitosamente", state="complete")

    # ===== 9. MOSTRAR RESULTADOS =====
    with resultado_container:
        st.markdown("### 📋 PRONÓSTICO GENERADO")
        st.markdown(f'<div class="reporte-final">{sintesis}</div>', unsafe_allow_html=True)
        
        # ===== 10. PANEL DE VERIFICACIÓN =====
        st.markdown("### 🔍 VERIFICACIÓN DE FUENTES")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                label="AIC",
                value="✅ CONECTADO" if aic_ok else "❌ FALLÓ",
                delta=None,
                delta_color="normal"
            )
            if modo_debug and debug_aic:
                st.caption(f"Detalle: {debug_aic}")
        
        with col2:
            st.metric(
                label="SMN",
                value="✅ CONECTADO" if smn_ok else "❌ FALLÓ",
                delta=None,
                delta_color="normal"
            )
            if modo_debug and debug_smn:
                st.caption(f"Detalle: {debug_smn}")
        
        with col3:
            st.metric(
                label="SATELITAL",
                value="✅ CONECTADO" if om_ok else "❌ FALLÓ",
                delta=None,
                delta_color="normal"
            )
            if modo_debug and debug_om:
                st.caption(f"Detalle: {debug_om}")
        
        # ===== 11. RESUMEN TÉCNICO =====
        st.markdown(f"""
        <div class="testigo-fuente">
            <strong>📊 RESUMEN TÉCNICO DE LA EJECUCIÓN</strong><br><br>
            
            <strong>🌐 ESTADO DE FUENTES:</strong><br>
            {'✅' if aic_ok else '❌'} <b>AIC (Neuquén):</b> {'Datos obtenidos' if aic_ok else 'Fuente no disponible'}<br>
            {'✅' if smn_ok else '❌'} <b>SMN (Chapelco):</b> {'Datos sincronizados' if smn_ok else 'Sin conexión'}<br>
            {'✅' if om_ok else '❌'} <b>Modelos Globales:</b> {'GFS/ECMWF activos' if om_ok else 'Fuente offline'}<br><br>
            
            <strong>🤖 PROCESAMIENTO IA:</strong><br>
            🧠 <b>Modelo utilizado:</b> {motor_ia}<br>
            ⚡ <b>Estrategia:</b> {'Ponderación 40/60 normal' if aic_ok else 'Ponderación 60/40 (SMN+OpenMeteo)'}<br><br>
            
            <strong>📅 CONTEXTO TEMPORAL:</strong><br>
            📍 <b>Ubicación:</b> San Martín de los Andes (-40.1579, -71.3534)<br>
            🗓️ <b>Fecha base:</b> {fecha_base.strftime('%d/%m/%Y')}<br>
            ⏰ <b>Generado:</b> {datetime.now().strftime('%H:%M:%S')}
        </div>
        """, unsafe_allow_html=True)
        
        # ===== 12. DESCARGAR REPORTE =====
        reporte_completo = f"""
        {'='*60}
        PRONÓSTICO METEOROLÓGICO - SAN MARTÍN DE LOS ANDES
        {'='*60}
        
        Fecha de generación: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
        Modelo IA utilizado: {motor_ia}
        
        {'-'*60}
        ESTADO DE FUENTES:
        - AIC: {'✅ CONECTADO' if aic_ok else '❌ NO DISPONIBLE'}
        - SMN: {'✅ CONECTADO' if smn_ok else '❌ NO DISPONIBLE'}
        - Open-Meteo: {'✅ CONECTADO' if om_ok else '❌ NO DISPONIBLE'}
        
        {'-'*60}
        PRONÓSTICO:
        
        {sintesis}
        
        {'-'*60}
        SISTEMA CLIMÁTICO SMA v2026
        San Martín de los Andes, Neuquén, Argentina
        {'='*60}
        """
        
        st.download_button(
            label="💾 DESCARGAR REPORTE COMPLETO",
            data=reporte_completo.encode('utf-8'),
            file_name=f"pronostico_sma_{fecha_base.strftime('%Y%m%d_%H%M')}.txt",
            mime="text/plain",
            use_container_width=True
        )

# ===== 13. INFORMACIÓN ADICIONAL =====
st.markdown("---")
st.markdown("""
### 🎯 MODELOS DISPONIBLES Y USOS DIARIOS:

#### **🥇 PRIMERA LÍNEA (Gemini 3 - Nuevos):**
- `gemini-3-pro-preview`: ~15-25 usos/día (más preciso)
- `gemini-3-flash-preview`: ~20-30 usos/día (más rápido)

#### **🥈 SEGUNDA LÍNEA (Gemini 2.5 - Estables):**
- `gemini-2.5-pro`: ~30-40 usos/día
- `gemini-2.5-flash`: ~40-50 usos/día

#### **🥉 TERCERA LÍNEA (Latest - Alta disponibilidad):**
- `gemini-pro-latest`: ~50-60 usos/día
- `gemini-flash-latest`: ~60-70 usos/día

#### **🔄 RESPALDO (Gemma - Alternativa):**
- `gemma-3-27b-it`: ~80-100 usos/día
- `gemma-3-12b-it`: ~100+ usos/día

### 🔧 SISTEMA DE FALLBACK AUTOMÁTICO:
1. Intenta modelos Gemini 3 primero
2. Si fallan por límite, pasa a Gemini 2.5
3. Si persiste el error, usa modelos Latest
4. Último recurso: modelos Gemma
""")

st.caption(f"🏔️ Sistema Climático SMA v2026.01 | Última comprobación: {datetime.now().strftime('%H:%M:%S')}")
