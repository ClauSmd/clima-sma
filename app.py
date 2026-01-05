import streamlit as st
import requests
from datetime import datetime, timedelta
import zipfile
import io
import re
import pdfplumber
import time
import urllib3

# Deshabilitar warnings de SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuración de página
st.set_page_config(page_title="Sistema Climático SMA", page_icon="🏔️", layout="wide")

# CSS personalizado
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #262730;
        border-radius: 8px 8px 0px 0px;
        padding: 10px 20px;
    }
    .metric-card {
        background-color: #1a1a1a;
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #4CAF50;
    }
    .metric-card-error {
        border-left: 4px solid #FF4B4B;
    }
    .metric-card-warning {
        border-left: 4px solid #FFA500;
    }
</style>
""", unsafe_allow_html=True)

# Título principal
st.title("🌤️ Sistema de Fusión Meteorológica - San Martín de los Andes")
st.markdown("---")

# Sidebar para configuración
with st.sidebar:
    st.header("⚙️ Configuración")
    fecha_base = st.date_input("Fecha de inicio", datetime.now().date())
    
    st.markdown("---")
    st.header("🔧 Opciones de Debug")
    debug_mode = st.checkbox("Modo Debug Detallado", value=True)
    mostrar_crudo = st.checkbox("Mostrar Datos Crudos", value=True)
    
    st.markdown("---")
    st.info("""
    **Versión 4.1 - Debug Mode**
    
    Este modo muestra información detallada
    para diagnosticar problemas con las
    fuentes de datos.
    """)

# Funciones principales
def obtener_datos_aic(fecha_base):
    """Obtiene datos del PDF de AIC"""
    urls = [
        "https://www.aic.gob.ar/sitio/extendido-pdf?a=1029&z=1750130550",
        "https://www.aic.gob.ar/sitio/extendido-pdf?id_localidad=22&id_pronostico=1",
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/pdf, */*',
    }
    
    for url in urls:
        try:
            response = requests.get(url, headers=headers, verify=False, timeout=30)
            
            if response.status_code == 200 and response.content[:4] == b'%PDF':
                with pdfplumber.open(io.BytesIO(response.content)) as pdf:
                    texto = pdf.pages[0].extract_text()
                    
                    if texto and len(texto.strip()) > 100:
                        datos = parsear_aic_texto(texto, fecha_base)
                        if datos:
                            return datos, True, f"✅ {len(datos)} días obtenidos"
                        else:
                            return [], False, "❌ Error parseando PDF"
            
            time.sleep(1)
        except Exception as e:
            continue
    
    return [], False, "❌ No se pudo conectar"

def parsear_aic_texto(texto, fecha_base):
    """Parsea texto del PDF de AIC"""
    try:
        lineas = [line.strip() for line in texto.split('\n') if line.strip()]
        
        if len(lineas) < 10:
            return []
        
        # Extraer fechas (línea 2 generalmente)
        fechas = []
        for i in range(1, min(5, len(lineas))):
            fechas_encontradas = re.findall(r'\d{2}-\d{2}-\d{4}', lineas[i])
            if fechas_encontradas:
                fechas = fechas_encontradas
                break
        
        if not fechas:
            return []
        
        # Buscar temperaturas
        temperaturas = []
        for linea in lineas:
            matches = re.findall(r'(-?\d+)\s*[ºC°C]', linea)
            if matches:
                temperaturas.extend([float(m) for m in matches])
        
        # Buscar condiciones
        condiciones = []
        palabras_clave = ['Despejado', 'Nublado', 'Lluvia', 'Tormenta', 'Mayormente', 'Parcialmente']
        for linea in lineas[3:8]:
            for palabra in palabras_clave:
                if palabra in linea:
                    condiciones.append(linea.strip())
                    break
        
        # Crear datos estructurados
        datos = []
        fecha_actual = None
        
        for i, fecha_str in enumerate(fechas[:3]):  # Máximo 3 días
            try:
                fecha_dt = datetime.strptime(fecha_str, '%d-%m-%Y').date()
                if fecha_dt >= fecha_base:
                    dato = {
                        'fecha': fecha_str,
                        'fecha_dt': fecha_dt,
                        'periodo': 'Día',
                        'condicion': condiciones[i] if i < len(condiciones) else 'No especificado'
                    }
                    
                    # Agregar temperaturas si hay
                    if i * 2 + 1 < len(temperaturas):
                        dato['temp_min'] = temperaturas[i * 2]
                        dato['temp_max'] = temperaturas[i * 2 + 1]
                    elif i < len(temperaturas):
                        dato['temp'] = temperaturas[i]
                    
                    datos.append(dato)
            except:
                continue
        
        return datos
    except Exception as e:
        return []

def obtener_datos_smn():
    """Obtiene datos del Servicio Meteorológico Nacional"""
    url = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=pron5d"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/zip, */*',
    }
    
    try:
        # Descargar archivo
        response = requests.get(url, headers=headers, timeout=30, verify=False)
        
        if response.status_code != 200:
            return {}, False, f"❌ Error HTTP {response.status_code}"
        
        if len(response.content) < 100:
            return {}, False, "❌ Contenido vacío"
        
        # Intentar abrir como ZIP
        with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
            # Buscar archivos txt
            txt_files = [f for f in zip_file.namelist() if f.endswith('.txt')]
            
            if not txt_files:
                return {}, False, "❌ No hay archivos txt en el ZIP"
            
            # Leer primer archivo txt
            with zip_file.open(txt_files[0]) as txt_file:
                contenido = txt_file.read().decode('utf-8', errors='ignore')
                
                if debug_mode:
                    with st.expander("📄 Contenido completo del TXT SMN"):
                        st.text_area("Contenido:", contenido[:5000], height=300)
                
                # Buscar Chapelco
                if 'CHAPELCO' in contenido.upper():
                    datos = parsear_contenido_smn(contenido)
                    if datos:
                        return datos, True, f"✅ {len(datos)} días obtenidos"
                    else:
                        return {}, False, "❌ No se pudieron parsear los datos"
                else:
                    return {}, False, "❌ No se encontró 'CHAPELCO' en el contenido"
    
    except zipfile.BadZipFile:
        return {}, False, "❌ Archivo no es un ZIP válido"
    except Exception as e:
        return {}, False, f"❌ Error: {str(e)}"

def parsear_contenido_smn(contenido):
    """Parsea el contenido del TXT del SMN"""
    try:
        datos = {}
        
        # Convertir a mayúsculas para búsqueda
        contenido_upper = contenido.upper()
        
        # Encontrar la posición de CHAPELCO
        idx_chapelco = contenido_upper.find('CHAPELCO')
        if idx_chapelco == -1:
            return {}
        
        # Extraer sección relevante (5000 caracteres después de CHAPELCO)
        seccion = contenido[idx_chapelco:idx_chapelco + 5000]
        
        if debug_mode:
            with st.expander("🔍 Sección Chapelco del TXT"):
                st.text(seccion[:2000])
        
        # Buscar líneas con fechas y temperaturas
        lineas = seccion.split('\n')
        
        for linea in lineas:
            linea = linea.strip()
            
            # Buscar patrones de fecha
            patrones_fecha = [
                r'(\d{2})/([A-Z]{3})/(\d{4})',  # 01/ENE/2024
                r'(\d{2})-([A-Z]{3})-(\d{4})',  # 01-ENE-2024
                r'(\d{2})\s+([A-Z]{3})\s+(\d{4})',  # 01 ENE 2024
            ]
            
            fecha_match = None
            for patron in patrones_fecha:
                fecha_match = re.search(patron, linea, re.IGNORECASE)
                if fecha_match:
                    break
            
            if fecha_match:
                # Extraer fecha
                dia = fecha_match.group(1)
                mes_abr = fecha_match.group(2).upper()
                año = fecha_match.group(3)
                
                # Convertir mes abreviado a número
                meses = {
                    'ENE': '01', 'FEB': '02', 'MAR': '03', 'ABR': '04',
                    'MAY': '05', 'JUN': '06', 'JUL': '07', 'AGO': '08',
                    'SEP': '09', 'OCT': '10', 'NOV': '11', 'DIC': '12'
                }
                
                if mes_abr in meses:
                    fecha_str = f"{dia}-{meses[mes_abr]}-{año}"
                    
                    # Buscar temperaturas en la línea
                    temp_matches = re.findall(r'(-?\d+\.?\d*)', linea[fecha_match.end():])
                    if temp_matches:
                        try:
                            temp = float(temp_matches[0])
                            
                            # Buscar viento
                            viento_match = re.search(r'(\d+)\s*km/h', linea)
                            viento = int(viento_match.group(1)) if viento_match else 0
                            
                            fecha_dt = datetime.strptime(fecha_str, '%d-%m-%Y').date()
                            
                            datos[fecha_str] = {
                                't_max': temp,
                                't_min': temp,
                                'v_max': viento,
                                'fecha_dt': fecha_dt
                            }
                            
                        except ValueError:
                            continue
        
        return datos
    
    except Exception as e:
        if debug_mode:
            st.error(f"Error parseando SMN: {e}")
        return {}

def obtener_datos_satelital(fecha_base):
    """Obtiene datos de API satelital"""
    start_date = fecha_base.strftime("%Y-%m-%d")
    end_date = (fecha_base + timedelta(days=2)).strftime("%Y-%m-%d")
    
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude=-40.1579&longitude=-71.3534&"
            f"daily=temperature_2m_max,temperature_2m_min,windspeed_10m_max,windgusts_10m_max&"
            f"timezone=America%2FArgentina%2FBuenos_Aires&"
            f"start_date={start_date}&end_date={end_date}"
        )
        
        response = requests.get(url, timeout=15)
        datos = response.json()
        
        if 'daily' in datos:
            datos_procesados = {}
            fechas = datos['daily']['time']
            
            for i, fecha_str in enumerate(fechas):
                try:
                    fecha_dt = datetime.strptime(fecha_str, '%Y-%m-%d').date()
                    fecha_key = fecha_dt.strftime('%d-%m-%Y')
                    
                    datos_procesados[fecha_key] = {
                        't_max': datos['daily']['temperature_2m_max'][i],
                        't_min': datos['daily']['temperature_2m_min'][i],
                        'v_prom': datos['daily']['windspeed_10m_max'][i],
                        'v_max': datos['daily']['windgusts_10m_max'][i],
                        'fecha_dt': fecha_dt
                    }
                except (IndexError, ValueError):
                    continue
            
            return datos_procesados, True, f"✅ {len(datos_procesados)} días obtenidos"
        
        return {}, False, "❌ No hay datos diarios"
    
    except Exception as e:
        return {}, False, f"❌ Error: {str(e)}"

def mostrar_resumen_fuentes(datos_aic, datos_smn, datos_sat, estados, mensajes):
    """Muestra resumen de fuentes en métricas"""
    cols = st.columns(3)
    
    with cols[0]:
        st.metric(
            label="AIC",
            value="✅ Activo" if estados["AIC"] else "❌ Inactivo",
            delta=mensajes["AIC"]
        )
        if datos_aic:
            st.caption(f"{len(datos_aic)} días disponibles")
    
    with cols[1]:
        st.metric(
            label="SMN",
            value="✅ Activo" if estados["SMN"] else "❌ Inactivo",
            delta=mensajes["SMN"]
        )
        if datos_smn:
            st.caption(f"{len(datos_smn)} días disponibles")
    
    with cols[2]:
        st.metric(
            label="Satélite",
            value="✅ Activo" if estados["SAT"] else "❌ Inactivo",
            delta=mensajes["SAT"]
        )
        if datos_sat:
            st.caption(f"{len(datos_sat)} días disponibles")

# Botón principal
if st.button("🚀 EJECUTAR CAPTURA DE DATOS", type="primary", use_container_width=True):
    
    # Placeholders para progreso
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Inicializar datos
    datos_aic, datos_smn, datos_sat = [], {}, {}
    estados = {"AIC": False, "SMN": False, "SAT": False}
    mensajes = {"AIC": "", "SMN": "", "SAT": ""}
    
    # 1. Obtener datos AIC
    status_text.text("📡 Capturando datos AIC...")
    progress_bar.progress(20)
    datos_aic, estados["AIC"], mensajes["AIC"] = obtener_datos_aic(fecha_base)
    
    # 2. Obtener datos SMN
    status_text.text("📡 Capturando datos SMN...")
    progress_bar.progress(50)
    datos_smn, estados["SMN"], mensajes["SMN"] = obtener_datos_smn()
    
    # 3. Obtener datos satelitales
    status_text.text("📡 Capturando datos satelitales...")
    progress_bar.progress(80)
    datos_sat, estados["SAT"], mensajes["SAT"] = obtener_datos_satelital(fecha_base)
    
    # Completar progreso
    progress_bar.progress(100)
    status_text.text("✅ Captura completada")
    
    # Mostrar resumen
    st.markdown("---")
    st.subheader("📊 RESUMEN DE FUENTES")
    mostrar_resumen_fuentes(datos_aic, datos_smn, datos_sat, estados, mensajes)
    
    # Mostrar detalles si está en debug mode
    if debug_mode or mostrar_crudo:
        st.markdown("---")
        st.subheader("🔍 DETALLES DE DATOS")
        
        tabs = st.tabs(["📄 AIC", "📊 SMN", "🛰️ SATÉLITE", "📈 COMPARACIÓN"])
        
        with tabs[0]:
            if datos_aic:
                st.write(f"**{len(datos_aic)} días obtenidos:**")
                for dato in datos_aic:
                    with st.expander(f"{dato['fecha']} ({dato.get('periodo', 'Día')})"):
                        st.json(dato)
            else:
                st.warning("No hay datos de AIC")
                st.info(mensajes["AIC"])
        
        with tabs[1]:
            if datos_smn:
                st.write(f"**{len(datos_smn)} días obtenidos:**")
                for fecha, valores in datos_smn.items():
                    with st.expander(fecha):
                        st.json(valores)
            else:
                st.warning("No hay datos de SMN")
                st.info(mensajes["SMN"])
                
                # Mostrar sugerencias para SMN
                st.markdown("---")
                st.subheader("💡 Sugerencias para solucionar SMN:")
                st.write("""
                1. Verificar que la URL del SMN esté accesible
                2. Revisar el formato del archivo TXT dentro del ZIP
                3. Verificar si 'CHAPELCO' aparece con otro nombre
                4. Comprobar la estructura de datos en el archivo
                """)
        
        with tabs[2]:
            if datos_sat:
                st.write(f"**{len(datos_sat)} días obtenidos:**")
                for fecha, valores in datos_sat.items():
                    with st.expander(fecha):
                        st.json(valores)
            else:
                st.warning("No hay datos satelitales")
                st.info(mensajes["SAT"])
        
        with tabs[3]:
            # Comparar temperaturas si hay datos de múltiples fuentes
            fuentes_con_datos = sum([1 for d in [datos_aic, datos_smn, datos_sat] if d])
            
            if fuentes_con_datos >= 2:
                st.success(f"✅ {fuentes_con_datos}/3 fuentes con datos")
                
                # Crear tabla comparativa
                fechas_comunes = set()
                if datos_aic:
                    fechas_comunes.update([d['fecha'] for d in datos_aic])
                if datos_smn:
                    fechas_comunes.update(datos_smn.keys())
                if datos_sat:
                    fechas_comunes.update(datos_sat.keys())
                
                if fechas_comunes:
                    st.write("**Fechas disponibles:**")
                    for fecha in sorted(fechas_comunes)[:5]:  # Mostrar max 5
                        st.write(f"- {fecha}")
            else:
                st.warning("Se necesitan al menos 2 fuentes para comparación")
    
    # Footer
    st.markdown("---")
    st.caption(f"Última actualización: {datetime.now().strftime('%H:%M:%S')}")

# Información en sidebar inferior
st.sidebar.markdown("---")
st.sidebar.markdown("""
**Estado del sistema:**
- ✅ Satélite: Siempre activo
- ⚠️ AIC: Depende del PDF
- ⚠️ SMN: Depende del ZIP/TXT

**Próximos pasos:**
1. Verificar datos SMN
2. Corregir parseo si es necesario
3. Activar fusión con IA
""")
