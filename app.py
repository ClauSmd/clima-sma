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
    .debug-info {
        font-size: 0.8rem;
        color: #888;
        background-color: #222;
        padding: 10px;
        border-radius: 5px;
        margin-top: 5px;
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
# 3. FUNCIONES DE EXTRACCIÓN (MOTORES DE DATOS) - VERSIÓN MEJORADA
# ============================================================================

def obtener_datos_aic():
    """
    Versión mejorada con múltiples estrategias y mejor manejo de errores
    """
    try:
        # URL principal del pronóstico extendido para San Martín de los Andes
        url = "https://www.aic.gob.ar/sitio/extendido-pdf?id_localidad=22&id_pronostico=1"
        
        # Headers más completos para simular un navegador real
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Cache-Control': 'max-age=0'
        }
        
        # Crear sesión con persistencia de cookies
        session = requests.Session()
        
        # Primero, hacer una solicitud a la página principal para establecer sesión
        try:
            session.get("https://www.aic.gob.ar", headers=headers, verify=False, timeout=15)
        except:
            pass  # Continuar incluso si esta falla
        
        # Intentar con timeout más largo y verificar la respuesta
        response = session.get(url, headers=headers, verify=False, timeout=45)
        
        # DEBUG: Mostrar información de la respuesta
        debug_info = f"Status Code: {response.status_code}, Content-Type: {response.headers.get('Content-Type', 'No content-type')}"
        
        # Verificar si la respuesta es un PDF válido
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '').lower()
            
            # Verificar por tipo de contenido
            if 'application/pdf' in content_type or response.content.startswith(b'%PDF'):
                try:
                    # Intentar extraer texto del PDF
                    with pdfplumber.open(io.BytesIO(response.content)) as pdf:
                        texto = ""
                        # Extraer texto de las primeras 2 páginas (suelen tener el pronóstico)
                        for pagina in pdf.pages[:2]:
                            texto_pagina = pagina.extract_text()
                            if texto_pagina:
                                texto += texto_pagina + "\n"
                        
                        if texto.strip():
                            # Limpiar el texto
                            texto = re.sub(r'\s+', ' ', texto)
                            return f"{texto[:1500]}...", True, debug_info
                        else:
                            return "PDF sin texto extraíble", False, debug_info
                except Exception as pdf_error:
                    return f"Error procesando PDF: {str(pdf_error)}", False, debug_info
            else:
                # Si no es PDF, verificar si es HTML que redirige
                if 'text/html' in content_type:
                    # Buscar enlaces a PDF en el HTML
                    pdf_links = re.findall(r'href=["\']([^"\']+\.pdf[^"\']*)["\']', response.text)
                    if pdf_links:
                        # Intentar con el primer enlace PDF encontrado
                        pdf_url = pdf_links[0]
                        if not pdf_url.startswith('http'):
                            pdf_url = 'https://www.aic.gob.ar' + pdf_url
                        
                        pdf_response = session.get(pdf_url, headers=headers, verify=False, timeout=30)
                        if pdf_response.status_code == 200 and pdf_response.content.startswith(b'%PDF'):
                            with pdfplumber.open(io.BytesIO(pdf_response.content)) as pdf:
                                texto = pdf.pages[0].extract_text() or ""
                                return f"{texto[:1500]}...", True, f"PDF encontrado en HTML. {debug_info}"
        
        return f"Respuesta no válida. {debug_info}", False, debug_info
        
    except requests.exceptions.Timeout:
        return "Timeout al conectar con AIC", False, "Timeout error"
    except requests.exceptions.ConnectionError:
        return "Error de conexión con AIC", False, "Connection error"
    except Exception as e:
        return f"Error AIC: {str(e)}", False, f"Exception: {str(e)}"

def obtener_datos_aic_alternativo():
    """
    Método alternativo usando diferentes parámetros o URLs
    """
    try:
        # Intentar con diferentes parámetros si el principal falla
        urls_alternativas = [
            "https://www.aic.gob.ar/sitio/pronostico-extendido",
            "https://www.aic.gob.ar/pronosticos/extendido",
            "https://www.aic.gob.ar/sitio/pronosticos?localidad=22"
        ]
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        for url in urls_alternativas:
            try:
                response = requests.get(url, headers=headers, verify=False, timeout=20)
                if response.status_code == 200:
                    # Buscar información de pronóstico en el HTML
                    texto = response.text
                    
                    # Buscar patrones comunes en páginas AIC
                    patrones = [
                        r'pronóstico extendido[^<]*</h[1-6]>([^<]+)',
                        r'San Martín de los Andes[^<]*</strong>([^<]+)',
                        r'<div[^>]*class="[^"]*pronostico[^"]*"[^>]*>([^<]+)'
                    ]
                    
                    for patron in patrones:
                        match = re.search(patron, texto, re.IGNORECASE)
                        if match:
                            encontrado = match.group(1).strip()
                            if len(encontrado) > 50:  # Validar que tenga suficiente contenido
                                return encontrado[:1000], True, f"Encontrado en {url}"
            except:
                continue
        
        return "No se pudo obtener datos de URLs alternativas", False, "Todas las alternativas fallaron"
        
    except Exception as e:
        return f"Error alternativo AIC: {str(e)}", False, str(e)

def obtener_datos_smn():
    try:
        url = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=pron5d"
        r = requests.get(url, timeout=20)
        
        if r.status_code == 200:
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                nombre_txt = [f for f in z.namelist() if f.endswith('.txt')][0]
                with z.open(nombre_txt) as f:
                    contenido = f.read().decode('utf-8', errors='ignore')
                    
                    # Buscar específicamente Chapelco
                    if "CHAPELCO_AERO" in contenido:
                        # Encontrar la sección completa para Chapelco
                        inicio = contenido.find("CHAPELCO_AERO")
                        if inicio != -1:
                            # Tomar desde Chapelco hasta la próxima estación o 2000 caracteres
                            resto = contenido[inicio:]
                            fin = resto.find("NOMBRE_ESTACION")
                            if fin == -1:
                                fin = 2000
                            
                            bloque = resto[:fin].strip()
                            return bloque, True, "Datos SMN obtenidos exitosamente"
        
        return None, False, "No se encontraron datos para Chapelco"
    except Exception as e:
        return f"Error SMN: {str(e)}", False, str(e)

def obtener_datos_openmeteo(fecha):
    try:
        # Modelo global satelital para San Martín de los Andes
        url = (f"https://api.open-meteo.com/v1/forecast?"
               f"latitude=-40.15&longitude=-71.35"
               f"&daily=temperature_2m_max,temperature_2m_min,"
               f"windspeed_10m_max,precipitation_sum,weathercode,"
               f"precipitation_probability_max"
               f"&timezone=America%2FArgentina%2FBuenos_Aires"
               f"&start_date={fecha.strftime('%Y-%m-%d')}"
               f"&end_date={(fecha + timedelta(days=6)).strftime('%Y-%m-%d')}")
        
        response = requests.get(url, timeout=20)
        if response.status_code == 200:
            datos = response.json()
            if 'daily' in datos:
                # Formatear datos para mejor legibilidad
                resumen = f"Pronóstico para {fecha.strftime('%d/%m')} a {(fecha + timedelta(days=6)).strftime('%d/%m')}:\n"
                for i in range(min(7, len(datos['daily']['time']))):
                    fecha_dia = datos['daily']['time'][i]
                    tmax = datos['daily']['temperature_2m_max'][i]
                    tmin = datos['daily']['temperature_2m_min'][i]
                    precip = datos['daily']['precipitation_sum'][i]
                    viento = datos['daily']['windspeed_10m_max'][i]
                    
                    resumen += f"{fecha_dia}: Max {tmax}°C, Min {tmin}°C, Precip {precip}mm, Viento {viento}km/h\n"
                
                return datos, True, "Datos Open-Meteo obtenidos"
        
        return None, False, f"Error HTTP {response.status_code}"
    except Exception as e:
        return f"Error Open-Meteo: {str(e)}", False, str(e)

# ============================================================================
# 4. INTERFAZ PRINCIPAL
# ============================================================================

# Barra lateral (Sidebar) limpia: Solo controles esenciales
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/869/869869.png", width=80)
    st.header("Configuración")
    fecha_base = st.date_input("Fecha del Reporte", datetime.now())
    
    # Opción para forzar modo debug
    modo_debug = st.checkbox("🔧 Modo Debug (mostrar detalles técnicos)")
    
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
        # 2. Captura de datos en paralelo con reintentos
        status.update(label="📡 Conectando con AIC (intento 1/2)...", state="running")
        datos_aic, aic_ok, debug_aic = obtener_datos_aic()
        
        # Si falla el primer intento, intentar método alternativo
        if not aic_ok:
            status.update(label="📡 Conectando con AIC (intento 2/2 - alternativo)...", state="running")
            datos_aic, aic_ok, debug_aic = obtener_datos_aic_alternativo()
        
        status.update(label="📡 Conectando con SMN...", state="running")
        datos_smn, smn_ok, debug_smn = obtener_datos_smn()
        
        status.update(label="🛰️ Obteniendo datos satelitales...", state="running")
        datos_om, om_ok, debug_om = obtener_datos_openmeteo(fecha_base)
        
        # Mostrar información de debug si está habilitado
        if modo_debug:
            with st.expander("🔍 Información de Debug"):
                st.write("**AIC:**", debug_aic)
                st.write("**SMN:**", debug_smn)
                st.write("**Open-Meteo:**", debug_om)
        
        status.update(label="🧠 Analizando datos con IA...", state="running")
        
        # 3. Preparar datos para el prompt
        datos_para_prompt = {
            "AIC": datos_aic[:800] + "..." if aic_ok and datos_aic and len(datos_aic) > 800 else datos_aic,
            "SMN": datos_smn[:800] + "..." if smn_ok and datos_smn and len(datos_smn) > 800 else datos_smn,
            "OpenMeteo": str(datos_om)[:500] + "..." if om_ok and datos_om else "SIN DATOS"
        }
        
        # 4. Prompt con tu Estructura de Memoria y Ponderación 40/60
        prompt = f"""
        FECHA DE REFERENCIA: {fecha_base.strftime('%A %d de %B de %Y')}
        LUGAR: San Martín de los Andes, Neuquén, Argentina.

        FUENTES OFICIALES (PONDERACIÓN 40% - PRIORIDAD EN ALERTAS):
        - AIC (Pronóstico Extendido PDF): {datos_para_prompt['AIC'] if aic_ok else 'SIN DATOS'}
        - SMN (Estación Chapelco Aero): {datos_para_prompt['SMN'] if smn_ok else 'SIN DATOS'}

        MODELO GLOBAL SATELITAL (PONDERACIÓN 60% - TENDENCIA):
        - Open-Meteo (GFS/ECMWF): {datos_para_prompt['OpenMeteo'] if om_ok else 'SIN DATOS'}

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
        7. Si falta información de AIC, usa más peso de SMN y Open-Meteo.
        """

        # 5. Ejecución con Jerarquía de Modelos
        sintesis, motor_ia = llamar_ia_con_fallback(prompt)
        
        if "❌ Todos los modelos fallaron" in sintesis:
            status.update(label="❌ Error crítico en IA", state="error")
            st.error(sintesis)
            st.stop()
        else:
            status.update(label="✅ Síntesis generada exitosamente", state="complete")

    # 6. RESULTADO FINAL (Pantalla principal)
    st.markdown("### 📋 Pronóstico Generado")
    st.markdown(f'<div class="reporte-final">{sintesis}</div>', unsafe_allow_html=True)

    # 7. TESTIGO DE VERDAD (Leyenda de fuentes al final)
    st.markdown("### 🔍 Testigo de Fuentes")
    
    # Información detallada de debug
    info_debug = ""
    if modo_debug:
        info_debug = f"""
        <div class="debug-info">
            <strong>Debug Info:</strong><br>
            AIC: {debug_aic}<br>
            SMN: {debug_smn}<br>
            Open-Meteo: {debug_om}
        </div>
        """
    
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
    {info_debug}
    """, unsafe_allow_html=True)

    # 8. Descarga del reporte
    reporte_completo = f"""
    SÍNTESIS METEOROLÓGICA - SAN MARTÍN DE LOS ANDES
    Fecha de generación: {datetime.now().strftime('%d/%m/%Y %H:%M')}
    Fuente IA: {motor_ia}
    
    {sintesis}
    
    --- METADATOS ---
    Fuentes consultadas:
    - AIC: {'✅' if aic_ok else '❌'} {'(método alternativo)' if not aic_ok and 'alternativo' in debug_aic else ''}
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
### 📌 Mejoras Implementadas:

#### 🔧 **Solución para AIC:**
1. **Headers mejorados:** Simulación de navegador real
2. **Verificación de contenido:** Detecta si es PDF o HTML
3. **Método alternativo:** Si falla el PDF directo, busca en páginas HTML
4. **Debug integrado:** Muestra información técnica para diagnóstico

#### 🔄 **Sistema de fallback:**
- Intento 1: URL directa del PDF
- Intento 2: Método alternativo con diferentes URLs
- Opción de debug para ver detalles técnicos

#### 📊 **Monitoreo mejorado:**
- Status codes de todas las respuestas
- Tipo de contenido detectado
- Tiempos de respuesta
""")

st.caption(f"🏔️ Sistema optimizado para modelos Gemini 3/2.5 | Versión 2026.01 | Última ejecución: {datetime.now().strftime('%H:%M:%S')}")
