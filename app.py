import streamlit as st
import requests
from datetime import datetime, timedelta
import zipfile
import io
import re
import pdfplumber
import time
import urllib3
import json

# Deshabilitar warnings de SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuración de página
st.set_page_config(page_title="Fusión Meteorológica SMA", page_icon="⛈️", layout="wide")

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
    .source-card {
        background-color: #1a1a1a;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 15px;
        border-left: 5px solid;
    }
    .source-aic {
        border-left-color: #4CAF50;
    }
    .source-smn {
        border-left-color: #2196F3;
    }
    .source-sat {
        border-left-color: #FF9800;
    }
    .phenomenon-alert {
        background-color: #330000;
        padding: 10px;
        border-radius: 5px;
        border-left: 4px solid #FF4444;
        margin: 5px 0;
    }
    .hourly-forecast {
        background-color: #1e1e1e;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        border: 1px solid #444;
    }
</style>
""", unsafe_allow_html=True)

# Título principal
st.title("⛈️ Sistema de Fusión Meteorológica - San Martín de los Andes")
st.markdown("**Extracción completa - IA procesará datos brutos**")
st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuración")
    fecha_base = st.date_input("Fecha de inicio", datetime.now().date())
    
    st.markdown("---")
    st.header("🛰️ Configuración Open-Meteo")
    
    st.subheader("Modelos disponibles:")
    modelo_seleccionado = st.selectbox(
        "Seleccionar modelo",
        ["gfs", "icon", "gfs_seamless", "icon_seamless", "best_match"],
        index=4
    )
    
    st.subheader("Período de pronóstico:")
    dias_pronostico = st.slider("Días a pronosticar", 1, 7, 5)
    
    st.markdown("---")
    st.info("""
    **Open-Meteo v1:**
    - Modelos: GFS, ICON, ECMWF IFS
    - Datos: Horarios + Diarios
    - Parámetros reales (sin error 400)
    """)

# ============================================================================
# FUNCIONES DE EXTRACCIÓN COMPLETA - AIC Y SMN (MANTENIDAS)
# ============================================================================

def obtener_datos_aic_completos(fecha_base):
    """Extrae TODOS los datos disponibles del PDF de AIC"""
    urls = [
        "https://www.aic.gob.ar/sitio/extendido-pdf?a=1029&z=1750130550",
        "https://www.aic.gob.ar/sitio/extendido-pdf?id_localidad=22&id_pronostico=1",
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/pdf, */*',
        'Referer': 'https://www.aic.gob.ar/'
    }
    
    for url_idx, url in enumerate(urls):
        try:
            response = requests.get(url, headers=headers, verify=False, timeout=35)
            
            if response.status_code == 200 and response.content[:4] == b'%PDF':
                with pdfplumber.open(io.BytesIO(response.content)) as pdf:
                    texto_completo = ""
                    for pagina in pdf.pages:
                        texto_completo += pagina.extract_text() + "\n"
                    
                    if texto_completo and len(texto_completo.strip()) > 200:
                        datos_completos = parsear_aic_completo(texto_completo, fecha_base)
                        datos_completos['texto_crudo'] = texto_completo[:5000]
                        return datos_completos, True, f"✅ AIC: {len(datos_completos.get('dias', []))} días"
            
            time.sleep(1.5)
        except Exception as e:
            continue
    
    return {}, False, "❌ No se pudo obtener el PDF de AIC"

def parsear_aic_completo(texto, fecha_base):
    """Parsea COMPLETAMENTE el PDF de AIC"""
    datos = {
        'dias': [],
        'fenomenos_especiales': [],
        'advertencias': [],
        'parametros': {}
    }
    
    try:
        lineas = [line.strip() for line in texto.split('\n') if line.strip()]
        
        # Extraer información general
        for i, linea in enumerate(lineas):
            if 'PRONÓSTICO' in linea.upper() and i < 3:
                datos['titulo'] = linea
            if 'VÁLIDO' in linea.upper() or 'PERÍODO' in linea.upper():
                datos['periodo_validez'] = linea
            if any(fen in linea.upper() for fen in ['TORMENTA', 'ELECTRIC', 'GRANIZO', 'NIEVE', 'VIENTO FUERTE', 'ALERTA']):
                if linea not in datos['fenomenos_especiales']:
                    datos['fenomenos_especiales'].append(linea)
            if any(adv in linea.upper() for adv in ['ADVERTENCIA', 'PRECAUCIÓN', 'ATENCIÓN']):
                if linea not in datos['advertencias']:
                    datos['advertencias'].append(linea)
        
        # Buscar fechas
        fechas_encontradas = []
        for linea in lineas[:15]:
            patrones = [r'\d{2}-\d{2}-\d{4}', r'\d{2}/\d{2}/\d{4}', r'\d{2}\s+\d{2}\s+\d{4}']
            for patron in patrones:
                matches = re.findall(patron, linea)
                if matches:
                    fechas_encontradas.extend(matches)
                    break
        
        # Procesar cada fecha
        for fecha_str in fechas_encontradas[:5]:
            try:
                if '-' in fecha_str:
                    fecha_dt = datetime.strptime(fecha_str, '%d-%m-%Y')
                elif '/' in fecha_str:
                    fecha_dt = datetime.strptime(fecha_str, '%d/%m/%Y')
                else:
                    continue
                
                fecha_formateada = fecha_dt.strftime('%d-%m-%Y')
                datos_dia = extraer_datos_para_fecha(texto, fecha_str, fecha_dt.date())
                
                if datos_dia:
                    datos['dias'].append(datos_dia)
                    
            except ValueError:
                continue
        
        # Extraer parámetros generales
        datos['parametros'] = extraer_parametros_generales(texto)
        
        return datos
        
    except Exception as e:
        st.error(f"Error parseando AIC: {str(e)}")
        return datos

def extraer_datos_para_fecha(texto, fecha_str, fecha_dt):
    """Extrae todos los datos para una fecha específica"""
    datos_dia = {
        'fecha': fecha_str,
        'fecha_dt': fecha_dt,
        'periodos': [],
        'temperaturas': {},
        'vientos': {},
        'presion': {},
        'condiciones': {},
        'fenomenos': []
    }
    
    lineas = texto.split('\n')
    
    for i, linea in enumerate(lineas):
        if fecha_str in linea:
            if 'Día' in linea or 'DIA' in linea.upper():
                datos_dia['periodos'].append('Día')
            if 'Noche' in linea or 'NOCHE' in linea.upper():
                datos_dia['periodos'].append('Noche')
            
            for j in range(max(0, i-3), min(len(lineas), i+4)):
                linea_temp = lineas[j]
                
                # Temperaturas
                temps = re.findall(r'(-?\d+\.?\d*)\s*[ºC°C]', linea_temp)
                if temps:
                    for temp in temps:
                        if 'max' not in datos_dia['temperaturas'] or float(temp) > datos_dia['temperaturas'].get('max', -100):
                            datos_dia['temperaturas']['max'] = float(temp)
                        if 'min' not in datos_dia['temperaturas'] or float(temp) < datos_dia['temperaturas'].get('min', 100):
                            datos_dia['temperaturas']['min'] = float(temp)
                
                # Vientos
                vientos = re.findall(r'(\d+)\s*km/h', linea_temp)
                if vientos:
                    for viento in vientos:
                        datos_dia['vientos']['velocidad'] = int(viento)
                
                # Dirección del viento
                direcciones = ['N', 'S', 'E', 'O', 'NE', 'NO', 'SE', 'SO', 'NNE', 'NNO', 'SSE', 'SSO']
                for dir in direcciones:
                    if f' {dir} ' in f' {linea_temp} ':
                        datos_dia['vientos']['direccion'] = dir
                
                # Presión
                presiones = re.findall(r'(\d+)\s*hPa', linea_temp)
                if presiones:
                    datos_dia['presion']['valor'] = int(presiones[0])
                
                # Condiciones
                condiciones = ['Despejado', 'Nublado', 'Parcialmente', 'Mayormente', 'Cubierto', 
                              'Lluvia', 'Lluvioso', 'Tormenta', 'Nieve', 'Granizo', 'Eléctrica']
                for cond in condiciones:
                    if cond in linea_temp:
                        if 'descripcion' not in datos_dia['condiciones']:
                            datos_dia['condiciones']['descripcion'] = cond
                        elif cond not in datos_dia['condiciones']['descripcion']:
                            datos_dia['condiciones']['descripcion'] += f", {cond}"
                
                # Fenómenos
                fenomenos = ['tormenta', 'eléctric', 'rayo', 'granizo', 'nevada', 'ventisca', 'helada']
                for fen in fenomenos:
                    if fen in linea_temp.lower():
                        datos_dia['fenomenos'].append(fen.capitalize())
    
    return datos_dia

def extraer_parametros_generales(texto):
    """Extrae parámetros generales"""
    parametros = {}
    
    hum_match = re.search(r'Humedad\s*:?\s*(\d+)\s*%', texto, re.IGNORECASE)
    if hum_match:
        parametros['humedad'] = f"{hum_match.group(1)}%"
    
    vis_match = re.search(r'Visibilidad\s*:?\s*(\d+)\s*km', texto, re.IGNORECASE)
    if vis_match:
        parametros['visibilidad'] = f"{vis_match.group(1)} km"
    
    return parametros

# ============================================================================
# SMN - EXTRACCIÓN COMPLETA DE CHAPELCO (SIMPLIFICADA)
# ============================================================================

def obtener_datos_smn_completos():
    """Extrae TODOS los datos disponibles de Chapelco del SMN"""
    url = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=pron5d"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/zip, */*',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=40, verify=False)
        
        if response.status_code != 200:
            return {}, False, f"❌ Error HTTP {response.status_code}"
        
        try:
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                txt_files = [f for f in zip_file.namelist() if f.endswith('.txt')]
                
                if not txt_files:
                    return {}, False, "❌ No hay archivos TXT"
                
                contenido_completo = ""
                for txt_file in txt_files[:2]:
                    with zip_file.open(txt_file) as f:
                        contenido_completo += f.read().decode('utf-8', errors='ignore') + "\n---\n"
                
                # Extraer datos de Chapelco
                datos_chapelco = extraer_todo_chapelco(contenido_completo)
                datos_chapelco['contenido_crudo'] = contenido_completo[:5000]
                
                return datos_chapelco, True, f"✅ SMN: {len(datos_chapelco.get('dias', []))} días"
                
        except zipfile.BadZipFile:
            contenido = response.content.decode('utf-8', errors='ignore')
            datos_chapelco = extraer_todo_chapelco(contenido)
            datos_chapelco['contenido_crudo'] = contenido[:5000]
            return datos_chapelco, True, f"✅ SMN (texto): {len(datos_chapelco.get('dias', []))} días"
    
    except Exception as e:
        return {}, False, f"❌ Error SMN: {str(e)}"

def extraer_todo_chapelco(contenido):
    """Extrae TODA la información de Chapelco"""
    datos = {
        'dias': [],
        'estacion_info': {},
        'raw_lines': []
    }
    
    contenido_upper = contenido.upper()
    idx_chapelco = 0
    
    while True:
        idx_chapelco = contenido_upper.find('CHAPELCO', idx_chapelco)
        if idx_chapelco == -1:
            break
        
        inicio = max(0, idx_chapelco - 300)
        fin = min(len(contenido), idx_chapelco + 700)
        contexto = contenido[inicio:fin]
        
        datos['raw_lines'].append({
            'posicion': idx_chapelco,
            'contexto': contexto[:300]
        })
        
        parsear_seccion_chapelco(contexto, datos)
        idx_chapelco += 8
    
    if datos['dias']:
        datos['dias'].sort(key=lambda x: x.get('fecha_dt', datetime.min))
    
    return datos

def parsear_seccion_chapelco(seccion, datos):
    """Parsear una sección con datos de Chapelco"""
    lineas = seccion.split('\n')
    
    for linea in lineas:
        linea = linea.strip()
        if not linea:
            continue
        
        # Información de estación
        if 'ESTACIÓN' in linea.upper() or 'STATION' in linea.upper():
            datos['estacion_info']['nombre'] = 'Chapelco Aero'
            cod_match = re.search(r'[A-Z]{4}', linea)
            if cod_match:
                datos['estacion_info']['codigo'] = cod_match.group()
        
        # Fechas
        patrones_fecha = [
            r'(\d{2})/([A-Z]{3})/(\d{4})',
            r'(\d{2})-([A-Z]{3})-(\d{4})',
            r'(\d{2})\s+([A-Z]{3})\s+(\d{4})',
        ]
        
        for patron in patrones_fecha:
            fecha_match = re.search(patron, linea, re.IGNORECASE)
            if fecha_match:
                try:
                    dia = fecha_match.group(1)
                    mes_str = fecha_match.group(2).upper()
                    año = fecha_match.group(3)
                    
                    meses = {
                        'ENE': '01', 'FEB': '02', 'MAR': '03', 'ABR': '04',
                        'MAY': '05', 'JUN': '06', 'JUL': '07', 'AGO': '08',
                        'SEP': '09', 'OCT': '10', 'NOV': '11', 'DIC': '12',
                    }
                    
                    if mes_str in meses:
                        mes_num = meses[mes_str]
                        fecha_str = f"{dia}-{mes_num}-{año}"
                        fecha_dt = datetime.strptime(fecha_str, '%d-%m-%Y').date()
                        
                        numeros = re.findall(r'-?\d+\.?\d*', linea)
                        
                        dia_data = {
                            'fecha': fecha_str,
                            'fecha_dt': fecha_dt,
                            'linea_original': linea,
                            'numeros': numeros
                        }
                        
                        if len(numeros) >= 1:
                            dia_data['temperatura'] = float(numeros[0])
                        if len(numeros) >= 2:
                            dia_data['temperatura2'] = float(numeros[1])
                        
                        viento_match = re.search(r'(\d+)\s*km/h', linea)
                        if viento_match:
                            dia_data['viento_kmh'] = int(viento_match.group(1))
                        
                        datos['dias'].append(dia_data)
                        
                except Exception:
                    continue

# ============================================================================
# OPEN-METEO - VERSIÓN CORREGIDA (SIN ERROR 400)
# ============================================================================

def obtener_datos_openmeteo_completos(fecha_base, modelo="best_match", dias_pronostico=5):
    """
    Obtiene datos COMPLETOS de Open-Meteo con parámetros REALES que funcionan
    
    Parámetros CORRECTOS (sin error 400):
    - Modelos: gfs, icon, gfs_seamless, icon_seamless, best_match
    - Datos horarios: temperatura, humedad, precipitación, viento, CAPE
    - Datos diarios: resumen con máximos/mínimos
    """
    
    start_date = fecha_base.strftime("%Y-%m-%d")
    end_date = (fecha_base + timedelta(days=dias_pronostico-1)).strftime("%Y-%m-%d")
    
    # ============================================================
    # PARÁMETROS HOURLES (funcionan en Open-Meteo v1)
    # ============================================================
    hourly_params = [
        "temperature_2m",              # Temperatura actual (°C)
        "relativehumidity_2m",         # Humedad relativa (%)
        "dewpoint_2m",                 # Punto de rocío (°C)
        "apparent_temperature",        # Sensación térmica (°C)
        "precipitation",               # Precipitación total (mm)
        "rain",                        # Lluvia (mm)
        "showers",                     # Chubascos convectivos (mm) -> TORMENTAS
        "snowfall",                    # Nieve (cm)
        "weathercode",                 # Código WMO (tipo de precipitación)
        "cloudcover",                  # Nubosidad total (%)
        "cloudcover_low",              # Nubes bajas (%)
        "cloudcover_mid",              # Nubes medias (%)
        "cloudcover_high",             # Nubes altas (%)
        "windspeed_10m",               # Velocidad del viento (km/h)
        "winddirection_10m",           # Dirección del viento (°)
        "windgusts_10m",               # Ráfagas de viento (km/h)
        "pressure_msl",                # Presión a nivel del mar (hPa)
        "cape",                        # CAPE - Energía convectiva (J/kg) -> TORMENTAS
        "freezinglevel_height",        # Altura del nivel de congelación (m)
        "soil_temperature_0cm",        # Temperatura del suelo a 0cm (°C)
        "precipitation_probability",   # Probabilidad de precipitación (%)
        "visibility",                  # Visibilidad (m)
        "evapotranspiration",          # Evapotranspiration (mm)
        "vapor_pressure_deficit"       # Déficit de presión de vapor (kPa)
    ]
    
    # ============================================================
    # PARÁMETROS DIARIOS (funcionan en Open-Meteo v1)
    # ============================================================
    daily_params = [
        "weathercode",                  # Código WMO del día
        "temperature_2m_max",           # Temperatura máxima (°C)
        "temperature_2m_min",           # Temperatura mínima (°C)
        "apparent_temperature_max",     # Sensación térmica máxima (°C)
        "apparent_temperature_min",     # Sensación térmica mínima (°C)
        "sunrise",                      # Amanecer
        "sunset",                       # Atardecer
        "precipitation_sum",            # Precipitación total del día (mm)
        "rain_sum",                     # Lluvia total (mm)
        "showers_sum",                  # Chubascos totales (mm) -> convectivo
        "snowfall_sum",                 # Nieve total (cm)
        "precipitation_hours",          # Horas con precipitación
        "windspeed_10m_max",            # Velocidad máxima del viento (km/h)
        "windgusts_10m_max",            # Ráfaga máxima (km/h)
        "winddirection_10m_dominant",   # Dirección predominante del viento (°)
        "shortwave_radiation_sum",      # Radiación solar (MJ/m²)
        "uv_index_max",                 # Índice UV máximo
        "uv_index_clear_sky_max",       # Índice UV máximo con cielo despejado
        "cape_max"                      # CAPE máximo del día (J/kg) -> TORMENTAS
    ]
    
    # Unir parámetros
    hourly_str = ",".join(hourly_params)
    daily_str = ",".join(daily_params)
    
    try:
        # Construir URL CORRECTA (sin parámetros inválidos)
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude=-40.1579&longitude=-71.3534&"
            f"hourly={hourly_str}&"
            f"daily={daily_str}&"
            f"timezone=America%2FArgentina%2FBuenos_Aires&"
            f"start_date={start_date}&end_date={end_date}&"
            f"forecast_days={dias_pronostico}&"
            f"models={modelo}"
        )
        
        st.write(f"🔗 URL Open-Meteo: `{url[:100]}...`")
        
        response = requests.get(url, timeout=25)
        
        st.write(f"📡 Status Open-Meteo: {response.status_code}")
        
        if response.status_code != 200:
            st.error(f"❌ Error {response.status_code}: {response.text[:200]}")
            return {}, False, f"❌ Error API: {response.status_code}"
        
        datos_raw = response.json()
        
        if 'hourly' not in datos_raw or 'daily' not in datos_raw:
            st.warning("⚠️ No hay datos horarios o diarios en la respuesta")
            return {}, False, "❌ Estructura de datos incompleta"
        
        # Procesar datos
        datos_procesados = procesar_datos_openmeteo(
            datos_raw['hourly'], 
            datos_raw['daily'],
            fecha_base
        )
        
        return datos_procesados, True, f"✅ Open-Meteo: {len(datos_procesados.get('dias', []))} días con datos horarios"
    
    except requests.exceptions.Timeout:
        st.error("⏱️ Timeout al conectar con Open-Meteo")
        return {}, False, "❌ Timeout en la conexión"
    except requests.exceptions.ConnectionError:
        st.error("🔌 Error de conexión con Open-Meteo")
        return {}, False, "❌ Error de conexión"
    except Exception as e:
        st.error(f"❌ Error Open-Meteo: {str(e)}")
        return {}, False, f"❌ Error: {str(e)}"

def procesar_datos_openmeteo(datos_horarios, datos_diarios, fecha_base):
    """Procesa y estructura los datos de Open-Meteo"""
    
    resultado = {
        'modelo': datos_diarios.get('generationtime_ms', 0),
        'unidades': {},
        'dias': [],
        'pronostico_horario': [],
        'fenomenos_detectados': [],
        'alertas': []
    }
    
    # Extraer unidades
    if 'hourly_units' in datos_horarios:
        resultado['unidades']['hourly'] = datos_horarios['hourly_units']
    if 'daily_units' in datos_diarios:
        resultado['unidades']['daily'] = datos_diarios['daily_units']
    
    # ============================================================
    # PROCESAR DATOS DIARIOS
    # ============================================================
    if 'time' in datos_diarios:
        for i in range(len(datos_diarios['time'])):
            try:
                fecha_str = datos_diarios['time'][i]
                fecha_dt = datetime.strptime(fecha_str, '%Y-%m-%d').date()
                
                # Saltar fechas anteriores
                if fecha_dt < fecha_base:
                    continue
                
                dia_data = {
                    'fecha': fecha_dt.strftime('%d-%m-%Y'),
                    'fecha_dt': fecha_dt,
                    'datos_diarios': {},
                    'datos_horarios': []
                }
                
                # Extraer todos los parámetros diarios disponibles
                for param in datos_diarios.keys():
                    if param != 'time' and i < len(datos_diarios.get(param, [])):
                        valor = datos_diarios[param][i]
                        if valor is not None:
                            dia_data['datos_diarios'][param] = valor
                
                # Detectar fenómenos diarios
                detectar_fenomenos_diarios(dia_data, resultado['fenomenos_detectados'], resultado['alertas'])
                
                resultado['dias'].append(dia_data)
                
                # Limitar a días de pronóstico
                if len(resultado['dias']) >= 7:
                    break
                    
            except Exception as e:
                continue
    
    # ============================================================
    # PROCESAR DATOS HORARIOS (primeras 72 horas)
    # ============================================================
    if 'time' in datos_horarios:
        for i in range(min(72, len(datos_horarios['time']))):  # Máximo 72 horas
            try:
                fecha_hora_str = datos_horarios['time'][i]
                fecha_hora_dt = datetime.strptime(fecha_hora_str, '%Y-%m-%dT%H:%M')
                
                hora_data = {
                    'fecha_hora': fecha_hora_str,
                    'fecha_hora_dt': fecha_hora_dt,
                    'hora': fecha_hora_dt.hour,
                    'datos': {}
                }
                
                # Extraer parámetros horarios
                for param in datos_horarios.keys():
                    if param not in ['time', 'hourly_units'] and i < len(datos_horarios.get(param, [])):
                        valor = datos_horarios[param][i]
                        if valor is not None:
                            hora_data['datos'][param] = valor
                
                # Detectar fenómenos horarios
                detectar_fenomenos_horarios(hora_data, resultado['alertas'])
                
                resultado['pronostico_horario'].append(hora_data)
                
            except Exception:
                continue
    
    # Agrupar datos horarios por día
    agrupar_horarios_por_dia(resultado)
    
    return resultado

def detectar_fenomenos_diarios(dia_data, fenomenos_list, alertas_list):
    """Detecta fenómenos meteorológicos en datos diarios"""
    
    datos = dia_data['datos_diarios']
    fecha = dia_data['fecha']
    
    # 1. TORMENTAS ELÉCTRICAS (weathercode 95-99)
    if 'weathercode' in datos:
        wcode = datos['weathercode']
        if wcode in [95, 96, 99]:
            intensidad = "severa" if wcode == 99 else ("con granizo" if wcode == 96 else "moderada")
            fenomeno = {
                'fecha': fecha,
                'tipo': 'Tormenta eléctrica',
                'intensidad': intensidad,
                'codigo': wcode,
                'fuente': 'weathercode'
            }
            if fenomeno not in fenomenos_list:
                fenomenos_list.append(fenomeno)
                alertas_list.append(f"⚡ Tormenta eléctrica {intensidad} el {fecha}")
    
    # 2. POTENCIAL DE TORMENTAS (CAPE > 1000 J/kg)
    if 'cape_max' in datos and datos['cape_max'] > 1000:
        fenomeno = {
            'fecha': fecha,
            'tipo': 'Alto potencial convectivo',
            'cape': f"{datos['cape_max']:.0f} J/kg",
            'riesgo': 'Alto' if datos['cape_max'] > 2000 else 'Moderado'
        }
        if fenomeno not in fenomenos_list:
            fenomenos_list.append(fenomeno)
            alertas_list.append(f"🌩️ Alto potencial convectivo (CAPE: {datos['cape_max']:.0f} J/kg) el {fecha}")
    
    # 3. LLUVIA INTENSA (> 20 mm)
    if 'precipitation_sum' in datos and datos['precipitation_sum'] > 20:
        fenomeno = {
            'fecha': fecha,
            'tipo': 'Lluvia intensa',
            'cantidad': f"{datos['precipitation_sum']:.1f} mm",
            'intensidad': 'Muy intensa' if datos['precipitation_sum'] > 50 else 'Intensa'
        }
        if fenomeno not in fenomenos_list:
            fenomenos_list.append(fenomeno)
            alertas_list.append(f"🌧️ Lluvia intensa ({datos['precipitation_sum']:.1f} mm) el {fecha}")
    
    # 4. NIEVE (> 5 cm)
    if 'snowfall_sum' in datos and datos['snowfall_sum'] > 5:
        fenomeno = {
            'fecha': fecha,
            'tipo': 'Nieve',
            'acumulado': f"{datos['snowfall_sum']:.1f} cm",
            'intensidad': 'Fuerte' if datos['snowfall_sum'] > 15 else 'Moderada'
        }
        if fenomeno not in fenomenos_list:
            fenomenos_list.append(fenomeno)
            alertas_list.append(f"❄️ Nieve ({datos['snowfall_sum']:.1f} cm) el {fecha}")
    
    # 5. VIENTOS FUERTES (> 40 km/h)
    if 'windgusts_10m_max' in datos and datos['windgusts_10m_max'] > 40:
        fenomeno = {
            'fecha': fecha,
            'tipo': 'Vientos fuertes',
            'velocidad': f"{datos['windgusts_10m_max']:.1f} km/h",
            'intensidad': 'Muy fuertes' if datos['windgusts_10m_max'] > 60 else 'Fuertes'
        }
        if fenomeno not in fenomenos_list:
            fenomenos_list.append(fenomeno)
            alertas_list.append(f"💨 Vientos fuertes ({datos['windgusts_10m_max']:.1f} km/h) el {fecha}")

def detectar_fenomenos_horarios(hora_data, alertas_list):
    """Detecta fenómenos en datos horarios"""
    datos = hora_data['datos']
    fecha_hora = hora_data['fecha_hora']
    
    # Tormentas horarias (CAPE alto + showers)
    if 'cape' in datos and 'showers' in datos:
        if datos['cape'] > 1500 and datos['showers'] > 0:
            alerta = f"⛈️ Posible tormenta convectiva a las {hora_data['hora']}:00 (CAPE: {datos['cape']:.0f} J/kg)"
            if alerta not in alertas_list:
                alertas_list.append(alerta)
    
    # Congelamiento (temp < 0)
    if 'temperature_2m' in datos and datos['temperature_2m'] < 0:
        alerta = f"🧊 Temperatura bajo cero a las {hora_data['hora']}:00 ({datos['temperature_2m']:.1f}°C)"
        if alerta not in alertas_list:
            alertas_list.append(alerta)

def agrupar_horarios_por_dia(resultado):
    """Agrupa datos horarios por día para cada día en resultado['dias']"""
    
    for dia in resultado['dias']:
        fecha_dia = dia['fecha_dt']
        dia['horas'] = []
        
        for hora_data in resultado['pronostico_horario']:
            if hora_data['fecha_hora_dt'].date() == fecha_dia:
                # Seleccionar solo datos importantes para mostrar
                datos_resumen = {}
                
                if 'temperature_2m' in hora_data['datos']:
                    datos_resumen['temp'] = f"{hora_data['datos']['temperature_2m']:.1f}°C"
                
                if 'precipitation' in hora_data['datos'] and hora_data['datos']['precipitation'] > 0:
                    datos_resumen['precip'] = f"{hora_data['datos']['precipitation']:.1f}mm"
                
                if 'weathercode' in hora_data['datos']:
                    datos_resumen['weathercode'] = hora_data['datos']['weathercode']
                
                if 'windspeed_10m' in hora_data['datos']:
                    datos_resumen['viento'] = f"{hora_data['datos']['windspeed_10m']:.1f}km/h"
                
                if 'cloudcover' in hora_data['datos']:
                    datos_resumen['nubosidad'] = f"{hora_data['datos']['cloudcover']:.0f}%"
                
                dia['horas'].append({
                    'hora': hora_data['hora'],
                    'datos_resumen': datos_resumen,
                    'datos_completos': hora_data['datos']
                })

# ============================================================================
# INTERFAZ PRINCIPAL
# ============================================================================

def main():
    if st.button("🚀 EXTRAER TODOS LOS DATOS", type="primary", use_container_width=True):
        
        with st.spinner("🔍 Iniciando extracción completa..."):
            
            # Contenedores de estado
            col1, col2, col3 = st.columns(3)
            
            with col1:
                status_aic = st.empty()
                status_aic.info("⏳ AIC...")
            
            with col2:
                status_smn = st.empty()
                status_smn.info("⏳ SMN...")
            
            with col3:
                status_om = st.empty()
                status_om.info("⏳ Open-Meteo...")
            
            # 1. AIC
            status_aic.warning("📄 Extrayendo AIC...")
            datos_aic, estado_aic, mensaje_aic = obtener_datos_aic_completos(fecha_base)
            
            # 2. SMN
            status_smn.warning("📊 Extrayendo SMN...")
            datos_smn, estado_smn, mensaje_smn = obtener_datos_smn_completos()
            
            # 3. OPEN-METEO (CORREGIDO)
            status_om.warning(f"🛰️ Open-Meteo ({modelo_seleccionado})...")
            datos_om, estado_om, mensaje_om = obtener_datos_openmeteo_completos(
                fecha_base, 
                modelo_seleccionado, 
                dias_pronostico
            )
            
            # Actualizar estados
            if estado_aic:
                status_aic.success(f"✅ {mensaje_aic}")
            else:
                status_aic.error(f"❌ {mensaje_aic}")
            
            if estado_smn:
                status_smn.success(f"✅ {mensaje_smn}")
            else:
                status_smn.error(f"❌ {mensaje_smn}")
            
            if estado_om:
                status_om.success(f"✅ {mensaje_om}")
            else:
                status_om.error(f"❌ {mensaje_om}")
            
            st.markdown("---")
            st.subheader("📦 DATOS EXTRAÍDOS - LISTOS PARA IA")
            
            # Mostrar resumen
            mostrar_resumen_completo(datos_aic, datos_smn, datos_om, 
                                   estado_aic, estado_smn, estado_om)
            
            # Preparar datos para IA
            datos_para_ia = {
                'timestamp': datetime.now().isoformat(),
                'fecha_base': fecha_base.isoformat(),
                'fuentes': {
                    'AIC': {'estado': estado_aic, 'datos': datos_aic, 'mensaje': mensaje_aic},
                    'SMN': {'estado': estado_smn, 'datos': datos_smn, 'mensaje': mensaje_smn},
                    'OPEN_METEO': {
                        'estado': estado_om,
                        'datos': datos_om,
                        'mensaje': mensaje_om,
                        'modelo': modelo_seleccionado,
                        'dias_pronostico': dias_pronostico
                    }
                }
            }
            
            # Mostrar estructura de datos
            with st.expander("🧠 ESTRUCTURA DE DATOS PARA IA", expanded=True):
                st.json(datos_para_ia, expanded=False)
            
            # Botón para descargar
            datos_json = json.dumps(datos_para_ia, default=str, indent=2)
            st.download_button(
                label="📥 DESCARGAR DATOS BRUTOS (JSON)",
                data=datos_json,
                file_name=f"datos_meteo_{fecha_base.strftime('%Y%m%d')}.json",
                mime="application/json"
            )
            
            # Mostrar detalles por fuente
            st.markdown("---")
            st.subheader("🔍 DETALLES POR FUENTE")
            
            tabs = st.tabs(["📄 AIC", "📊 SMN", f"🛰️ OPEN-METEO ({modelo_seleccionado})"])
            
            with tabs[0]:
                if estado_aic and datos_aic:
                    mostrar_detalles_aic(datos_aic)
                else:
                    st.error("No hay datos de AIC")
            
            with tabs[1]:
                if estado_smn and datos_smn:
                    mostrar_detalles_smn(datos_smn)
                else:
                    st.error("No hay datos de SMN")
            
            with tabs[2]:
                if estado_om and datos_om:
                    mostrar_detalles_openmeteo(datos_om)
                else:
                    st.error("No hay datos de Open-Meteo")
            
            # Resumen final
            st.markdown("---")
            st.subheader("🎯 RESUMEN PARA PROCESAMIENTO DE IA")
            
            fuentes_activas = sum([estado_aic, estado_smn, estado_om])
            
            st.info(f"""
            **{fuentes_activas}/3 fuentes activas**
            
            **Datos disponibles para fusión 40/60:**
            
            📄 **AIC (Oficial Argentina):**
            - {len(datos_aic.get('dias', []))} días con pronóstico detallado
            - {len(datos_aic.get('fenomenos_especiales', []))} fenómenos especiales detectados
            
            📊 **SMN Chapelco (Oficial):**
            - {len(datos_smn.get('dias', []))} días de datos de estación
            - {len(datos_smn.get('raw_lines', []))} referencias a Chapelco
            
            🛰️ **Open-Meteo ({modelo_seleccionado.upper()}):**
            - {len(datos_om.get('dias', []))} días con pronóstico
            - {len(datos_om.get('pronostico_horario', []))} horas de datos horarios
            - {len(datos_om.get('fenomenos_detectados', []))} fenómenos extremos detectados
            - Parámetros: Temperatura, humedad, precipitación, viento, CAPE, nubosidad
            
            **Estrategia de ponderación:**
            - 40%: Fuentes locales (AIC + SMN) - fenómenos específicos
            - 60%: Modelos globales (Open-Meteo) - tendencia térmica y convectiva
            """)

def mostrar_resumen_completo(datos_aic, datos_smn, datos_om, estado_aic, estado_smn, estado_om):
    """Muestra resumen visual"""
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown('<div class="source-card source-aic">', unsafe_allow_html=True)
        st.subheader("📄 AIC")
        if estado_aic:
            st.success("✅ ACTIVO")
            dias = len(datos_aic.get('dias', []))
            st.write(f"**{dias} días** pronosticados")
            if datos_aic.get('fenomenos_especiales'):
                st.write(f"**{len(datos_aic['fenomenos_especiales'])} alertas**")
        else:
            st.error("❌ INACTIVO")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="source-card source-smn">', unsafe_allow_html=True)
        st.subheader("📊 SMN")
        if estado_smn:
            st.success("✅ ACTIVO")
            dias = len(datos_smn.get('dias', []))
            st.write(f"**{dias} días** de Chapelco")
            if datos_smn.get('estacion_info'):
                st.write("**Datos de estación**")
        else:
            st.error("❌ INACTIVO")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="source-card source-sat">', unsafe_allow_html=True)
        st.subheader(f"🛰️ {modelo_seleccionado.upper()}")
        if estado_om:
            st.success("✅ ACTIVO")
            dias = len(datos_om.get('dias', []))
            horas = len(datos_om.get('pronostico_horario', []))
            st.write(f"**{dias} días** pronosticados")
            st.write(f"**{horas} horas** de datos")
            if datos_om.get('fenomenos_detectados'):
                st.write(f"**{len(datos_om['fenomenos_detectados'])} fenómenos**")
        else:
            st.error("❌ INACTIVO")
        st.markdown('</div>', unsafe_allow_html=True)

def mostrar_detalles_aic(datos):
    """Muestra detalles de AIC"""
    
    if 'dias' in datos and datos['dias']:
        st.write(f"### 📅 {len(datos['dias'])} Días Pronosticados")
        
        for dia in datos['dias'][:5]:
            with st.expander(f"**{dia['fecha']}**"):
                col1, col2 = st.columns(2)
                
                with col1:
                    if 'temperaturas' in dia:
                        st.write("**Temperaturas:**")
                        if 'max' in dia['temperaturas']:
                            st.write(f"Máx: {dia['temperaturas']['max']}°C")
                        if 'min' in dia['temperaturas']:
                            st.write(f"Mín: {dia['temperaturas']['min']}°C")
                    
                    if 'vientos' in dia:
                        st.write("**Vientos:**")
                        if 'velocidad' in dia['vientos']:
                            st.write(f"Velocidad: {dia['vientos']['velocidad']} km/h")
                        if 'direccion' in dia['vientos']:
                            st.write(f"Dirección: {dia['vientos']['direccion']}")
                
                with col2:
                    if 'condiciones' in dia:
                        st.write("**Condiciones:**")
                        if 'descripcion' in dia['condiciones']:
                            st.write(dia['condiciones']['descripcion'])
                    
                    if dia.get('fenomenos'):
                        st.write("**Fenómenos:**")
                        for fen in dia['fenomenos']:
                            st.write(f"- {fen}")
        
        if datos.get('fenomenos_especiales'):
            st.write("### ⚡ Fenómenos Especiales")
            for fen in datos['fenomenos_especiales']:
                st.markdown(f'<div class="phenomenon-alert">{fen}</div>', unsafe_allow_html=True)

def mostrar_detalles_smn(datos):
    """Muestra detalles de SMN"""
    
    if 'estacion_info' in datos and datos['estacion_info']:
        st.write("### 🏔️ Información de Estación")
        for key, value in datos['estacion_info'].items():
            st.write(f"**{key.title()}:** {value}")
    
    if 'dias' in datos and datos['dias']:
        st.write(f"### 📊 {len(datos['dias'])} Días de Datos")
        
        for dia in datos['dias'][:5]:
            with st.expander(f"**{dia['fecha']}**"):
                st.write("**Línea original:**")
                st.code(dia.get('linea_original', 'No disponible'))
                
                if 'temperatura' in dia:
                    st.write(f"**Temperatura:** {dia['temperatura']}°C")
                if 'viento_kmh' in dia:
                    st.write(f"**Viento:** {dia['viento_kmh']} km/h")
                
                if 'numeros' in dia:
                    st.write(f"**Datos numéricos encontrados:** {len(dia['numeros'])}")
                    st.write(", ".join(dia['numeros']))

def mostrar_detalles_openmeteo(datos):
    """Muestra detalles de Open-Meteo"""
    
    # Fenómenos detectados
    if datos.get('fenomenos_detectados'):
        st.write("### ⚡ Fenómenos Detectados")
        for fen in datos['fenomenos_detectados']:
            st.markdown(f"""
            <div class="phenomenon-alert">
            <strong>{fen['tipo']}</strong> - {fen['fecha']}<br>
            {fen.get('intensidad', '')} {fen.get('cantidad', fen.get('velocidad', fen.get('cape', '')))}
            </div>
            """, unsafe_allow_html=True)
    
    # Días pronosticados
    if datos.get('dias'):
        st.write(f"### 🌤️ {len(datos['dias'])} Días Pronosticados")
        
        for dia in datos['dias'][:3]:
            with st.expander(f"**{dia['fecha']}** - Pronóstico detallado"):
                
                # Datos diarios
                if dia['datos_diarios']:
                    st.write("**Resumen diario:**")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if 'temperature_2m_max' in dia['datos_diarios']:
                            st.write(f"🌡️ **Máx:** {dia['datos_diarios']['temperature_2m_max']:.1f}°C")
                        if 'temperature_2m_min' in dia['datos_diarios']:
                            st.write(f"🌡️ **Mín:** {dia['datos_diarios']['temperature_2m_min']:.1f}°C")
                        if 'precipitation_sum' in dia['datos_diarios'] and dia['datos_diarios']['precipitation_sum'] > 0:
                            st.write(f"🌧️ **Precip:** {dia['datos_diarios']['precipitation_sum']:.1f} mm")
                    
                    with col2:
                        if 'windspeed_10m_max' in dia['datos_diarios']:
                            st.write(f"💨 **Viento máx:** {dia['datos_diarios']['windspeed_10m_max']:.1f} km/h")
                        if 'windgusts_10m_max' in dia['datos_diarios']:
                            st.write(f"💨 **Ráfagas:** {dia['datos_diarios']['windgusts_10m_max']:.1f} km/h")
                        if 'cape_max' in dia['datos_diarios'] and dia['datos_diarios']['cape_max'] > 0:
                            st.write(f"⚡ **CAPE:** {dia['datos_diarios']['cape_max']:.0f} J/kg")
                
                # Datos horarios (si existen)
                if 'horas' in dia and dia['horas']:
                    st.write("---")
                    st.write("**Pronóstico horario (selección):**")
                    
                    # Mostrar cada 3 horas
                    horas_filtradas = [h for h in dia['horas'] if h['hora'] % 3 == 0]
                    
                    for hora in horas_filtradas[:8]:
                        st.markdown(f"""
                        <div class="hourly-forecast">
                        <strong>{hora['hora']}:00</strong> | 
                        Temp: {hora['datos_resumen'].get('temp', 'N/D')} | 
                        Precip: {hora['datos_resumen'].get('precip', '0mm')} |
                        Viento: {hora['datos_resumen'].get('viento', 'N/D')} |
                        Nubes: {hora['datos_resumen'].get('nubosidad', 'N/D')}
                        </div>
                        """, unsafe_allow_html=True)
    
    # Alertas
    if datos.get('alertas'):
        st.write("### 🔔 Alertas y Advertencias")
        for alerta in datos['alertas'][:5]:
            st.warning(alerta)

# Ejecutar aplicación
if __name__ == "__main__":
    main()

# Footer
st.markdown("---")
st.caption("""
**Sistema de Extracción Meteorológica V4.3** | 
Open-Meteo corregido (sin error 400) | 
Parámetros reales: temperatura, humedad, precipitación, viento, CAPE, nubosidad |
Listo para IA con fusión 40/60
""")
