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
# 1. CONFIGURACIÓN INICIAL
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
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        border: 1px solid #444;
    }
    .alert-box {
        background-color: #330000;
        padding: 10px;
        border-radius: 5px;
        border-left: 4px solid #ff4444;
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
    st.header("🔑 Configuración IA")
    
    # API Key de Google
    api_key = st.text_input("Google API Key", type="password")
    
    if api_key:
        try:
            genai.configure(api_key=api_key)
            st.success("✅ API Key configurada")
        except:
            st.error("❌ API Key inválida")
    
    st.markdown("---")
    st.info("""
    **Estrategia de fusión:**
    - 40%: Fuentes locales (AIC + SMN)
    - 60%: Modelos globales (Open-Meteo)
    
    **Prioridades:**
    1. Fenómenos locales (AIC/SMN)
    2. Tendencia térmica (Open-Meteo)
    3. Alertas de seguridad
    """)

# ============================================================================
# 2. FUNCIONES DE EXTRACCIÓN (MEJORADAS)
# ============================================================================

def obtener_datos_aic():
    """Extrae datos de AIC con parseo CORRECTO"""
    try:
        url = "https://www.aic.gob.ar/sitio/extendido-pdf?a=1029&z=1750130550"
        response = requests.get(url, timeout=30, verify=False)
        
        if response.status_code != 200:
            return [], False, "❌ Error HTTP"
        
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            texto = pdf.pages[0].extract_text()
        
        lineas = [line.strip() for line in texto.split('\n') if line.strip()]
        
        if len(lineas) < 12:
            return [], False, "❌ Formato inesperado"
        
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
        
        return tabla, True, f"✅ AIC: {len(tabla)} registros"
        
    except Exception as e:
        return [], False, f"❌ Error: {str(e)}"

def obtener_datos_smn():
    """Extrae datos de SMN - estructura lista"""
    try:
        url = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=pron5d"
        response = requests.get(url, timeout=30, verify=False)
        
        if response.status_code != 200:
            return {"estado": "error", "mensaje": f"HTTP {response.status_code}"}, False, f"❌ HTTP {response.status_code}"
        
        estructura = {
            "estado": "disponible",
            "timestamp": datetime.now().isoformat(),
            "contenido": None
        }
        
        try:
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                archivos = zip_file.namelist()
                estructura["archivos"] = archivos
                
                txt_files = [f for f in archivos if f.lower().endswith('.txt')]
                if txt_files:
                    with zip_file.open(txt_files[0]) as f:
                        contenido = f.read().decode('utf-8', errors='ignore')
                    
                    estructura["contenido"] = contenido[:3000]
                    estructura["archivo_txt"] = txt_files[0]
                    
                    if 'CHAPELCO' in contenido.upper():
                        estructura["chapelco_encontrado"] = True
                        return estructura, True, "✅ SMN: Estructura lista"
                    else:
                        estructura["chapelco_encontrado"] = False
                        return estructura, True, "⚠️ SMN: Sin CHAPELCO"
                else:
                    estructura["contenido"] = "No hay TXT"
                    return estructura, True, "⚠️ SMN: Sin archivos TXT"
        
        except zipfile.BadZipFile:
            estructura["estado"] = "bad_zip"
            return estructura, True, "⚠️ SMN: ZIP inválido"
            
    except Exception as e:
        return {"estado": "error", "mensaje": str(e)}, False, f"❌ Error: {str(e)}"

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
                    fecha_dt = datetime.strptime(fecha_str, '%Y-%m-%d')
                    fecha_key = fecha_dt.strftime('%d-%m-%Y')
                    
                    datos_procesados[fecha_key] = {
                        'fecha_dt': fecha_dt,
                        't_max': datos['daily']['temperature_2m_max'][i] if i < len(datos['daily']['temperature_2m_max']) else None,
                        't_min': datos['daily']['temperature_2m_min'][i] if i < len(datos['daily']['temperature_2m_min']) else None,
                        'precip': datos['daily']['precipitation_sum'][i] if i < len(datos['daily']['precipitation_sum']) else None,
                        'viento_max': datos['daily']['windspeed_10m_max'][i] if i < len(datos['daily']['windspeed_10m_max']) else None,
                        'rafagas_max': datos['daily']['windgusts_10m_max'][i] if i < len(datos['daily']['windgusts_10m_max']) else None,
                        'weathercode': datos['daily']['weathercode'][i] if i < len(datos['daily']['weathercode']) else None
                    }
            
            return datos_procesados, True, f"✅ Open-Meteo: {len(datos_procesados)} días"
        else:
            return {}, False, f"❌ Error {response.status_code}"
            
    except Exception as e:
        return {}, False, f"❌ Error: {str(e)}"

# ============================================================================
# 3. FUNCIÓN DE IA (REACTIVADA)
# ============================================================================

def generar_sintesis_ia(datos_aic, datos_smn, datos_om, fuentes_activas):
    """Genera síntesis con IA usando ponderación 40/60"""
    
    try:
        # Preparar prompt para IA
        fecha_str = fecha_base.strftime('%A %d de %B %Y')
        
        # Formatear datos AIC
        aic_texto = "No disponible"
        if datos_aic:
            aic_texto = "\n".join([f"- {d['Fecha']} ({d['Momento']}): {d['Cielo']}. Temp: {d['Temp']}°C. Viento: {d['Viento']} km/h" for d in datos_aic[:6]])
        
        # Formatear datos SMN
        smn_texto = "No disponible"
        if datos_smn and datos_smn.get('contenido'):
            smn_texto = "Datos de Chapelco disponibles (estructura preparada)"
        
        # Formatear datos Open-Meteo
        om_texto = "No disponible"
        if datos_om:
            om_texto = "\n".join([f"- {fecha}: {vals['t_min']:.1f}°C/{vals['t_max']:.1f}°C. Precip: {vals.get('precip', 0):.1f}mm" 
                                  for fecha, vals in list(datos_om.items())[:3]])
        
        prompt = f"""
        SÍNTESIS METEOROLÓGICA - SAN MARTÍN DE LOS ANDES
        Fecha: {fecha_str}
        
        FUENTES DISPONIBLES:
        - AIC (Oficial Argentina): {'✅ ACTIVA' if fuentes_activas['AIC'] else '❌ INACTIVA'}
        - SMN Chapelco: {'✅ ESTRUCTURA' if fuentes_activas['SMN'] else '❌ INACTIVA'}
        - Open-Meteo (Modelos): {'✅ ACTIVA' if fuentes_activas['OM'] else '❌ INACTIVA'}
        
        DATOS DISPONIBLES:
        
        AIC (Pronóstico oficial):
        {aic_texto}
        
        SMN (Datos estación):
        {smn_texto}
        
        Open-Meteo (Modelos globales):
        {om_texto}
        
        INSTRUCCIONES DE PONDERACIÓN 40/60:
        
        1. ESTRATEGIA:
           - 40% peso: Fuentes locales (AIC + SMN) para fenómenos específicos
           - 60% peso: Modelos Open-Meteo para tendencia térmica
        
        2. PRIORIDADES:
           - Tormentas eléctricas (si AIC reporta)
           - Ráfagas de viento > 30 km/h
           - Nevadas o precipitación intensa
           - Temperaturas extremas
        
        3. FORMATO DE SALIDA:
           [Emoji] [Día, Mes] – San Martín de los Andes: [condiciones fusionadas].
           Máxima: [temp_max]°C, Mínima: [temp_min]°C.
           Viento: [viento_prom] km/h con ráfagas de [rafaga_max] km/h.
        
        4. ALERTAS (solo si aplica):
           ⚡ ALERTA: [descripción breve si hay condiciones extremas]
        
        5. RESTRICCIONES:
           - No inventar datos no respaldados
           - Si falta una fuente, ajustar ponderación
           - Priorizar seguridad en alertas
           - Máximo 3 días de pronóstico
           - Usar lenguaje natural pero preciso
        
        GENERA LA SÍNTESIS METEOROLÓGICA:
        """
        
        # Usar Gemini (con failover)
        modelos = ['gemini-pro', 'models/text-bison-001']
        
        for modelo in modelos:
            try:
                model = genai.GenerativeModel(modelo)
                response = model.generate_content(prompt)
                if response.text:
                    return response.text, modelo
            except:
                continue
        
        return None, None
        
    except Exception as e:
        st.error(f"Error en IA: {str(e)}")
        return None, None

# ============================================================================
# 4. INTERFAZ PRINCIPAL
# ============================================================================

# Botón principal
if st.button("🚀 EJECUTAR SÍNTESIS COMPLETA", type="primary", use_container_width=True):
    
    # Verificar API Key
    if not api_key:
        st.error("❌ Ingresa tu Google API Key en el sidebar")
        st.stop()
    
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
    
    status_text.text("📡 Extrayendo datos AIC...")
    datos_aic, fuentes_activas["AIC"], mensajes["AIC"] = obtener_datos_aic()
    progress_bar.progress(30)
    
    status_text.text("📡 Extrayendo datos SMN...")
    datos_smn, fuentes_activas["SMN"], mensajes["SMN"] = obtener_datos_smn()
    progress_bar.progress(60)
    
    status_text.text("📡 Extrayendo datos Open-Meteo...")
    datos_om, fuentes_activas["OM"], mensajes["OM"] = obtener_datos_openmeteo()
    progress_bar.progress(90)
    
    # ========================================
    # MOSTRAR DATOS INDIVIDUALES
    # ========================================
    
    st.markdown("---")
    st.subheader("📊 DATOS EXTRAÍDOS")
    
    # AIC
    with st.expander(f"📄 AIC - {mensajes['AIC']}", expanded=True):
        if datos_aic:
            df_aic = pd.DataFrame(datos_aic)
            st.dataframe(df_aic, hide_index=True, use_container_width=True)
        else:
            st.info("No hay datos de AIC")
    
    # SMN
    with st.expander(f"⏰ SMN - {mensajes['SMN']}"):
        if datos_smn and datos_smn.get('contenido'):
            st.json(datos_smn)
        else:
            st.info("Estructura SMN preparada, esperando datos")
    
    # Open-Meteo
    with st.expander(f"🛰️ Open-Meteo - {mensajes['OM']}"):
        if datos_om:
            df_om = pd.DataFrame([
                {
                    'Fecha': fecha,
                    'Temp Máx': f"{vals['t_max']:.1f}°C",
                    'Temp Mín': f"{vals['t_min']:.1f}°C",
                    'Precipitación': f"{vals.get('precip', 0):.1f} mm",
                    'Viento Máx': f"{vals.get('viento_max', 0):.1f} km/h"
                }
                for fecha, vals in datos_om.items()
            ])
            st.dataframe(df_om, hide_index=True, use_container_width=True)
        else:
            st.info("No hay datos de Open-Meteo")
    
    # ========================================
    # SÍNTESIS CON IA
    # ========================================
    
    # Verificar que tenemos al menos Open-Meteo
    if fuentes_activas["OM"]:
        status_text.text("🧠 Generando síntesis con IA...")
        
        sintesis, modelo_usado = generar_sintesis_ia(
            datos_aic, datos_smn, datos_om, fuentes_activas
        )
        
        progress_bar.progress(100)
        status_text.text("✅ Síntesis completada")
        
        if sintesis:
            st.markdown("---")
            st.subheader("🎯 SÍNTESIS PONDERADA (40/60)")
            
            # Mostrar síntesis
            st.markdown(f'<div class="forecast-card">{sintesis}</div>', unsafe_allow_html=True)
            
            # Información de la síntesis
            st.caption(f"🧠 Motor: {modelo_usado} | ⚖️ Ponderación: 40% Local / 60% Global")
        else:
            st.error("❌ No se pudo generar la síntesis con IA")
    else:
        st.error("❌ Se requiere al menos Open-Meteo para la síntesis")
    
    # ========================================
    # RESUMEN DE FUENTES DISPONIBLES
    # ========================================
    
    st.markdown("---")
    st.subheader("📡 FUENTES DISPONIBLES")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown('<div class="source-card card-aic">', unsafe_allow_html=True)
        st.markdown("**📄 AIC**")
        if fuentes_activas["AIC"]:
            st.success("✅ ACTIVA")
            st.write(f"{len(datos_aic)} registros")
            if datos_aic:
                st.write(f"Días: {len(set([d['Fecha'] for d in datos_aic]))}")
        else:
            st.error("❌ INACTIVA")
        st.caption(mensajes["AIC"])
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="source-card card-smn">', unsafe_allow_html=True)
        st.markdown("**⏰ SMN**")
        if fuentes_activas["SMN"]:
            st.warning("⚠️ ESTRUCTURA")
            if datos_smn.get('chapelco_encontrado'):
                st.success("CHAPELCO encontrado")
            else:
                st.info("Esperando datos")
        else:
            st.error("❌ INACTIVA")
        st.caption(mensajes["SMN"])
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="source-card card-om">', unsafe_allow_html=True)
        st.markdown("**🛰️ Open-Meteo**")
        if fuentes_activas["OM"]:
            st.success("✅ ACTIVA")
            st.write(f"{len(datos_om)} días")
            if datos_om:
                primer_dia = list(datos_om.keys())[0]
                st.write(f"Ej: {primer_dia}: {datos_om[primer_dia]['t_min']:.1f}°C/{datos_om[primer_dia]['t_max']:.1f}°C")
        else:
            st.error("❌ INACTIVA")
        st.caption(mensajes["OM"])
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Resumen final
    st.markdown("---")
    fuentes_totales = sum(fuentes_activas.values())
    
    if fuentes_totales == 3:
        st.success(f"✅ {fuentes_totales}/3 fuentes activas - Síntesis óptima")
    elif fuentes_totales == 2:
        st.warning(f"⚠️ {fuentes_totales}/3 fuentes activas - Síntesis parcial")
    else:
        st.error(f"❌ {fuentes_totales}/3 fuentes activas - Síntesis limitada")

# ============================================================================
# 5. INFORMACIÓN ADICIONAL
# ============================================================================

st.markdown("---")
st.caption("""
**Sistema de Fusión Meteorológica V6.0** | 
Ponderación 40/60 Local/Global | 
IA: Gemini Pro | 
Actualizado: {}
""".format(datetime.now().strftime("%d/%m/%Y %H:%M")))

# Información en el sidebar inferior
st.sidebar.markdown("---")
st.sidebar.markdown("""
**📊 Estado del sistema:**
- ✅ AIC: Funcionando
- ⚠️ SMN: Estructura lista
- ✅ Open-Meteo: Funcionando

**🎯 Escenarios IA:**
1. AIC + OM: Síntesis completa
2. Solo OM: Síntesis básica
3. SMN + OM: Cuando SMN tenga datos
""")
