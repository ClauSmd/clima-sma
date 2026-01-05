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
from bs4 import BeautifulSoup

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
    .success-box {
        background-color: #4CAF50;
        color: white;
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
    Jerarquía optimizada
    """
    
    # MODELOS ORDENADOS POR CALIDAD Y DISPONIBILIDAD
    motores = [
        # 1. GEMINI 3 (los mejores)
        "models/gemini-3-pro-preview",      # Más preciso
        "models/gemini-3-flash-preview",    # Más rápido
        
        # 2. GEMINI 2.5 (muy buenos)
        "models/gemini-2.5-pro",
        "models/gemini-2.5-flash",
        
        # 3. GEMINI LATEST (alta disponibilidad)
        "models/gemini-pro-latest",
        "models/gemini-flash-latest",
        
        # 4. GEMINI 2.0 (backup)
        "models/gemini-2.0-flash-exp",
        "models/gemini-2.0-flash",
        
        # 5. GEMMA (último recurso)
        "models/gemma-3-27b-it",
        "models/gemma-3-12b-it"
    ]
    
    ultimo_error = ""
    for motor in motores:
        try:
            st.info(f"🤖 Probando modelo: {motor}")
            model = genai.GenerativeModel(motor)
            response = model.generate_content(prompt)
            if response.text:
                st.success(f"✅ Modelo {motor} funcionó correctamente")
                return response.text, motor.replace("models/", "").upper()
        except Exception as e:
            error_msg = str(e)
            ultimo_error = f"Modelo {motor}: {error_msg}"
            
            if "429" in error_msg or "quota" in error_msg.lower():
                st.warning(f"⚠️ Límite diario alcanzado en {motor}")
                continue
            elif "not found" in error_msg.lower():
                st.warning(f"⚠️ Modelo {motor} no encontrado")
                continue
            else:
                st.warning(f"⚠️ Error en {motor}: {error_msg[:100]}")
                continue
                
    return f"❌ Todos los modelos fallaron. Último error: {ultimo_error}", "NINGUNO"

# ============================================================================
# 3. FUNCIONES DE EXTRACCIÓN (VERSIÓN DEFINITIVA PARA AIC)
# ============================================================================

def obtener_datos_aic():
    """
    VERSIÓN DEFINITIVA - AIC devuelve HTML, extraemos información directamente
    """
    try:
        st.info("🌐 Conectando a AIC (sitio web)...")
        
        # URL que sabemos que funciona (devuelve HTML)
        url = "https://www.aic.gob.ar/sitio/extendido-pdf?id_localidad=22&id_pronostico=1"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }
        
        response = requests.get(url, headers=headers, verify=False, timeout=30)
        st.info(f"📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            # Parsear el HTML con BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # ESTRATEGIA 1: Buscar el iframe que contiene el PDF
            iframe = soup.find('iframe')
            if iframe and 'src' in iframe.attrs:
                pdf_url = iframe['src']
                if not pdf_url.startswith('http'):
                    pdf_url = 'https://www.aic.gob.ar' + pdf_url
                
                st.info(f"🔗 Encontrado iframe con PDF: {pdf_url}")
                # Intentar descargar el PDF desde el iframe
                pdf_response = requests.get(pdf_url, headers=headers, verify=False, timeout=30)
                if pdf_response.status_code == 200 and pdf_response.content.startswith(b'%PDF'):
                    with pdfplumber.open(io.BytesIO(pdf_response.content)) as pdf:
                        texto = ""
                        for page in pdf.pages[:3]:
                            texto += page.extract_text() or ""
                        if texto.strip():
                            texto = re.sub(r'\s+', ' ', texto)
                            return texto[:2500], True, f"PDF extraído de iframe - {len(texto)} chars"
            
            # ESTRATEGIA 2: Buscar texto directamente en el HTML
            st.info("📝 Buscando texto del pronóstico en HTML...")
            
            # Buscar secciones que puedan contener el pronóstico
            posibles_contenedores = []
            
            # Buscar por clases comunes
            for div in soup.find_all(['div', 'section', 'article']):
                if 'pronostico' in str(div.get('class', '')).lower() or 'extendido' in str(div.get('class', '')).lower():
                    posibles_contenedores.append(div.get_text(strip=True))
            
            # Buscar por texto que contenga "San Martín"
            for element in soup.find_all(text=re.compile(r'San\s+Martín', re.IGNORECASE)):
                parent = element.parent
                if parent:
                    posibles_contenedores.append(parent.get_text(strip=True))
            
            # Buscar todas las tablas (pueden contener datos meteorológicos)
            for table in soup.find_all('table'):
                posibles_contenedores.append(table.get_text(strip=True))
            
            # Si encontramos contenido relevante
            if posibles_contenedores:
                # Tomar el contenido más largo (probablemente el más completo)
                contenido = max(posibles_contenedores, key=len)
                if len(contenido) > 200:
                    return contenido[:2500], True, f"Texto extraído de HTML - {len(contenido)} chars"
            
            # ESTRATEGIA 3: Extraer todo el texto y buscar patrones meteorológicos
            st.info("🔍 Extrayendo todo el texto y buscando patrones...")
            todo_texto = soup.get_text()
            
            # Limpiar y buscar secciones relevantes
            lineas = [line.strip() for line in todo_texto.split('\n') if line.strip()]
            
            # Filtrar líneas que parezcan ser pronóstico
            lineas_meteo = []
            palabras_clave = ['temperatura', 'viento', 'lluvia', 'nublado', 'despejado', '°C', 'km/h', 'mm', 'pronóstico', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
            
            for linea in lineas:
                if any(palabra.lower() in linea.lower() for palabra in palabras_clave):
                    lineas_meteo.append(linea)
            
            if lineas_meteo:
                texto_meteo = '\n'.join(lineas_meteo[:50])  # Tomar hasta 50 líneas
                if len(texto_meteo) > 100:
                    return texto_meteo[:2500], True, f"Patrones encontrados en HTML - {len(texto_meteo)} chars"
            
            # ESTRATEGIA 4: Devolver el HTML limpio como último recurso
            texto_limpio = re.sub(r'<[^>]+>', ' ', response.text)
            texto_limpio = re.sub(r'\s+', ' ', texto_limpio)
            
            # Buscar la sección más probable del pronóstico (últimos 5000 caracteres)
            texto_relevante = texto_limpio[-5000:]
            
            if len(texto_relevante) > 200:
                return texto_relevante[:2500], True, f"HTML procesado - {len(texto_relevante)} chars"
            else:
                return texto_limpio[:2500], True, f"HTML completo - {len(texto_limpio)} chars"
        
        return f"Error HTTP: {response.status_code}", False, f"Status {response.status_code}"
        
    except Exception as e:
        return f"Error AIC: {str(e)}", False, f"Exception: {str(e)}"

def obtener_datos_smn():
    """
    SMN optimizado
    """
    try:
        url = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=pron5d"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        
        response = requests.get(url, headers=headers, timeout=25)
        
        if response.status_code == 200:
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                archivos = z.namelist()
                archivo_txt = next((f for f in archivos if f.lower().endswith('.txt')), None)
                
                if archivo_txt:
                    with z.open(archivo_txt) as f:
                        contenido = f.read().decode('utf-8', errors='ignore')
                        
                        # Buscar Chapelco de múltiples formas
                        contenido_upper = contenido.upper()
                        busquedas = ["CHAPELCO_AERO", "CHAPELCO", "SAN MARTIN"]
                        
                        for busqueda in busquedas:
                            if busqueda in contenido_upper:
                                inicio = contenido_upper.find(busqueda)
                                fin = contenido_upper.find("NOMBRE_ESTACION", inicio + 1)
                                if fin == -1:
                                    fin = inicio + 1500
                                
                                bloque = contenido[inicio:fin].strip()
                                return bloque, True, f"Encontrado: {busqueda} - {len(bloque)} chars"
        
        return "No se encontraron datos", False, "Sin datos válidos"
        
    except Exception as e:
        return f"Error: {str(e)}", False, str(e)

def obtener_datos_openmeteo(fecha):
    """
    Open-Meteo optimizado
    """
    try:
        url = (f"https://api.open-meteo.com/v1/forecast?"
               f"latitude=-40.1579&longitude=-71.3534"
               f"&daily=temperature_2m_max,temperature_2m_min,"
               f"precipitation_sum,precipitation_probability_max,"
               f"windspeed_10m_max,winddirection_10m_dominant,weathercode"
               f"&timezone=America%2FSantiago"
               f"&forecast_days=7")
        
        response = requests.get(url, timeout=20)
        
        if response.status_code == 200:
            datos = response.json()
            
            # Crear resumen estructurado
            if 'daily' in datos:
                resumen = []
                tiempos = datos['daily']['time']
                
                for i in range(min(7, len(tiempos))):
                    dia_info = {
                        'fecha': tiempos[i],
                        'tmax': datos['daily']['temperature_2m_max'][i],
                        'tmin': datos['daily']['temperature_2m_min'][i],
                        'precip': datos['daily']['precipitation_sum'][i],
                        'prob_precip': datos['daily']['precipitation_probability_max'][i],
                        'viento': datos['daily']['windspeed_10m_max'][i],
                        'direccion': datos['daily']['winddirection_10m_dominant'][i]
                    }
                    resumen.append(dia_info)
                
                return resumen, True, f"7 días obtenidos"
        
        return [], False, f"Error: {response.status_code}"
        
    except Exception as e:
        return f"Error: {str(e)}", False, str(e)

# ============================================================================
# 4. INTERFAZ PRINCIPAL
# ============================================================================

# Barra lateral
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/869/869869.png", width=80)
    st.header("⚙️ Configuración")
    fecha_base = st.date_input("Fecha Base", datetime.now())
    
    st.markdown("---")
    st.markdown("**🎯 Estrategia IA:**")
    st.progress(0.4, text="40% Fuentes locales")
    st.progress(0.6, text="60% Modelos globales")
    
    st.markdown("---")
    st.markdown("**📡 Fuentes activas:**")
    st.markdown("• 🌐 AIC Neuquén")
    st.markdown("• 🏔️ SMN Chapelco")
    st.markdown("• 🛰️ Open-Meteo")

st.title("🏔️ Sistema Meteorológico SMA")
st.subheader("Pronóstico Inteligente para San Martín de los Andes")

# Botón principal
if st.button("🚀 GENERAR PRONÓSTICO AVANZADO", type="primary", use_container_width=True):
    
    # Configurar API
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        st.success("🔑 API Key configurada")
    except:
        st.error("❌ Error con API Key")
        st.stop()
    
    # Proceso principal
    with st.status("🚀 Iniciando análisis meteorológico...", expanded=True) as status:
        
        # === AIC ===
        status.update(label="📡 Extrayendo datos de AIC Neuquén...", state="running")
        datos_aic, aic_ok, debug_aic = obtener_datos_aic()
        
        # === SMN ===
        status.update(label="📡 Extrayendo datos de SMN Chapelco...", state="running")
        datos_smn, smn_ok, debug_smn = obtener_datos_smn()
        
        # === Open-Meteo ===
        status.update(label="🛰️ Obteniendo datos satelitales...", state="running")
        datos_om, om_ok, debug_om = obtener_datos_openmeteo(fecha_base)
        
        # === Preparar prompt ===
        status.update(label="📝 Preparando análisis para IA...", state="running")
        
        # Formatear datos para el prompt
        datos_aic_texto = datos_aic[:1500] + "..." if aic_ok and len(str(datos_aic)) > 1500 else (str(datos_aic) if aic_ok else "NO DISPONIBLE")
        datos_smn_texto = datos_smn[:1500] + "..." if smn_ok and len(str(datos_smn)) > 1500 else (str(datos_smn) if smn_ok else "NO DISPONIBLE")
        
        # Formatear Open-Meteo
        if om_ok and isinstance(datos_om, list):
            om_texto = "Pronóstico Open-Meteo (7 días):\n"
            for dia in datos_om:
                fecha = datetime.strptime(dia['fecha'], '%Y-%m-%d')
                om_texto += f"{fecha.strftime('%A %d/%m')}: Max {dia['tmax']}°C, Min {dia['tmin']}°C, "
                om_texto += f"Precip {dia['precip']}mm ({dia['prob_precip']}%), "
                om_texto += f"Viento {dia['viento']}km/h ({dia['direccion']}°)\n"
        else:
            om_texto = str(datos_om) if om_ok else "NO DISPONIBLE"
        
        # === Construir prompt optimizado ===
        prompt = f"""
        # INSTRUCCIONES PARA PRONÓSTICO METEOROLÓGICO
        FECHA ACTUAL: {fecha_base.strftime('%A %d de %B de %Y')}
        UBICACIÓN: San Martín de los Andes, Neuquén, Argentina
        
        ## DATOS DE FUENTES OFICIALES:
        
        ### 1. AIC NEUQUÉN (Pronóstico Extendido):
        {datos_aic_texto}
        
        ### 2. SMN CHAPELCO (Datos de Estación):
        {datos_smn_texto}
        
        ### 3. MODELOS GLOBALES OPEN-METEO:
        {om_texto}
        
        ## INSTRUCCIONES ESPECÍFICAS:
        
        1. **GENERAR PRONÓSTICO PARA 5-6 DÍAS** comenzando desde mañana.
        
        2. **APLICAR PONDERACIÓN 40/60**:
           - 40% peso a AIC/SMN (fenómenos locales específicos)
           - 60% peso a Open-Meteo (tendencias de temperatura)
        
        3. **FORMATO ESTRICTO POR DÍA**:
        [Día de semana] [Día] de [Mes] – San Martín de los Andes: [Descripción concisa] con [estado del cielo], y máxima esperada de [temperatura]°C, mínima de [temperatura]°C. Viento del [dirección] entre [vel_min] y [vel_max] km/h, [precipitación].
        #[SanMartínDeLosAndes] #[ClimaSMA] #[Condición1] #[Condición2] #[Condición3]
        
        4. **VOCABULARIO ESPECÍFICO**:
           - Cielo: "despejado", "parcialmente nublado", "mayormente nublado", "cubierto"
           - Precipitación: "sin precipitaciones", "lloviznas", "lluvias leves", "lluvias moderadas", "lluvias intensas"
           - Viento: "leve (0-15 km/h)", "moderado (15-30)", "intenso (30-45)", "fuerte (+45)"
        
        5. **HASHTAGS RELEVANTES**: Usar #Andino #Patagonia #Montaña #Neuquén según contexto.
        
        6. **PRECISIÓN**: Las temperaturas mínimas en montaña pueden ser 5-10°C más bajas que en valle.
        
        7. **SI AIC ES HTML**: Interpretar la información meteorológica del texto HTML proporcionado.
        
        ## EJEMPLO DE FORMATO CORRECTO:
        Martes 06 de Enero – San Martín de los Andes: Día agradable con cielo parcialmente nublado, y máxima esperada de 25°C, mínima de 12°C. Viento del Oeste entre 10 y 20 km/h, sin precipitaciones.
        #SanMartínDeLosAndes #ClimaSMA #ParcialmenteNublado #VientoModerado #Andino
        """
        
        # === Ejecutar IA ===
        status.update(label="🧠 Analizando con modelos de IA...", state="running")
        sintesis, motor_ia = llamar_ia_con_fallback(prompt)
        
        if "❌ Todos los modelos fallaron" in sintesis:
            status.update(label="❌ Error en modelos IA", state="error")
            st.error(sintesis)
        else:
            status.update(label="✅ Análisis completado", state="complete")
    
    # === MOSTRAR RESULTADOS ===
    if "❌ Todos los modelos fallaron" not in sintesis:
        # Pronóstico
        st.markdown("### 📋 PRONÓSTICO GENERADO")
        st.markdown(f'<div class="reporte-final">{sintesis}</div>', unsafe_allow_html=True)
        
        # Panel de estado
        st.markdown("### 📊 ESTADO DEL SISTEMA")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("AIC", "✅ ONLINE" if aic_ok else "❌ OFFLINE", 
                     debug_aic.split(' - ')[0] if aic_ok else "Error")
        
        with col2:
            st.metric("SMN", "✅ ONLINE" if smn_ok else "❌ OFFLINE",
                     debug_smn.split(' - ')[0] if smn_ok else "Error")
        
        with col3:
            st.metric("SATELITAL", "✅ ONLINE" if om_ok else "❌ OFFLINE",
                     debug_om.split(' - ')[0] if om_ok else "Error")
        
        # Detalles técnicos
        with st.expander("🔍 DETALLES TÉCNICOS", expanded=False):
            st.markdown(f"""
            **Motor IA:** {motor_ia}
            
            **Estrategia:** {"Ponderación 40/60 normal" if aic_ok else "Ajustada por falta de AIC"}
            
            **Timestamp:** {datetime.now().strftime('%H:%M:%S')}
            
            **Debug AIC:** {debug_aic}
            **Debug SMN:** {debug_smn}
            **Debug Open-Meteo:** {debug_om}
            """)
        
        # Descarga
        reporte = f"""PRONÓSTICO SMA - {fecha_base.strftime('%d/%m/%Y')}
        
{sintesis}

---
Fuentes: AIC ({'OK' if aic_ok else 'FAIL'}), SMN ({'OK' if smn_ok else 'FAIL'}), Open-Meteo ({'OK' if om_ok else 'FAIL'})
Modelo IA: {motor_ia}
Generado: {datetime.now().strftime('%H:%M:%S')}
"""
        
        st.download_button(
            "💾 DESCARGAR REPORTE",
            reporte,
            f"pronostico_sma_{fecha_base.strftime('%Y%m%d')}.txt"
        )

# Información final
st.markdown("---")
st.markdown("""
### 📈 ESTADÍSTICAS DE MODELOS (usos/día aproximados):

**Gemini 3 Series:** 15-25 usos  
**Gemini 2.5 Series:** 30-40 usos  
**Gemini Latest:** 50-60 usos  
**Gemma 3 Series:** 80-100+ usos  

*El sistema selecciona automáticamente el mejor modelo disponible.*
""")

st.caption(f"🔄 Sistema actualizado: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
