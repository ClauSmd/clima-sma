import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime, timedelta
import zipfile
import io
import re
import pdfplumber
import time
import urllib3
import pandas as pd

# Deshabilitar warnings de SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================================================
# 1. CONFIGURACIÓN INICIAL - CON API KEY FIXED
# ============================================================================

# Configurar API Key de Google (tu clave)
API_KEY = "AIzaSyBKoBfnlDsZ99DFgg2EQfhdfl_3B8yj_34"

try:
    genai.configure(api_key=API_KEY)
    st.sidebar.success("✅ API Key configurada")
except Exception as e:
    st.sidebar.error(f"❌ Error API Key: {e}")

# Configuración de página
st.set_page_config(page_title="Sistema Climático SMA", page_icon="🏔️", layout="wide")

# CSS personalizado
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 20px;
        background: linear-gradient(135deg, #1a2980, #26d0ce);
        border-radius: 10px;
        margin-bottom: 20px;
        color: white;
    }
    .source-card {
        background-color: #1e1e1e;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        border-left: 5px solid;
    }
    .card-aic { border-left-color: #4CAF50; }
    .card-smn { border-left-color: #2196F3; }
    .card-om { border-left-color: #FF9800; }
    .forecast-card {
        background-color: #2d2d2d;
        padding: 20px;
        border-radius: 10px;
        margin: 15px 0;
        border: 1px solid #444;
        font-size: 1.1em;
        line-height: 1.6;
    }
    .alert-box {
        background-color: #330000;
        padding: 12px;
        border-radius: 6px;
        border-left: 4px solid #ff4444;
        margin: 8px 0;
    }
    .model-info {
        background-color: #1a3c1a;
        padding: 10px;
        border-radius: 5px;
        border-left: 4px solid #4CAF50;
        margin: 5px 0;
    }
</style>
""", unsafe_allow_html=True)

# Título principal
st.markdown('<div class="main-header"><h1>🏔️ Sistema de Fusión Meteorológica SMA</h1><p>Ponderación 40/60: AIC+SMN (40%) + Open-Meteo (60%)</p></div>', unsafe_allow_html=True)

# Sidebar con configuración
with st.sidebar:
    st.header("⚙️ Configuración")
    
    # Fecha base
    fecha_base = st.date_input("Fecha de inicio", datetime.now().date())
    
    st.markdown("---")
    st.header("🤖 Configuración IA")
    
    # Selección de modelo
    modelo_seleccionado = st.selectbox(
        "Modelo Gemini",
        ["gemini-1.5-pro", "gemini-1.0-pro", "gemini-pro", "models/gemini-pro"]
    )
    
    st.markdown("---")
    st.info("""
    **📊 Estrategia de fusión:**
    - 40%: Fuentes locales (AIC + SMN)
    - 60%: Modelos globales (Open-Meteo)
    
    **🎯 Prioridades:**
    1. Fenómenos locales (tormentas, ráfagas)
    2. Tendencia térmica precisa
    3. Alertas de seguridad
    
    **🔧 Modelos disponibles:**
    - gemini-1.5-pro (recomendado)
    - gemini-1.0-pro
    - gemini-pro
    """)

# ============================================================================
# 2. FUNCIONES DE EXTRACCIÓN (OPTIMIZADAS)
# ============================================================================

def obtener_datos_aic():
    """Extrae datos de AIC"""
    try:
        url = "https://www.aic.gob.ar/sitio/extendido-pdf?a=1029&z=1750130550"
        response = requests.get(url, timeout=30, verify=False)
        
        if response.status_code != 200:
            return [], False, "❌ Error HTTP al descargar PDF"
        
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            texto = pdf.pages[0].extract_text()
        
        lineas = [line.strip() for line in texto.split('\n') if line.strip()]
        
        if len(lineas) < 12:
            return [], False, "❌ Formato de PDF inesperado"
        
        # Fechas únicas
        todas_fechas = lineas[1].split()
        fechas_unicas = []
        for i in range(0, len(todas_fechas), 2):
            if i < len(todas_fechas) and todas_fechas[i] not in fechas_unicas:
                fechas_unicas.append(todas_fechas[i])
        
        # Períodos
        periodos = lineas[2].split()
        
        # Condiciones del cielo (líneas 3-6)
        lineas_cielo = lineas[3:7]
        palabras_por_linea = []
        for linea in lineas_cielo:
            palabras = linea.split()
            if palabras and palabras[0] == "Cielo":
                palabras = palabras[1:]
            palabras_por_linea.append(palabras)
        
        # Reconstruir condiciones VERTICALMENTE
        condiciones = []
        for col in range(12):  # 12 columnas
            condicion = ""
            for fila in range(4):  # 4 líneas
                if col < len(palabras_por_linea[fila]):
                    palabra = palabras_por_linea[fila][col].rstrip(',')
                    condicion += palabra + " "
            condiciones.append(condicion.strip())
        
        # Temperaturas
        temperaturas = re.findall(r'(-?\d+)\s*[ºC°C]', lineas[7])
        
        # Vientos
        vientos = re.findall(r'(\d+)\s*km/h', lineas[8])
        
        # Ráfagas
        rafagas = re.findall(r'(\d+)\s*km/h', lineas[9])
        
        # Dirección
        partes = lineas[10].split()
        direcciones = [p for p in partes if re.match(r'^[NSEO]{1,3}$', p)]
        
        # Presión
        presiones = re.findall(r'(\d+)\s*hPa', lineas[11])
        
        # Construir tabla
        tabla = []
        for i in range(min(12, len(periodos), len(temperaturas))):
            fecha_idx = i // 2
            fecha = fechas_unicas[fecha_idx] if fecha_idx < len(fechas_unicas) else "N/D"
            
            tabla.append({
                'Fecha': fecha,
                'Momento': periodos[i],
                'Cielo': condiciones[i] if i < len(condiciones) else "",
                'Temp': temperaturas[i] if i < len(temperaturas) else "N/D",
                'Viento': vientos[i] if i < len(vientos) else "N/D",
                'Ráfagas': rafagas[i] if i < len(rafagas) else "N/D",
                'Dirección': direcciones[i] if i < len(direcciones) else "N/D",
                'Presión': presiones[i] if i < len(presiones) else "N/D"
            })
        
        return tabla, True, f"✅ AIC: {len(tabla)} registros ({len(fechas_unicas)} días)"
        
    except Exception as e:
        return [], False, f"❌ Error AIC: {str(e)}"

def obtener_datos_smn():
    """Extrae datos de SMN"""
    try:
        url = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=pron5d"
        response = requests.get(url, timeout=30, verify=False)
        
        if response.status_code != 200:
            return {"estado": "error", "mensaje": f"HTTP {response.status_code}"}, False, f"❌ HTTP {response.status_code}"
        
        estructura = {
            "estado": "disponible",
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                archivos = zip_file.namelist()
                estructura["archivos"] = archivos
                
                # Buscar archivo TXT (puede tener nombre dinámico)
                txt_files = [f for f in archivos if f.lower().endswith('.txt')]
                
                if txt_files:
                    archivo_txt = txt_files[0]
                    with zip_file.open(archivo_txt) as f:
                        contenido = f.read().decode('utf-8', errors='ignore')
                    
                    estructura["archivo_txt"] = archivo_txt
                    estructura["contenido_preview"] = contenido[:1000] + "..." if len(contenido) > 1000 else contenido
                    
                    # Buscar CHAPELCO
                    if 'CHAPELCO' in contenido.upper():
                        idx = contenido.upper().find('CHAPELCO')
                        seccion = contenido[idx:idx+500]
                        estructura["chapelco_encontrado"] = True
                        estructura["seccion_chapelco"] = seccion
                        return estructura, True, f"✅ SMN: CHAPELCO encontrado en {archivo_txt}"
                    else:
                        estructura["chapelco_encontrado"] = False
                        return estructura, True, f"⚠️ SMN: Archivo {archivo_txt} sin CHAPELCO"
                else:
                    estructura["contenido"] = "No hay archivos TXT"
                    return estructura, True, "⚠️ SMN: ZIP sin archivos TXT"
        
        except zipfile.BadZipFile:
            estructura["estado"] = "bad_zip"
            return estructura, True, "⚠️ SMN: Archivo no es ZIP válido"
            
    except Exception as e:
        return {"estado": "error", "mensaje": str(e)}, False, f"❌ Error SMN: {str(e)}"

def obtener_datos_openmeteo():
    """Extrae datos COMPLETOS de Open-Meteo"""
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude=-40.1579&longitude=-71.3534&"
            f"hourly=temperature_2m,relativehumidity_2m,precipitation,weathercode,"
            f"windspeed_10m,winddirection_10m&"
            f"daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_sum,"
            f"windspeed_10m_max,windgusts_10m_max&"
            f"timezone=America%2FArgentina%2FBuenos_Aires&"
            f"forecast_days=5"
        )
        
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            datos = response.json()
            
            # Procesar datos diarios
            datos_procesados = {}
            if 'daily' in datos and 'time' in datos['daily']:
                for i in range(len(datos['daily']['time'])):
                    fecha_str = datos['daily']['time'][i]
                    try:
                        fecha_dt = datetime.strptime(fecha_str, '%Y-%m-%d')
                        fecha_key = fecha_dt.strftime('%d-%m-%Y')
                        
                        datos_procesados[fecha_key] = {
                            'fecha_dt': fecha_dt,
                            't_max': datos['daily']['temperature_2m_max'][i] if i < len(datos['daily']['temperature_2m_max']) else None,
                            't_min': datos['daily']['temperature_2m_min'][i] if i < len(datos['daily']['temperature_2m_min']) else None,
                            'precip': datos['daily']['precipitation_sum'][i] if i < len(datos['daily']['precipitation_sum']) else 0,
                            'viento_max': datos['daily']['windspeed_10m_max'][i] if i < len(datos['daily']['windspeed_10m_max']) else 0,
                            'rafagas_max': datos['daily']['windgusts_10m_max'][i] if i < len(datos['daily']['windgusts_10m_max']) else 0,
                            'weathercode': datos['daily']['weathercode'][i] if i < len(datos['daily']['weathercode']) else 0
                        }
                    except:
                        continue
            
            return datos_procesados, True, f"✅ Open-Meteo: {len(datos_procesados)} días"
        else:
            return {}, False, f"❌ Error HTTP {response.status_code}"
            
    except Exception as e:
        return {}, False, f"❌ Error Open-Meteo: {str(e)}"

# ============================================================================
# 3. FUNCIÓN DE IA MEJORADA (CON MÁS MODELOS Y MEJOR MANEJO)
# ============================================================================

def generar_sintesis_ia(datos_aic, datos_smn, datos_om, fuentes_activas):
    """Genera síntesis con IA - Versión mejorada"""
    
    try:
        # Preparar prompt detallado
        fecha_str = fecha_base.strftime('%A %d de %B %Y')
        
        # Formatear datos AIC
        aic_texto = "No disponible"
        if datos_aic:
            aic_lines = []
            for d in datos_aic[:6]:  # Primeros 6 registros (3 días)
                aic_lines.append(f"- {d['Fecha']} ({d['Momento']}): {d['Cielo']}. Temp: {d['Temp']}°C. Viento: {d['Viento']} km/h. Ráfagas: {d['Ráfagas']} km/h")
            aic_texto = "\n".join(aic_lines)
        
        # Formatear datos SMN
        smn_texto = "No disponible"
        if datos_smn and datos_smn.get('chapelco_encontrado'):
            smn_texto = datos_smn.get('seccion_chapelco', 'Datos Chapelco disponibles')[:500]
        
        # Formatear datos Open-Meteo
        om_texto = "No disponible"
        if datos_om:
            om_lines = []
            for fecha, vals in list(datos_om.items())[:3]:
                # Interpretar weathercode
                wcode = vals.get('weathercode', 0)
                condicion = interpretar_weathercode(wcode)
                
                om_lines.append(f"- {fecha}: {vals['t_min']:.1f}°C/{vals['t_max']:.1f}°C. {condicion}. Precip: {vals.get('precip', 0):.1f}mm. Viento: {vals.get('viento_max', 0):.1f} km/h")
            om_texto = "\n".join(om_lines)
        
        # Crear prompt detallado
        prompt = f"""
        # SÍNTESIS METEOROLÓGICA PROFESIONAL - SAN MARTÍN DE LOS ANDES
        ## FECHA: {fecha_str}
        
        ## 📊 FUENTES DISPONIBLES:
        - **AIC (Pronóstico Oficial Argentina):** {'✅ ACTIVA' if fuentes_activas['AIC'] else '❌ INACTIVA'}
        - **SMN Chapelco (Datos Estación):** {'✅ ACTIVA' if fuentes_activas['SMN'] and datos_smn.get('chapelco_encontrado') else '⚠️ ESTRUCTURA' if fuentes_activas['SMN'] else '❌ INACTIVA'}
        - **Open-Meteo (Modelos Globales):** {'✅ ACTIVA' if fuentes_activas['OM'] else '❌ INACTIVA'}
        
        ## 📋 DATOS CRUDOS POR FUENTE:
        
        ### A. AIC - PRONÓSTICO OFICIAL:
        {aic_texto}
        
        ### B. SMN - DATOS CHAPELCO:
        {smn_texto}
        
        ### C. OPEN-METEO - MODELOS GLOBALES:
        {om_texto}
        
        ## ⚖️ INSTRUCCIONES DE PONDERACIÓN 40/60:
        
        ### 1. ESTRATEGIA DE FUSIÓN:
        - **40% PESO:** Fuentes locales (AIC + SMN combinados)
        - **60% PESO:** Modelos Open-Meteo (tendencia térmica)
        
        ### 2. REGLAS DE DECISIÓN:
        a) **TEMPERATURAS:** 
           - Si AIC tiene datos: usar 40% AIC + 60% Open-Meteo
           - Si solo Open-Meteo: usar 100% Open-Meteo
           
        b) **FENÓMENOS ESPECÍFICOS:**
           - Tormentas eléctricas: priorizar AIC si reporta
           - Ráfagas > 30 km/h: priorizar AIC/SMN
           - Precipitación: promedio ponderado
           
        c) **CONDICIONES DEL CIELO:**
           - Usar descripción de AIC si disponible
           - Complementar con weathercode de Open-Meteo
        
        ### 3. FORMATO DE SALIDA REQUERIDO:
        [Emoji representativo] **DÍA (Fecha)** – San Martín de los Andes: [Descripción concisa de condiciones].
        
        **🌡️ Temperaturas:** Máxima de [temp_max]°C, mínima de [temp_min]°C.
        **💨 Viento:** [viento_prom] km/h con ráfagas de [rafaga_max] km/h desde [direccion].
        **📊 Presión:** [presion] hPa.
        
        [Solo si aplica] ⚡ **ALERTA:** [Mencionar si hay tormentas eléctricas, ráfagas fuertes >45 km/h, o temperaturas extremas]
        
        ### 4. RESTRICCIONES ESTRICTAS:
        - NO inventar datos no respaldados por las fuentes
        - Si falta una fuente, ajustar la ponderación proporcionalmente
        - Máximo 3 días de pronóstico detallado
        - Lenguaje natural pero técnicamente preciso
        - Incluir hashtags: #SanMartínDeLosAndes #ClimaSMA #PronósticoFusionado
        
        ## 🎯 GENERA LA SÍNTESIS METEOROLÓGICA FINAL:
        """
        
        # Lista de modelos a probar (en orden de preferencia)
        modelos_a_probar = [
            modelo_seleccionado,  # El seleccionado en el sidebar
            "gemini-1.5-pro",
            "gemini-1.0-pro",
            "gemini-pro",
            "models/gemini-pro"
        ]
        
        for modelo in modelos_a_probar:
            try:
                st.write(f"🔍 Probando modelo: {modelo}")
                model = genai.GenerativeModel(modelo)
                
                # Configurar parámetros de generación
                generation_config = {
                    "temperature": 0.2,  # Baja temperatura para respuestas consistentes
                    "top_p": 0.8,
                    "top_k": 40,
                    "max_output_tokens": 1500,
                }
                
                response = model.generate_content(
                    prompt,
                    generation_config=generation_config
                )
                
                if response.text and len(response.text.strip()) > 100:
                    return response.text, modelo
                    
            except Exception as e:
                st.warning(f"Modelo {modelo} falló: {str(e)[:100]}")
                continue
        
        # Si todos los modelos fallan
        return None, None
        
    except Exception as e:
        st.error(f"❌ Error crítico en IA: {str(e)}")
        return None, None

def interpretar_weathercode(code):
    """Interpreta los códigos de weathercode de Open-Meteo"""
    codigos = {
        0: "Cielo despejado",
        1: "Mayormente despejado",
        2: "Parcialmente nublado",
        3: "Nublado",
        45: "Niebla",
        48: "Niebla helada",
        51: "Llovizna ligera",
        53: "Llovizna moderada",
        55: "Llovizna densa",
        61: "Lluvia ligera",
        63: "Lluvia moderada",
        65: "Lluvia intensa",
        71: "Nieve ligera",
        73: "Nieve moderada",
        75: "Nieve intensa",
        80: "Chubascos ligeros",
        81: "Chubascos moderados",
        82: "Chubascos intensos",
        95: "Tormenta eléctrica",
        96: "Tormenta con granizo ligero",
        99: "Tormenta con granizo intenso"
    }
    return codigos.get(code, f"Código {code}")

# ============================================================================
# 4. INTERFAZ PRINCIPAL MEJORADA
# ============================================================================

# Botón principal de ejecución
if st.button("🚀 EJECUTAR SÍNTESIS COMPLETA CON IA", type="primary", use_container_width=True):
    
    # Inicializar estados
    fuentes_activas = {"AIC": False, "SMN": False, "OM": False}
    mensajes = {"AIC": "", "SMN": "", "OM": ""}
    datos_aic, datos_smn, datos_om = [], {}, {}
    
    # Contenedor de progreso
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # ========================================
    # EXTRACCIÓN DE DATOS
    # ========================================
    
    with st.spinner("📡 Extrayendo datos de todas las fuentes..."):
        # AIC
        status_text.text("📊 Extrayendo AIC...")
        datos_aic, fuentes_activas["AIC"], mensajes["AIC"] = obtener_datos_aic()
        progress_bar.progress(30)
        
        # SMN
        status_text.text("⏰ Extrayendo SMN...")
        datos_smn, fuentes_activas["SMN"], mensajes["SMN"] = obtener_datos_smn()
        progress_bar.progress(60)
        
        # Open-Meteo
        status_text.text("🛰️ Extrayendo Open-Meteo...")
        datos_om, fuentes_activas["OM"], mensajes["OM"] = obtener_datos_openmeteo()
        progress_bar.progress(90)
    
    # ========================================
    # MOSTRAR DATOS INDIVIDUALES
    # ========================================
    
    st.markdown("---")
    st.subheader("📊 DATOS EXTRAÍDOS POR FUENTE")
    
    # Mostrar en pestañas
    tab1, tab2, tab3 = st.tabs(["📄 AIC", "⏰ SMN", "🛰️ Open-Meteo"])
    
    with tab1:
        if datos_aic:
            df_aic = pd.DataFrame(datos_aic)
            st.dataframe(df_aic, hide_index=True, use_container_width=True)
            
            # Mostrar ejemplo de parseo correcto
            st.write("**✅ Ejemplo de datos AIC parseados correctamente:**")
            if len(datos_aic) >= 2:
                st.write(f"**{datos_aic[0]['Fecha']} - {datos_aic[0]['Momento']}:** {datos_aic[0]['Cielo']}")
                st.write(f"**{datos_aic[1]['Fecha']} - {datos_aic[1]['Momento']}:** {datos_aic[1]['Cielo']}")
        else:
            st.info("No hay datos de AIC disponibles")
    
    with tab2:
        if datos_smn:
            st.json(datos_smn, expanded=False)
            
            if datos_smn.get('chapelco_encontrado'):
                st.success("✅ CHAPELCO encontrado en el archivo")
                if 'seccion_chapelco' in datos_smn:
                    st.text_area("Sección CHAPELCO:", datos_smn['seccion_chapelco'], height=200)
        else:
            st.info("Estructura SMN preparada, esperando datos completos")
    
    with tab3:
        if datos_om:
            # Crear tabla resumen
            resumen_om = []
            for fecha, vals in datos_om.items():
                resumen_om.append({
                    'Fecha': fecha,
                    'Máx': f"{vals['t_max']:.1f}°C",
                    'Mín': f"{vals['t_min']:.1f}°C",
                    'Precip': f"{vals.get('precip', 0):.1f} mm",
                    'Viento': f"{vals.get('viento_max', 0):.1f} km/h",
                    'Condición': interpretar_weathercode(vals.get('weathercode', 0))
                })
            
            df_om = pd.DataFrame(resumen_om)
            st.dataframe(df_om, hide_index=True, use_container_width=True)
        else:
            st.info("No hay datos de Open-Meteo")
    
    # ========================================
    # SÍNTESIS CON IA
    # ========================================
    
    # Verificar que tenemos datos para síntesis
    if fuentes_activas["OM"] or fuentes_activas["AIC"]:
        with st.spinner("🧠 Generando síntesis con IA..."):
            sintesis, modelo_usado = generar_sintesis_ia(
                datos_aic, datos_smn, datos_om, fuentes_activas
            )
        
        progress_bar.progress(100)
        status_text.text("✅ Proceso completado")
        
        if sintesis:
            st.markdown("---")
            st.subheader("🎯 SÍNTESIS PONDERADA 40/60")
            
            # Mostrar síntesis con estilo
            st.markdown(f'<div class="forecast-card">{sintesis}</div>', unsafe_allow_html=True)
            
            # Información del modelo usado
            st.markdown(f'<div class="model-info">🧠 <strong>Modelo utilizado:</strong> {modelo_usado} | ⚖️ <strong>Ponderación:</strong> 40% Local / 60% Global</div>', unsafe_allow_html=True)
            
            # Botón para copiar
            st.download_button(
                "📋 Copiar síntesis",
                sintesis,
                file_name=f"sintesis_sma_{datetime.now().strftime('%Y%m%d')}.txt",
                mime="text/plain"
            )
        else:
            st.error("""
            ❌ No se pudo generar la síntesis con IA. Posibles causas:
            
            1. **Problemas con la API Key** - Verifica que sea válida
            2. **Límite de cuota alcanzado** - Espera o usa otra cuenta
            3. **Modelos no disponibles** - Intenta con otro modelo en el sidebar
            
            **Solución temporal:** Usa los datos crudos mostrados arriba.
            """)
    else:
        st.error("❌ Se requiere al menos Open-Meteo o AIC para generar síntesis")
    
    # ========================================
    # RESUMEN DE FUENTES DISPONIBLES
    # ========================================
    
    st.markdown("---")
    st.subheader("📡 ESTADO DE FUENTES DISPONIBLES")
    
    # Mostrar tarjetas de estado
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown('<div class="source-card card-aic">', unsafe_allow_html=True)
        st.markdown("### 📄 AIC")
        if fuentes_activas["AIC"]:
            st.success("✅ **ACTIVA**")
            st.write(f"**Registros:** {len(datos_aic)}")
            st.write(f"**Días:** {len(set([d['Fecha'] for d in datos_aic]))}")
            if datos_aic:
                st.write(f"**Ejemplo:** {datos_aic[0]['Fecha']} - {datos_aic[0]['Temp']}")
        else:
            st.error("❌ **INACTIVA**")
        st.caption(mensajes["AIC"])
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="source-card card-smn">', unsafe_allow_html=True)
        st.markdown("### ⏰ SMN")
        if fuentes_activas["SMN"]:
            if datos_smn.get('chapelco_encontrado'):
                st.success("✅ **ACTIVA (CHAPELCO)**")
                st.write("**Estado:** Datos encontrados")
            else:
                st.warning("⚠️ **ESTRUCTURA**")
                st.write("**Estado:** Esperando datos")
            if datos_smn.get('archivo_txt'):
                st.write(f"**Archivo:** {datos_smn['archivo_txt']}")
        else:
            st.error("❌ **INACTIVA**")
        st.caption(mensajes["SMN"])
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="source-card card-om">', unsafe_allow_html=True)
        st.markdown("### 🛰️ Open-Meteo")
        if fuentes_activas["OM"]:
            st.success("✅ **ACTIVA**")
            st.write(f"**Días:** {len(datos_om)}")
            if datos_om:
                primer_fecha = list(datos_om.keys())[0]
                st.write(f"**Ejemplo:** {primer_fecha}")
                st.write(f"Temp: {datos_om[primer_fecha]['t_min']:.1f}°C/{datos_om[primer_fecha]['t_max']:.1f}°C")
        else:
            st.error("❌ **INACTIVA**")
        st.caption(mensajes["OM"])
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Resumen final
    st.markdown("---")
    fuentes_totales = sum(fuentes_activas.values())
    fuentes_con_datos = sum([1 for k,v in fuentes_activas.items() if v and (
        (k == 'AIC' and datos_aic) or 
        (k == 'SMN' and datos_smn.get('chapelco_encontrado')) or 
        (k == 'OM' and datos_om)
    )])
    
    if fuentes_con_datos >= 2:
        st.success(f"✅ **{fuentes_con_datos}/{fuentes_totales}** fuentes con datos - Síntesis óptima")
    elif fuentes_con_datos == 1:
        st.warning(f"⚠️ **{fuentes_con_datos}/{fuentes_totales}** fuentes con datos - Síntesis básica")
    else:
        st.error(f"❌ **{fuentes_con_datos}/{fuentes_totales}** fuentes con datos - Sin datos suficientes")

# ============================================================================
# 5. INFORMACIÓN FINAL
# ============================================================================

st.markdown("---")
st.caption(f"""
**🏔️ Sistema de Fusión Meteorológica SMA v7.0** | 
Ponderación 40/60 Local/Global | 
IA: Gemini Pro | 
Última actualización: {datetime.now().strftime("%d/%m/%Y %H:%M")}
""")

# Información en sidebar
st.sidebar.markdown("---")
st.sidebar.markdown("""
### 📊 Escenarios soportados:

**🎯 Escenario ideal:**
- AIC ✅ + SMN ✅ + Open-Meteo ✅
- **Síntesis:** Completa (40/60)

**⚠️ Escenario básico:**
- Open-Meteo ✅
- **Síntesis:** Básica (100% modelos)

**🔧 Escenario mixto:**
- Cualquier combinación disponible
- **Síntesis:** Ajustada automáticamente

### 🔍 Debug:
Si la IA falla:
1. Verifica la API Key
2. Cambia el modelo en el selector
3. Revisa la consola para errores
""")
