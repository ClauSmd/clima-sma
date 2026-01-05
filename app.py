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
</style>
""", unsafe_allow_html=True)

# Título principal
st.title("⛈️ Sistema de Fusión Meteorológica - San Martín de los Andes")
st.markdown("**Extracción completa de todas las fuentes - IA procesará datos brutos**")
st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuración")
    fecha_base = st.date_input("Fecha de inicio", datetime.now().date())
    
    st.markdown("---")
    st.header("🎯 Parámetros Satelitales")
    
    st.subheader("Fenómenos Extremos")
    incluir_tormentas = st.checkbox("Tormentas eléctricas", value=True)
    incluir_granizo = st.checkbox("Granizo", value=True)
    incluir_nieve = st.checkbox("Nieve intensa", value=True)
    incluir_vientos = st.checkbox("Vientos fuertes", value=True)
    
    st.markdown("---")
    st.info("""
    **Modo: Extracción Bruta**
    
    - AIC: Todo el PDF
    - SMN: Todo Chapelco del TXT  
    - Satélite: Parámetros absolutos
    - IA hará fusión 40/60
    """)

# ============================================================================
# FUNCIONES DE EXTRACCIÓN COMPLETA
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
                    # Extraer texto de todas las páginas
                    texto_completo = ""
                    for pagina in pdf.pages:
                        texto_completo += pagina.extract_text() + "\n"
                    
                    if texto_completo and len(texto_completo.strip()) > 200:
                        # Parsear TODOS los datos disponibles
                        datos_completos = parsear_aic_completo(texto_completo, fecha_base)
                        
                        # También guardar el texto crudo para la IA
                        datos_completos['texto_crudo'] = texto_completo[:5000]  # Primeros 5000 chars
                        
                        return datos_completos, True, f"✅ AIC: {len(datos_completos.get('dias', []))} días + texto completo"
            
            time.sleep(1.5)
        except Exception as e:
            continue
    
    return {}, False, "❌ No se pudo obtener el PDF de AIC"

def parsear_aic_completo(texto, fecha_base):
    """Parsea COMPLETAMENTE el PDF de AIC - extrae todo lo disponible"""
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
            # Buscar título o encabezado
            if 'PRONÓSTICO' in linea.upper() and i < 3:
                datos['titulo'] = linea
            
            # Buscar período de validez
            if 'VÁLIDO' in linea.upper() or 'PERÍODO' in linea.upper():
                datos['periodo_validez'] = linea
            
            # Buscar fenómenos especiales
            if any(fen in linea.upper() for fen in ['TORMENTA', 'ELECTRIC', 'GRANIZO', 'NIEVE', 'VIENTO FUERTE', 'ALERTA']):
                if linea not in datos['fenomenos_especiales']:
                    datos['fenomenos_especiales'].append(linea)
            
            # Buscar advertencias
            if any(adv in linea.upper() for adv in ['ADVERTENCIA', 'PRECAUCIÓN', 'ATENCIÓN']):
                if linea not in datos['advertencias']:
                    datos['advertencias'].append(linea)
        
        # Buscar fechas - múltiples patrones
        fechas_encontradas = []
        for linea in lineas[:15]:  # Buscar en primeras líneas
            # Patrones de fecha: DD-MM-YYYY, DD/MM/YYYY, DD MM YYYY
            patrones = [
                r'\d{2}-\d{2}-\d{4}',
                r'\d{2}/\d{2}/\d{4}',
                r'\d{2}\s+\d{2}\s+\d{4}'
            ]
            
            for patron in patrones:
                matches = re.findall(patron, linea)
                if matches:
                    fechas_encontradas.extend(matches)
                    break
        
        # Procesar cada fecha encontrada
        for fecha_str in fechas_encontradas[:5]:  # Máximo 5 fechas
            try:
                # Normalizar formato de fecha
                if '-' in fecha_str:
                    fecha_dt = datetime.strptime(fecha_str, '%d-%m-%Y')
                elif '/' in fecha_str:
                    fecha_dt = datetime.strptime(fecha_str, '%d/%m/%Y')
                else:
                    continue
                
                fecha_formateada = fecha_dt.strftime('%d-%m-%Y')
                
                # Buscar datos para esta fecha en todo el texto
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
    
    # Buscar líneas relacionadas con esta fecha
    lineas = texto.split('\n')
    fecha_encontrada = False
    
    for i, linea in enumerate(lineas):
        if fecha_str in linea:
            fecha_encontrada = True
            
            # Extraer período (Día/Noche)
            if 'Día' in linea or 'DIA' in linea.upper():
                datos_dia['periodos'].append('Día')
            if 'Noche' in linea or 'NOCHE' in linea.upper():
                datos_dia['periodos'].append('Noche')
            
            # Buscar temperaturas alrededor de esta línea
            for j in range(max(0, i-3), min(len(lineas), i+4)):
                linea_temp = lineas[j]
                
                # Temperaturas en °C
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
                
                # Condiciones del cielo
                condiciones = ['Despejado', 'Nublado', 'Parcialmente', 'Mayormente', 'Cubierto', 
                              'Lluvia', 'Lluvioso', 'Tormenta', 'Nieve', 'Granizo', 'Eléctrica']
                for cond in condiciones:
                    if cond in linea_temp:
                        if 'descripcion' not in datos_dia['condiciones']:
                            datos_dia['condiciones']['descripcion'] = cond
                        elif cond not in datos_dia['condiciones']['descripcion']:
                            datos_dia['condiciones']['descripcion'] += f", {cond}"
                
                # Fenómenos especiales
                fenomenos = ['tormenta', 'eléctric', 'rayo', 'granizo', 'nevada', 'ventisca', 'helada']
                for fen in fenomenos:
                    if fen in linea_temp.lower():
                        datos_dia['fenomenos'].append(fen.capitalize())
    
    if not fecha_encontrada:
        return None
    
    return datos_dia

def extraer_parametros_generales(texto):
    """Extrae parámetros generales del pronóstico"""
    parametros = {}
    
    # Humedad
    hum_match = re.search(r'Humedad\s*:?\s*(\d+)\s*%', texto, re.IGNORECASE)
    if hum_match:
        parametros['humedad'] = f"{hum_match.group(1)}%"
    
    # Visibilidad
    vis_match = re.search(r'Visibilidad\s*:?\s*(\d+)\s*km', texto, re.IGNORECASE)
    if vis_match:
        parametros['visibilidad'] = f"{vis_match.group(1)} km"
    
    # Nubosidad
    nub_match = re.search(r'Nubosidad\s*:?\s*(\d+)\s*%', texto, re.IGNORECASE)
    if nub_match:
        parametros['nubosidad'] = f"{nub_match.group(1)}%"
    
    # Punto de rocío
    rocio_match = re.search(r'Punto de rocío\s*:?\s*(-?\d+)\s*°C', texto, re.IGNORECASE)
    if rocio_match:
        parametros['punto_rocio'] = f"{rocio_match.group(1)}°C"
    
    return parametros

# ============================================================================
# SMN - EXTRACCIÓN COMPLETA DE CHAPELCO
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
        
        # Intentar como ZIP
        try:
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                txt_files = [f for f in zip_file.namelist() if f.endswith('.txt')]
                
                if not txt_files:
                    return {}, False, "❌ No hay archivos TXT"
                
                # Leer todos los archivos TXT
                contenido_completo = ""
                for txt_file in txt_files[:3]:  # Máximo 3 archivos
                    with zip_file.open(txt_file) as f:
                        contenido_completo += f.read().decode('utf-8', errors='ignore') + "\n---\n"
                
                # Extraer TODO lo de Chapelco
                datos_chapelco = extraer_todo_chapelco(contenido_completo)
                
                # Agregar contenido crudo
                datos_chapelco['contenido_crudo'] = contenido_completo[:8000]
                
                return datos_chapelco, True, f"✅ SMN: {len(datos_chapelco.get('dias', []))} días + datos completos"
                
        except zipfile.BadZipFile:
            # Intentar como texto directo
            contenido = response.content.decode('utf-8', errors='ignore')
            datos_chapelco = extraer_todo_chapelco(contenido)
            datos_chapelco['contenido_crudo'] = contenido[:8000]
            return datos_chapelco, True, f"✅ SMN (texto): {len(datos_chapelco.get('dias', []))} días"
    
    except Exception as e:
        return {}, False, f"❌ Error SMN: {str(e)}"

def extraer_todo_chapelco(contenido):
    """Extrae TODA la información de Chapelco del contenido"""
    datos = {
        'dias': [],
        'estacion_info': {},
        'parametros': {},
        'observaciones': [],
        'raw_lines': []
    }
    
    # Convertir a mayúsculas para búsqueda
    contenido_upper = contenido.upper()
    
    # Buscar todas las apariciones de CHAPELCO
    idx_chapelco = 0
    while True:
        idx_chapelco = contenido_upper.find('CHAPELCO', idx_chapelco)
        if idx_chapelco == -1:
            break
        
        # Extraer contexto (1000 caracteres antes y después)
        inicio = max(0, idx_chapelco - 500)
        fin = min(len(contenido), idx_chapelco + 1500)
        contexto = contenido[inicio:fin]
        
        # Guardar línea cruda
        datos['raw_lines'].append({
            'posicion': idx_chapelco,
            'contexto': contexto[:500]
        })
        
        # Parsear esta sección
        parsear_seccion_chapelco(contexto, datos)
        
        idx_chapelco += 8  # Avanzar más allá de "CHAPELCO"
    
    # Si no encontramos CHAPELCO, buscar por coordenadas o códigos
    if not datos['dias']:
        buscar_por_coordenadas(contenido, datos)
    
    # Ordenar días por fecha
    if datos['dias']:
        datos['dias'].sort(key=lambda x: x.get('fecha_dt', datetime.min))
    
    return datos

def parsear_seccion_chapelco(seccion, datos):
    """Parsear una sección que contiene datos de Chapelco"""
    lineas = seccion.split('\n')
    
    for linea in lineas:
        linea = linea.strip()
        if not linea:
            continue
        
        # Información de estación
        if 'ESTACIÓN' in linea.upper() or 'STATION' in linea.upper():
            datos['estacion_info']['nombre'] = 'Chapelco Aero'
            # Extraer código si existe
            cod_match = re.search(r'[A-Z]{4}', linea)
            if cod_match:
                datos['estacion_info']['codigo'] = cod_match.group()
        
        # Coordenadas
        coord_match = re.search(r'(\d+)[°º]\s*(\d+)\'?\s*[S|N].*?(\d+)[°º]\s*(\d+)\'?\s*[W|O]', linea, re.IGNORECASE)
        if coord_match:
            datos['estacion_info']['coordenadas'] = linea
        
        # Altura
        alt_match = re.search(r'(\d+)\s*m\s*(?:s\.n\.m|SNM|msnm)', linea, re.IGNORECASE)
        if alt_match:
            datos['estacion_info']['altura'] = f"{alt_match.group(1)} m"
        
        # Fechas y temperaturas - múltiples formatos
        patrones_fecha = [
            r'(\d{2})/([A-Z]{3})/(\d{4})',  # 01/ENE/2024
            r'(\d{2})-([A-Z]{3})-(\d{4})',  # 01-ENE-2024
            r'(\d{2})\s+([A-Z]{3})\s+(\d{4})',  # 01 ENE 2024
            r'(\d{2})/(\d{2})/(\d{4})',  # 01/01/2024
        ]
        
        for patron in patrones_fecha:
            fecha_match = re.search(patron, linea, re.IGNORECASE)
            if fecha_match:
                try:
                    dia = fecha_match.group(1)
                    mes_str = fecha_match.group(2).upper()
                    año = fecha_match.group(3)
                    
                    # Convertir mes abreviado a número
                    meses = {
                        'ENE': '01', 'FEB': '02', 'MAR': '03', 'ABR': '04',
                        'MAY': '05', 'JUN': '06', 'JUL': '07', 'AGO': '08',
                        'SEP': '09', 'OCT': '10', 'NOV': '11', 'DIC': '12',
                        'JAN': '01', 'FEB': '02', 'MAR': '03', 'APR': '04',
                        'MAY': '05', 'JUN': '06', 'JUL': '07', 'AUG': '08',
                        'SEP': '09', 'OCT': '10', 'NOV': '11', 'DEC': '12'
                    }
                    
                    if mes_str in meses:
                        mes_num = meses[mes_str]
                    else:
                        mes_num = mes_str.zfill(2)
                    
                    fecha_str = f"{dia}-{mes_num}-{año}"
                    fecha_dt = datetime.strptime(fecha_str, '%d-%m-%Y').date()
                    
                    # Extraer TODOS los números de la línea (temperaturas, viento, etc.)
                    numeros = re.findall(r'-?\d+\.?\d*', linea)
                    
                    # Crear entrada para este día
                    dia_data = {
                        'fecha': fecha_str,
                        'fecha_dt': fecha_dt,
                        'linea_original': linea,
                        'numeros': numeros
                    }
                    
                    # Interpretar números (primeros números suelen ser temperaturas)
                    if len(numeros) >= 1:
                        dia_data['temperatura'] = float(numeros[0])
                    
                    if len(numeros) >= 2:
                        dia_data['temperatura2'] = float(numeros[1])
                    
                    # Buscar viento específicamente
                    viento_match = re.search(r'(\d+)\s*km/h', linea)
                    if viento_match:
                        dia_data['viento_kmh'] = int(viento_match.group(1))
                    
                    # Buscar precipitación
                    precip_match = re.search(r'(\d+)\s*mm', linea, re.IGNORECASE)
                    if precip_match:
                        dia_data['precipitacion_mm'] = int(precip_match.group(1))
                    
                    # Buscar fenómenos
                    fenomenos = ['LLUVIA', 'NIEVE', 'GRANIZO', 'TORMENTA', 'VIENTO', 'NEBLINA']
                    for fen in fenomenos:
                        if fen in linea.upper():
                            if 'fenomenos' not in dia_data:
                                dia_data['fenomenos'] = []
                            dia_data['fenomenos'].append(fen.title())
                    
                    datos['dias'].append(dia_data)
                    
                except Exception:
                    continue
        
        # Observaciones generales
        if 'OBS' in linea.upper()[:4] or 'NOTA' in linea.upper() or 'OBSERVACIÓN' in linea.upper():
            if linea not in datos['observaciones']:
                datos['observaciones'].append(linea)

def buscar_por_coordenadas(contenido, datos):
    """Buscar datos por coordenadas de Chapelco si no se encuentra por nombre"""
    # Coordenadas aproximadas de Chapelco: 40°08'S 71°10'W
    coord_patrones = [
        r'40[°º]\s*\d+\'?\s*[S|N].*?71[°º]\s*\d+\'?\s*[W|O]',
        r'-40\.\d+.*-71\.\d+',  # Coordenadas decimales
    ]
    
    for patron in coord_patrones:
        coord_match = re.search(patron, contenido, re.IGNORECASE)
        if coord_match:
            # Extraer 300 caracteres alrededor de las coordenadas
            inicio = max(0, coord_match.start() - 150)
            fin = min(len(contenido), coord_match.end() + 150)
            contexto = contenido[inicio:fin]
            parsear_seccion_chapelco(contexto, datos)
            break

# ============================================================================
# SATÉLITE - PARÁMETROS ABSOLUTOS DE FENÓMENOS
# ============================================================================

def obtener_datos_satelital_completos(fecha_base, opciones):
    """Obtiene datos satelitales con parámetros absolutos de fenómenos"""
    start_date = fecha_base.strftime("%Y-%m-%d")
    end_date = (fecha_base + timedelta(days=4)).strftime("%Y-%m-%d")  # 5 días
    
    # Parámetros base
    parametros_base = [
        "temperature_2m_max", "temperature_2m_min",
        "apparent_temperature_max", "apparent_temperature_min",
        "windspeed_10m_max", "windgusts_10m_max",
        "winddirection_10m_dominant",
        "weathercode",  # Códigos WMO para fenómenos
        "precipitation_probability_max",
        "precipitation_sum", "rain_sum", "showers_sum", "snowfall_sum",
        "precipitation_hours",
        "uv_index_max", "uv_index_clear_sky_max"
    ]
    
    # Parámetros adicionales según selección
    if opciones.get('incluir_tormentas', True):
        parametros_base.extend(["cape", "lightning_potential"])
    
    if opciones.get('incluir_granizo', True):
        parametros_base.extend(["hail_potential"])
    
    if opciones.get('incluir_nieve', True):
        parametros_base.extend(["freezinglevel_height"])
    
    if opciones.get('incluir_vientos', True):
        parametros_base.extend(["wind_speed_100m_max"])
    
    # Unir parámetros
    parametros_str = ",".join(parametros_base)
    
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude=-40.1579&longitude=-71.3534&"
            f"daily={parametros_str}&"
            f"timezone=America%2FArgentina%2FBuenos_Aires&"
            f"start_date={start_date}&end_date={end_date}"
        )
        
        response = requests.get(url, timeout=20)
        
        if response.status_code != 200:
            return {}, False, f"❌ Error API: {response.status_code}"
        
        datos_raw = response.json()
        
        if 'daily' not in datos_raw:
            return {}, False, "❌ No hay datos diarios"
        
        # Procesar datos
        datos_procesados = procesar_datos_satelitales(datos_raw['daily'], fecha_base)
        
        return datos_procesados, True, f"✅ Satélite: {len(datos_procesados.get('dias', []))} días con fenómenos"
    
    except Exception as e:
        return {}, False, f"❌ Error Satélite: {str(e)}"

def procesar_datos_satelitales(datos_diarios, fecha_base):
    """Procesa y enriquece los datos satelitales"""
    resultado = {
        'dias': [],
        'fenomenos_extremos': [],
        'alertas': [],
        'parametros_disponibles': list(datos_diarios.keys())
    }
    
    # Procesar cada día
    for i in range(len(datos_diarios['time'])):
        try:
            fecha_str = datos_diarios['time'][i]
            fecha_dt = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            
            # Saltar fechas anteriores a la base
            if fecha_dt < fecha_base:
                continue
            
            dia_data = {
                'fecha': fecha_dt.strftime('%d-%m-%Y'),
                'fecha_dt': fecha_dt,
                'datos': {}
            }
            
            # Extraer todos los parámetros disponibles
            for param in datos_diarios.keys():
                if i < len(datos_diarios[param]):
                    valor = datos_diarios[param][i]
                    if valor is not None:
                        # Estandarizar unidades
                        if 'temperature' in param or 'apparent' in param:
                            dia_data['datos'][param] = f"{valor:.1f}°C"
                        elif 'wind' in param or 'gust' in param:
                            dia_data['datos'][param] = f"{valor:.1f} km/h"
                        elif 'precipitation' in param or 'rain' in param or 'snow' in param:
                            dia_data['datos'][param] = f"{valor:.1f} mm"
                        elif 'uv' in param:
                            dia_data['datos'][param] = f"{valor:.1f}"
                        elif param == 'weathercode':
                            dia_data['datos'][param] = int(valor)
                            # Interpretar código WMO
                            dia_data['datos']['weathercode_desc'] = interpretar_weathercode(int(valor))
                        else:
                            dia_data['datos'][param] = valor
            
            # Detectar fenómenos extremos
            detectar_fenomenos_extremos(dia_data, resultado['fenomenos_extremos'], resultado['alertas'])
            
            resultado['dias'].append(dia_data)
            
            # Limitar a 5 días
            if len(resultado['dias']) >= 5:
                break
                
        except Exception:
            continue
    
    return resultado

def interpretar_weathercode(code):
    """Interpreta los códigos WMO de fenómenos meteorológicos"""
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
        56: "Llovizna helada ligera",
        57: "Llovizna helada densa",
        61: "Lluvia ligera",
        63: "Lluvia moderada",
        65: "Lluvia intensa",
        66: "Lluvia helada ligera",
        67: "Lluvia helada intensa",
        71: "Nieve ligera",
        73: "Nieve moderada",
        75: "Nieve intensa",
        77: "Granos de nieve",
        80: "Chubascos ligeros",
        81: "Chubascos moderados",
        82: "Chubascos intensos",
        85: "Nevadas ligeras",
        86: "Nevadas intensas",
        95: "Tormenta eléctrica",
        96: "Tormenta eléctrica con granizo ligero",
        99: "Tormenta eléctrica con granizo intenso"
    }
    return codigos.get(code, f"Código {code}")

def detectar_fenomenos_extremos(dia_data, fenomenos_list, alertas_list):
    """Detecta fenómenos meteorológicos extremos"""
    datos = dia_data['datos']
    
    # Tormentas eléctricas (weathercode 95-99)
    if 'weathercode' in datos and isinstance(datos['weathercode'], int):
        if datos['weathercode'] >= 95:
            fenomeno = {
                'fecha': dia_data['fecha'],
                'tipo': 'Tormenta eléctrica',
                'intensidad': 'Severa' if datos['weathercode'] >= 98 else 'Moderada',
                'codigo': datos['weathercode']
            }
            if fenomeno not in fenomenos_list:
                fenomenos_list.append(fenomeno)
                alertas_list.append(f"⚠️ Alerta: Tormenta eléctrica el {dia_data['fecha']}")
    
    # Granizo (weathercode 96, 99)
    if 'weathercode' in datos and datos['weathercode'] in [96, 99]:
        fenomeno = {
            'fecha': dia_data['fecha'],
            'tipo': 'Granizo',
            'intensidad': 'Intenso' if datos['weathercode'] == 99 else 'Ligero'
        }
        if fenomeno not in fenomenos_list:
            fenomenos_list.append(fenomeno)
            alertas_list.append(f"⚠️ Alerta: Granizo el {dia_data['fecha']}")
    
    # Lluvia intensa (> 20 mm)
    if 'precipitation_sum' in datos:
        try:
            mm = float(datos['precipitation_sum'].replace(' mm', ''))
            if mm > 20:
                fenomeno = {
                    'fecha': dia_data['fecha'],
                    'tipo': 'Lluvia intensa',
                    'cantidad': f"{mm:.1f} mm",
                    'intensidad': 'Muy intensa' if mm > 50 else 'Intensa'
                }
                if fenomeno not in fenomenos_list:
                    fenomenos_list.append(fenomeno)
        except:
            pass
    
    # Vientos fuertes (> 40 km/h)
    if 'windspeed_10m_max' in datos:
        try:
            viento = float(datos['windspeed_10m_max'].replace(' km/h', ''))
            if viento > 40:
                fenomeno = {
                    'fecha': dia_data['fecha'],
                    'tipo': 'Vientos fuertes',
                    'velocidad': f"{viento:.1f} km/h",
                    'intensidad': 'Muy fuertes' if viento > 60 else 'Fuertes'
                }
                if fenomeno not in fenomenos_list:
                    fenomenos_list.append(fenomeno)
        except:
            pass
    
    # Nieve intensa
    if 'snowfall_sum' in datos:
        try:
            nieve = float(datos['snowfall_sum'].replace(' mm', ''))
            if nieve > 10:
                fenomeno = {
                    'fecha': dia_data['fecha'],
                    'tipo': 'Nieve',
                    'acumulado': f"{nieve:.1f} mm",
                    'intensidad': 'Intensa' if nieve > 30 else 'Moderada'
                }
                if fenomeno not in fenomenos_list:
                    fenomenos_list.append(fenomeno)
        except:
            pass

# ============================================================================
# INTERFAZ PRINCIPAL
# ============================================================================

def main():
    # Configurar opciones satelitales
    opciones_satelital = {
        'incluir_tormentas': incluir_tormentas,
        'incluir_granizo': incluir_granizo,
        'incluir_nieve': incluir_nieve,
        'incluir_vientos': incluir_vientos
    }
    
    if st.button("🚀 EXTRAER TODOS LOS DATOS BRUTOS", type="primary", use_container_width=True):
        
        with st.spinner("🔍 Iniciando extracción completa de todas las fuentes..."):
            
            # Contenedores de estado
            col1, col2, col3 = st.columns(3)
            
            with col1:
                status_aic = st.empty()
                status_aic.info("⏳ Extrayendo AIC...")
            
            with col2:
                status_smn = st.empty()
                status_smn.info("⏳ Extrayendo SMN...")
            
            with col3:
                status_sat = st.empty()
                status_sat.info("⏳ Extrayendo Satélite...")
            
            # 1. EXTRAER AIC COMPLETO
            status_aic.warning("📄 Leyendo PDF completo de AIC...")
            datos_aic, estado_aic, mensaje_aic = obtener_datos_aic_completos(fecha_base)
            
            # 2. EXTRAER SMN COMPLETO
            status_smn.warning("📊 Extrayendo todo Chapelco del SMN...")
            datos_smn, estado_smn, mensaje_smn = obtener_datos_smn_completos()
            
            # 3. EXTRAER SATÉLITE COMPLETO
            status_sat.warning("🛰️ Obteniendo parámetros absolutos satelitales...")
            datos_sat, estado_sat, mensaje_sat = obtener_datos_satelital_completos(fecha_base, opciones_satelital)
            
            # Actualizar estados
            if estado_aic:
                status_aic.success(f"✅ {mensaje_aic}")
            else:
                status_aic.error(f"❌ {mensaje_aic}")
            
            if estado_smn:
                status_smn.success(f"✅ {mensaje_smn}")
            else:
                status_smn.error(f"❌ {mensaje_smn}")
            
            if estado_sat:
                status_sat.success(f"✅ {mensaje_sat}")
            else:
                status_sat.error(f"❌ {mensaje_sat}")
            
            st.markdown("---")
            st.subheader("📦 DATOS BRUTOS EXTRAÍDOS - LISTOS PARA IA")
            
            # Mostrar resumen
            mostrar_resumen_completo(datos_aic, datos_smn, datos_sat, 
                                   estado_aic, estado_smn, estado_sat)
            
            # Preparar datos para IA
            datos_para_ia = {
                'timestamp': datetime.now().isoformat(),
                'fecha_base': fecha_base.isoformat(),
                'fuentes': {
                    'AIC': {
                        'estado': estado_aic,
                        'datos': datos_aic,
                        'mensaje': mensaje_aic
                    },
                    'SMN': {
                        'estado': estado_smn,
                        'datos': datos_smn,
                        'mensaje': mensaje_smn
                    },
                    'SATELITE': {
                        'estado': estado_sat,
                        'datos': datos_sat,
                        'mensaje': mensaje_sat
                    }
                },
                'configuracion': {
                    'fenomenos_extremos': opciones_satelital
                }
            }
            
            # Mostrar datos estructurados
            with st.expander("🧠 ESTRUCTURA DE DATOS PARA IA", expanded=True):
                st.json(datos_para_ia, expanded=False)
            
            # Botón para copiar datos
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
            
            tabs = st.tabs(["📄 AIC COMPLETO", "📊 SMN CHAPELCO", "🛰️ SATÉLITE FENÓMENOS"])
            
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
                if estado_sat and datos_sat:
                    mostrar_detalles_satelital(datos_sat)
                else:
                    st.error("No hay datos satelitales")
            
            # Resumen para IA
            st.markdown("---")
            st.subheader("🎯 RESUMEN PARA PROCESAMIENTO DE IA")
            
            fuentes_activas = sum([estado_aic, estado_smn, estado_sat])
            st.info(f"""
            **{fuentes_activas}/3 fuentes activas**
            
            La IA deberá procesar estos datos con ponderación 40/60:
            - **40%:** Fuentes locales (AIC + SMN) - Fenómenos específicos
            - **60%:** Modelos satelitales - Tendencia térmica y fenómenos absolutos
            
            **Datos disponibles para fusión:**
            - AIC: {len(datos_aic.get('dias', []))} días con condiciones detalladas
            - SMN: {len(datos_smn.get('dias', []))} días de Chapelco
            - Satélite: {len(datos_sat.get('dias', []))} días con parámetros absolutos
            """)

def mostrar_resumen_completo(datos_aic, datos_smn, datos_sat, estado_aic, estado_smn, estado_sat):
    """Muestra resumen visual de los datos extraídos"""
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown('<div class="source-card source-aic">', unsafe_allow_html=True)
        st.subheader("📄 AIC")
        if estado_aic:
            st.success("✅ ACTIVO")
            dias = len(datos_aic.get('dias', []))
            fenomenos = len(datos_aic.get('fenomenos_especiales', []))
            st.write(f"**{dias} días** extraídos")
            if fenomenos > 0:
                st.write(f"**{fenomenos} fenómenos** detectados")
            if 'texto_crudo' in datos_aic:
                st.caption(f"{len(datos_aic['texto_crudo'])} caracteres de texto")
        else:
            st.error("❌ INACTIVO")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="source-card source-smn">', unsafe_allow_html=True)
        st.subheader("📊 SMN Chapelco")
        if estado_smn:
            st.success("✅ ACTIVO")
            dias = len(datos_smn.get('dias', []))
            lineas = len(datos_smn.get('raw_lines', []))
            st.write(f"**{dias} días** extraídos")
            st.write(f"**{lineas} referencias** a Chapelco")
            if 'contenido_crudo' in datos_smn:
                st.caption(f"{len(datos_smn['contenido_crudo'])} caracteres de texto")
        else:
            st.error("❌ INACTIVO")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="source-card source-sat">', unsafe_allow_html=True)
        st.subheader("🛰️ Satélite")
        if estado_sat:
            st.success("✅ ACTIVO")
            dias = len(datos_sat.get('dias', []))
            fenomenos = len(datos_sat.get('fenomenos_extremos', []))
            st.write(f"**{dias} días** extraídos")
            st.write(f"**{fenomenos} fenómenos** extremos")
            params = len(datos_sat.get('parametros_disponibles', []))
            st.write(f"**{params} parámetros** meteorológicos")
        else:
            st.error("❌ INACTIVO")
        st.markdown('</div>', unsafe_allow_html=True)

def mostrar_detalles_aic(datos):
    """Muestra detalles completos de AIC"""
    
    if 'dias' in datos and datos['dias']:
        st.write(f"### 📅 {len(datos['dias'])} Días Pronosticados")
        
        for dia in datos['dias'][:5]:  # Mostrar máximo 5 días
            with st.expander(f"**{dia['fecha']}** - {len(dia.get('periodos', []))} períodos"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Temperaturas:**")
                    if 'temperaturas' in dia:
                        temps = dia['temperaturas']
                        if 'max' in temps:
                            st.write(f"Máx: {temps['max']}°C")
                        if 'min' in temps:
                            st.write(f"Mín: {temps['min']}°C")
                    
                    st.write("**Vientos:**")
                    if 'vientos' in dia:
                        vientos = dia['vientos']
                        if 'velocidad' in vientos:
                            st.write(f"Velocidad: {vientos['velocidad']} km/h")
                        if 'direccion' in vientos:
                            st.write(f"Dirección: {vientos['direccion']}")
                
                with col2:
                    st.write("**Condiciones:**")
                    if 'condiciones' in dia and 'descripcion' in dia['condiciones']:
                        st.write(dia['condiciones']['descripcion'])
                    
                    st.write("**Fenómenos:**")
                    if dia.get('fenomenos'):
                        for fen in dia['fenomenos']:
                            st.write(f"- {fen}")
                    else:
                        st.write("Ninguno detectado")
        
        # Fenómenos especiales
        if datos.get('fenomenos_especiales'):
            st.write("### ⚡ Fenómenos Especiales Detectados")
            for fen in datos['fenomenos_especiales']:
                st.markdown(f'<div class="phenomenon-alert">{fen}</div>', unsafe_allow_html=True)
        
        # Texto crudo (muestra parcial)
        if 'texto_crudo' in datos:
            with st.expander("📋 Texto Crudo Extraído (primeros 2000 caracteres)"):
                st.text(datos['texto_crudo'][:2000])

def mostrar_detalles_smn(datos):
    """Muestra detalles completos de SMN Chapelco"""
    
    # Información de estación
    if datos.get('estacion_info'):
        st.write("### 🏔️ Información de Estación")
        for key, value in datos['estacion_info'].items():
            st.write(f"**{key.title()}:** {value}")
    
    # Días extraídos
    if datos.get('dias'):
        st.write(f"### 📊 {len(datos['dias'])} Días de Datos")
        
        for dia in datos['dias'][:5]:  # Mostrar máximo 5 días
            with st.expander(f"**{dia['fecha']}** - Datos SMN"):
                st.write("**Línea original:**")
                st.code(dia.get('linea_original', 'No disponible'))
                
                st.write("**Datos extraídos:**")
                if 'temperatura' in dia:
                    st.write(f"Temperatura: {dia['temperatura']}°C")
                if 'temperatura2' in dia:
                    st.write(f"Temperatura 2: {dia['temperatura2']}°C")
                if 'viento_kmh' in dia:
                    st.write(f"Viento: {dia['viento_kmh']} km/h")
                if 'precipitacion_mm' in dia:
                    st.write(f"Precipitación: {dia['precipitacion_mm']} mm")
                if 'fenomenos' in dia:
                    st.write("Fenómenos detectados:")
                    for fen in dia['fenomenos']:
                        st.write(f"- {fen}")
                
                if 'numeros' in dia:
                    st.write(f"**{len(dia['numeros'])} números encontrados:**")
                    st.write(", ".join(dia['numeros']))
    
    # Líneas crudas donde apareció Chapelco
    if datos.get('raw_lines'):
        st.write(f"### 🔍 {len(datos['raw_lines'])} Referencias a Chapelco")
        for i, ref in enumerate(datos['raw_lines'][:3]):  # Mostrar 3 referencias
            with st.expander(f"Referencia #{i+1} (posición {ref['posicion']})"):
                st.text(ref['contexto'])

def mostrar_detalles_satelital(datos):
    """Muestra detalles completos de datos satelitales"""
    
    # Fenómenos extremos detectados
    if datos.get('fenomenos_extremos'):
        st.write("### ⚡ Fenómenos Extremos Detectados")
        for fen in datos['fenomenos_extremos']:
            st.markdown(f'<div class="phenomenon-alert">'
                       f'**{fen["tipo"]}** el {fen["fecha"]} - {fen.get("intensidad", "Detectado")}'
                       f'</div>', unsafe_allow_html=True)
    
    # Días con datos
    if datos.get('dias'):
        st.write(f"### 🌤️ {len(datos['dias'])} Días Pronosticados")
        
        for dia in datos['dias'][:5]:  # Mostrar máximo 5 días
            with st.expander(f"**{dia['fecha']}** - Parámetros Satelitales"):
                
                # Agrupar parámetros por categoría
                categorias = {
                    'Temperatura': ['temperature', 'apparent'],
                    'Viento': ['wind', 'gust'],
                    'Precipitación': ['precipitation', 'rain', 'snow', 'shower'],
                    'Radiación': ['uv', 'index'],
                    'Fenómenos': ['weathercode', 'cape', 'hail', 'lightning']
                }
                
                for cat_name, keywords in categorias.items():
                    params_cat = []
                    for param, valor in dia['datos'].items():
                        if any(keyword in param for keyword in keywords):
                            params_cat.append((param, valor))
                    
                    if params_cat:
                        st.write(f"**{cat_name}:**")
                        for param, valor in params_cat:
                            # Formatear nombre del parámetro
                            param_name = param.replace('_', ' ').title()
                            st.write(f"- {param_name}: {valor}")
                        st.write("")
    
    # Parámetros disponibles
    if datos.get('parametros_disponibles'):
        st.write(f"### 📋 {len(datos['parametros_disponibles'])} Parámetros Disponibles")
        params_per_row = 4
        params = datos['parametros_disponibles']
        
        for i in range(0, len(params), params_per_row):
            cols = st.columns(params_per_row)
            for j in range(params_per_row):
                if i + j < len(params):
                    with cols[j]:
                        st.code(params[i + j])

# Ejecutar aplicación
if __name__ == "__main__":
    main()

# Footer
st.markdown("---")
st.caption("""
**Sistema de Extracción Meteorológica V4.2** | 
Extracción completa de fuentes | 
Datos brutos listos para IA | 
Ponderación 40/60 Local/Satelital
""")
