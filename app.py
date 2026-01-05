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
import json

# Deshabilitar warnings de SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================================================
# 1. CONFIGURACIÓN SEGURA - SIN API KEY EN CÓDIGO
# ============================================================================

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
    .warning-box {
        background-color: #332200;
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid #ffaa00;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# Título principal
st.markdown('<div class="main-header"><h1>🏔️ Sistema de Fusión Meteorológica SMA</h1><p>Ponderación 40/60: AIC+SMN (40%) + Open-Meteo (60%)</p></div>', unsafe_allow_html=True)

# ============================================================================
# 2. CONFIGURACIÓN DE API KEY (SEGURA)
# ============================================================================

# Sidebar con configuración
with st.sidebar:
    st.header("⚙️ Configuración")
    
    # Fecha base
    fecha_base = st.date_input("Fecha de inicio", datetime.now().date())
    
    st.markdown("---")
    st.header("🔑 Configuración IA")
    
    # Opciones para API Key (múltiples formas seguras)
    api_key_option = st.radio(
        "Fuente de API Key:",
        ["Streamlit Secrets", "Ingresar manualmente", "Sin IA (solo datos)"]
    )
    
    api_key = None
    
    if api_key_option == "Streamlit Secrets":
        try:
            # Intentar obtener de secrets (forma segura)
            api_key = st.secrets["GOOGLE_API_KEY"]
            st.success("✅ API Key cargada desde secrets")
        except:
            st.warning("⚠️ No se encontró GOOGLE_API_KEY en secrets")
            st.info("Agrega tu API Key en: Configuración → Secrets de Streamlit")
    
    elif api_key_option == "Ingresar manualmente":
        # Input temporal (solo para desarrollo)
        api_key = st.text_input("Google API Key", type="password")
        if api_key:
            st.warning("⚠️ ADVERTENCIA: No expongas tu API Key en producción")
    
    elif api_key_option == "Sin IA (solo datos)":
        st.info("📊 Solo se mostrarán los datos crudos")
    
    # Configurar Gemini si hay API Key
    if api_key:
        try:
            genai.configure(api_key=api_key)
            st.success("✅ Gemini configurado")
            
            # Intentar listar modelos disponibles
            try:
                models = genai.list_models()
                model_names = [model.name for model in models]
                
                # Filtrar modelos de generación
                available_models = []
                for model in model_names:
                    if 'generateContent' in model.supported_generation_methods:
                        available_models.append(model.name)
                
                if available_models:
                    st.write(f"**Modelos disponibles ({len(available_models)}):**")
                    for model in available_models[:5]:  # Mostrar primeros 5
                        st.caption(f"• {model.split('/')[-1]}")
            except:
                st.info("No se pudieron listar modelos")
                
        except Exception as e:
            st.error(f"❌ Error configurando Gemini: {e}")
    
    st.markdown("---")
    st.info("""
    **📊 Estrategia de fusión:**
    - 40%: Fuentes locales (AIC + SMN)
    - 60%: Modelos globales (Open-Meteo)
    
    **🔧 Sin API Key?** 
    El sistema mostrará:
    1. Datos crudos de todas las fuentes
    2. Estado de disponibilidad
    3. Estructura lista para cuando actives la IA
    """)

# ============================================================================
# 3. FUNCIONES DE EXTRACCIÓN (MANTENIDAS)
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
                
                # Buscar archivo TXT
                txt_files = [f for f in archivos if f.lower().endswith('.txt')]
                
                if txt_files:
                    archivo_txt = txt_files[0]
                    with zip_file.open(archivo_txt) as f:
                        contenido = f.read().decode('utf-8', errors='ignore')
                    
                    estructura["archivo_txt"] = archivo_txt
                    estructura["contenido_preview"] = contenido[:1000]
                    
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
# 4. FUNCIÓN DE IA CON DETECCIÓN DE MODELOS
# ============================================================================

def detectar_modelos_disponibles():
    """Detecta automáticamente los modelos de Gemini disponibles"""
    
    modelos_prueba = [
        "gemini-1.5-pro",      # Última versión
        "gemini-1.0-pro",      # Versión estable
        "gemini-pro",          # Alias común
        "models/gemini-pro",   # Ruta completa
        "gemini-1.5-flash",    # Versión rápida
        "gemini-1.0-pro-001",  # Versión específica
    ]
    
    modelos_funcionales = []
    
    for modelo in modelos_prueba:
        try:
            # Crear instancia temporal
            temp_model = genai.GenerativeModel(modelo)
            
            # Intentar una consulta simple
            response = temp_model.generate_content("Test")
            
            if response.text:
                modelos_funcionales.append(modelo)
                st.sidebar.success(f"✅ {modelo} funciona")
            else:
                st.sidebar.warning(f"⚠️ {modelo} no respondió")
                
        except Exception as e:
            st.sidebar.error(f"❌ {modelo}: {str(e)[:50]}")
            continue
    
    return modelos_funcionales

def generar_sintesis_ia(datos_aic, datos_smn, datos_om, fuentes_activas):
    """Genera síntesis con IA - Con detección de modelos"""
    
    try:
        # Preparar prompt
        fecha_str = fecha_base.strftime('%A %d de %B %Y')
        
        # Formatear datos AIC
        aic_texto = "No disponible"
        if datos_aic:
            aic_lines = []
            for d in datos_aic[:6]:
                aic_lines.append(f"- {d['Fecha']} ({d['Momento']}): {d['Cielo']}. Temp: {d['Temp']}°C. Viento: {d['Viento']} km/h")
            aic_texto = "\n".join(aic_lines)
        
        # Formatear datos SMN
        smn_texto = "No disponible"
        if datos_smn and datos_smn.get('chapelco_encontrado'):
            smn_texto = "Datos de Chapelco disponibles (estructura preparada)"
        
        # Formatear datos Open-Meteo
        om_texto = "No disponible"
        if datos_om:
            om_lines = []
            for fecha, vals in list(datos_om.items())[:3]:
                om_lines.append(f"- {fecha}: {vals['t_min']:.1f}°C/{vals['t_max']:.1f}°C. Precip: {vals.get('precip', 0):.1f}mm")
            om_texto = "\n".join(om_lines)
        
        prompt = f"""
        SÍNTESIS METEOROLÓGICA - SAN MARTÍN DE LOS ANDES
        Fecha: {fecha_str}
        
        FUENTES:
        - AIC: {'✅' if fuentes_activas['AIC'] else '❌'}
        - SMN: {'✅' if fuentes_activas['SMN'] and datos_smn.get('chapelco_encontrado') else '⚠️' if fuentes_activas['SMN'] else '❌'}
        - Open-Meteo: {'✅' if fuentes_activas['OM'] else '❌'}
        
        DATOS AIC:
        {aic_texto}
        
        DATOS OPEN-METEO:
        {om_texto}
        
        Genera un pronóstico conciso para 3 días usando ponderación 40/60 (40% fuentes locales, 60% modelos).
        Formato: [Día] - [condiciones]. Temp: [mín]°C/[máx]°C. Viento: [velocidad] km/h.
        Solo datos reales, no inventar.
        """
        
        # Detectar modelos disponibles
        modelos_disponibles = detectar_modelos_disponibles()
        
        if not modelos_disponibles:
            st.error("❌ No hay modelos de Gemini disponibles")
            return None, None
        
        st.info(f"🔍 Modelos detectados: {', '.join(modelos_disponibles)}")
        
        # Probar cada modelo
        for modelo in modelos_disponibles:
            try:
                st.write(f"🔄 Probando: {modelo}")
                model = genai.GenerativeModel(modelo)
                
                # Configuración conservadora
                generation_config = {
                    "temperature": 0.3,
                    "top_p": 0.8,
                    "top_k": 40,
                    "max_output_tokens": 800,
                }
                
                response = model.generate_content(
                    prompt,
                    generation_config=generation_config,
                    safety_settings=[
                        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
                    ]
                )
                
                if response.text and len(response.text.strip()) > 50:
                    st.success(f"✅ {modelo} funcionó")
                    return response.text, modelo
                    
            except Exception as e:
                st.warning(f"❌ {modelo} falló: {str(e)[:80]}")
                continue
        
        return None, None
        
    except Exception as e:
        st.error(f"❌ Error en IA: {str(e)}")
        return None, None

# ============================================================================
# 5. INTERFAZ PRINCIPAL MEJORADA
# ============================================================================

# Botón principal
if st.button("🚀 EJECUTAR SISTEMA COMPLETO", type="primary", use_container_width=True):
    
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
    
    with st.spinner("📡 Extrayendo datos..."):
        status_text.text("📊 AIC...")
        datos_aic, fuentes_activas["AIC"], mensajes["AIC"] = obtener_datos_aic()
        progress_bar.progress(30)
        
        status_text.text("⏰ SMN...")
        datos_smn, fuentes_activas["SMN"], mensajes["SMN"] = obtener_datos_smn()
        progress_bar.progress(60)
        
        status_text.text("🛰️ Open-Meteo...")
        datos_om, fuentes_activas["OM"], mensajes["OM"] = obtener_datos_openmeteo()
        progress_bar.progress(90)
    
    # ========================================
    # MOSTRAR DATOS
    # ========================================
    
    st.markdown("---")
    st.subheader("📊 DATOS EXTRAÍDOS")
    
    # Mostrar en tabs
    tab1, tab2, tab3 = st.tabs(["📄 AIC", "⏰ SMN", "🛰️ Open-Meteo"])
    
    with tab1:
        if datos_aic:
            df_aic = pd.DataFrame(datos_aic)
            st.dataframe(df_aic, hide_index=True, use_container_width=True)
        else:
            st.info("Sin datos AIC")
    
    with tab2:
        if datos_smn:
            st.json(datos_smn, expanded=False)
        else:
            st.info("Estructura SMN preparada")
    
    with tab3:
        if datos_om:
            # Tabla resumida
            resumen = []
            for fecha, vals in datos_om.items():
                resumen.append({
                    'Fecha': fecha,
                    'Máx': f"{vals['t_max']:.1f}°C",
                    'Mín': f"{vals['t_min']:.1f}°C",
                    'Precip': f"{vals.get('precip', 0):.1f} mm",
                    'Viento': f"{vals.get('viento_max', 0):.1f} km/h"
                })
            
            df_om = pd.DataFrame(resumen)
            st.dataframe(df_om, hide_index=True, use_container_width=True)
        else:
            st.info("Sin datos Open-Meteo")
    
    # ========================================
    # SÍNTESIS CON IA (SI HAY API KEY)
    # ========================================
    
    progress_bar.progress(95)
    
    if api_key and (fuentes_activas["OM"] or fuentes_activas["AIC"]):
        with st.spinner("🧠 Generando síntesis con IA..."):
            sintesis, modelo_usado = generar_sintesis_ia(
                datos_aic, datos_smn, datos_om, fuentes_activas
            )
        
        progress_bar.progress(100)
        status_text.text("✅ Proceso completado")
        
        if sintesis:
            st.markdown("---")
            st.subheader("🎯 SÍNTESIS CON IA")
            
            # Mostrar síntesis
            st.markdown(f'<div class="forecast-card">{sintesis}</div>', unsafe_allow_html=True)
            
            # Info del modelo
            st.markdown(f'<div class="model-info">🧠 <strong>Modelo:</strong> {modelo_usado}</div>', unsafe_allow_html=True)
        else:
            st.markdown("---")
            st.subheader("⚠️ SÍNTESIS SIN IA")
            
            # Generar síntesis manual básica
            st.markdown('<div class="warning-box">', unsafe_allow_html=True)
            st.write("**IA no disponible - Datos crudos:**")
            
            if datos_om:
                st.write("**Pronóstico basado en Open-Meteo:**")
                for fecha, vals in list(datos_om.items())[:3]:
                    st.write(f"**{fecha}:** {vals['t_min']:.1f}°C/{vals['t_max']:.1f}°C")
            
            if datos_aic:
                st.write("**Datos AIC disponibles para fusión manual**")
            
            st.markdown('</div>', unsafe_allow_html=True)
    else:
        progress_bar.progress(100)
        status_text.text("✅ Extracción completada")
        
        # Mostrar mensaje según disponibilidad
        if not api_key:
            st.markdown("---")
            st.markdown('<div class="warning-box">', unsafe_allow_html=True)
            st.write("**⚠️ IA DESACTIVADA**")
            st.write("Para activar la síntesis con IA:")
            st.write("1. Agrega tu API Key en Streamlit Secrets")
            st.write("2. O ingrésala manualmente en el sidebar")
            st.write("3. O selecciona 'Sin IA' para solo datos")
            st.markdown('</div>', unsafe_allow_html=True)
    
    # ========================================
    # RESUMEN DE FUENTES
    # ========================================
    
    st.markdown("---")
    st.subheader("📡 ESTADO DE FUENTES")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown('<div class="source-card card-aic">', unsafe_allow_html=True)
        st.markdown("### 📄 AIC")
        estado = "✅ ACTIVA" if fuentes_activas["AIC"] else "❌ INACTIVA"
        st.markdown(f"**{estado}**")
        if datos_aic:
            st.write(f"Registros: {len(datos_aic)}")
        st.caption(mensajes["AIC"])
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="source-card card-smn">', unsafe_allow_html=True)
        st.markdown("### ⏰ SMN")
        if fuentes_activas["SMN"]:
            if datos_smn.get('chapelco_encontrado'):
                st.success("✅ CON DATOS")
            else:
                st.warning("⚠️ ESTRUCTURA")
        else:
            st.error("❌ INACTIVA")
        st.caption(mensajes["SMN"])
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="source-card card-om">', unsafe_allow_html=True)
        st.markdown("### 🛰️ Open-Meteo")
        estado = "✅ ACTIVA" if fuentes_activas["OM"] else "❌ INACTIVA"
        st.markdown(f"**{estado}**")
        if datos_om:
            st.write(f"Días: {len(datos_om)}")
        st.caption(mensajes["OM"])
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Resumen final
    st.markdown("---")
    fuentes_con_datos = sum([
        1 if fuentes_activas["AIC"] and datos_aic else 0,
        1 if fuentes_activas["SMN"] and datos_smn.get('chapelco_encontrado') else 0,
        1 if fuentes_activas["OM"] and datos_om else 0
    ])
    
    if fuentes_con_datos >= 2:
        st.success(f"✅ **{fuentes_con_datos}/3** fuentes con datos - Sistema operativo")
    elif fuentes_con_datos == 1:
        st.warning(f"⚠️ **{fuentes_con_datos}/3** fuentes con datos - Datos limitados")
    else:
        st.error(f"❌ **{fuentes_con_datos}/3** fuentes con datos - Sin datos")

# ============================================================================
# 6. INFORMACIÓN FINAL
# ============================================================================

st.markdown("---")
st.caption(f"""
**🏔️ Sistema de Fusión Meteorológica SMA v8.0** | 
Diseñado para Streamlit Cloud | 
Última actualización: {datetime.now().strftime("%d/%m/%Y %H:%M")}
""")

# Instrucciones en sidebar
st.sidebar.markdown("---")
st.sidebar.markdown("""
### 🚀 Para usar en Streamlit Cloud:

1. **Agrega tu API Key** en:
   - Dashboard de tu app
   - ⚙️ Settings → Secrets
   - Agrega: `GOOGLE_API_KEY = "tu-key-aqui"`

2. **Selecciona** "Streamlit Secrets" en el sidebar

3. **Ejecuta** el sistema

### 🔧 Solución de problemas:

**API Key no funciona:**
- Verifica que sea válida
- Revisa la consola de Streamlit
- Prueba generando una nueva key

**Modelos no disponibles:**
- El sistema detecta automáticamente
- Prueba diferentes modelos
- Revisa tu cuenta de Google AI

**Sin datos:**
- Verifica conexión a internet
- Revisa que las fuentes estén activas
- Intenta más tarde
""")
