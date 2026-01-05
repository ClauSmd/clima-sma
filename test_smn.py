import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime, timedelta
import zipfile
import io
import re
import pandas as pd
import json
import time
from typing import Dict, List, Tuple, Optional
import urllib3
from bs4 import BeautifulSoup
import hashlib
import os
from dataclasses import dataclass

# Deshabilitar warnings SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================================================
# 1. CONFIGURACIÓN DE PÁGINA Y ESTILO MEJORADO
# ============================================================================
st.set_page_config(
    page_title="Sistema Climático Inteligente SMA v2026",
    page_icon="🏔️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS mejorado
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        padding: 20px 0;
        font-weight: 800;
    }
    
    .data-source-card {
        background: linear-gradient(145deg, #2d3748 0%, #4a5568 100%);
        border-radius: 12px;
        padding: 20px;
        margin: 10px 0;
        border-left: 5px solid #4299e1;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    .forecast-day {
        background: linear-gradient(135deg, #1a202c 0%, #2d3748 100%);
        border-radius: 15px;
        padding: 25px;
        margin: 15px 0;
        border: 1px solid #4a5568;
        transition: transform 0.3s ease;
    }
    
    .forecast-day:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 20px rgba(0, 0, 0, 0.2);
    }
    
    .ai-analysis-box {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        border-radius: 15px;
        padding: 30px;
        border: 2px solid #38b2ac;
        font-size: 1.1rem;
        line-height: 1.8;
        color: #e2e8f0;
        margin: 20px 0;
    }
    
    .raw-data-box {
        background-color: #0f172a;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #334155;
        font-family: 'Roboto Mono', monospace;
        font-size: 0.85rem;
        height: 400px;
        overflow-y: auto;
        white-space: pre-wrap;
        color: #94a3b8;
    }
    
    .metric-card {
        background: linear-gradient(135deg, #2d3748 0%, #4a5568 100%);
        border-radius: 10px;
        padding: 15px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    .date-selector {
        background: #2d3748;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
    }
    
    .warning-box {
        background: linear-gradient(135deg, #7b341e 0%, #9c4221 100%);
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
        color: white;
        border-left: 5px solid #ed8936;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# 2. CLASES DE DATOS ESTRUCTURADOS
# ============================================================================

@dataclass
class ForecastDay:
    """Estructura unificada para datos diarios"""
    fecha: str
    fecha_obj: datetime
    temp_max: Optional[float] = None
    temp_min: Optional[float] = None
    viento_vel: Optional[float] = None
    viento_dir: Optional[str] = None
    precipitacion: Optional[float] = None
    cielo: Optional[str] = None
    descripcion: Optional[str] = None
    fuente: str = ""
    rafagas: Optional[float] = None
    presion: Optional[float] = None

@dataclass
class DataSource:
    """Información de la fuente de datos"""
    nombre: str
    datos: Dict
    estado: bool
    debug_info: str
    raw_data: str

# ============================================================================
# 3. FUNCIONES DE EXTRACCIÓN MEJORADAS
# ============================================================================

def extraer_datos_smn() -> DataSource:
    """Extrae datos del SMN con manejo robusto de errores y backup"""
    datos_estructurados = {}
    raw_text = ""
    debug_info = ""
    
    try:
        # Intentar descargar datos actuales
        url = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=pron5d"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200 and len(response.content) > 1000:
            # Procesar ZIP actual
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                archivos_txt = [f for f in z.namelist() if f.endswith('.txt')]
                if archivos_txt:
                    archivo = archivos_txt[0]
                    with z.open(archivo) as f:
                        contenido = f.read().decode('utf-8', errors='ignore')
                        raw_text = contenido[:5000]  # Guardar para debug
                        
                    # Buscar CHAPELCO_AERO
                    if "CHAPELCO_AERO" in contenido:
                        # Extraer bloque completo
                        partes = contenido.split("CHAPELCO_AERO")
                        if len(partes) > 1:
                            bloque = partes[1]
                            
                            # Buscar próximas 45 líneas
                            lineas = bloque.split('\n')[:50]
                            datos_lineas = []
                            
                            for linea in lineas:
                                # Buscar líneas con datos (formato fecha)
                                if re.match(r'\s*\d{2}/\w{3}/\d{4}', linea):
                                    datos_lineas.append(linea)
                            
                            # Procesar por día
                            datos_por_dia = {}
                            for linea in datos_lineas:
                                try:
                                    # Extraer fecha (primeros 11 caracteres)
                                    fecha_str = linea[:11].strip()
                                    fecha_obj = datetime.strptime(fecha_str, '%d/%b/%Y')
                                    fecha_key = fecha_obj.strftime('%Y-%m-%d')
                                    
                                    # Extraer temperatura
                                    temp_match = re.search(r'(\d+\.\d+)\s*°?C?', linea[20:40])
                                    temp = float(temp_match.group(1)) if temp_match else None
                                    
                                    # Extraer viento
                                    viento_match = re.search(r'(\d+)\s*\|\s*(\d+)', linea[40:60])
                                    viento_dir = int(viento_match.group(1)) if viento_match else None
                                    viento_vel = int(viento_match.group(2)) if viento_match else None
                                    
                                    # Extraer precipitación
                                    precip_match = re.search(r'(\d+\.\d+)\s*mm?', linea[60:])
                                    precip = float(precip_match.group(1)) if precip_match else None
                                    
                                    # Agregar al día correspondiente
                                    if fecha_key not in datos_por_dia:
                                        datos_por_dia[fecha_key] = {
                                            'temps': [],
                                            'vientos_dir': [],
                                            'vientos_vel': [],
                                            'precip_total': 0
                                        }
                                    
                                    if temp:
                                        datos_por_dia[fecha_key]['temps'].append(temp)
                                    if viento_vel:
                                        datos_por_dia[fecha_key]['vientos_vel'].append(viento_vel)
                                    if viento_dir:
                                        datos_por_dia[fecha_key]['vientos_dir'].append(viento_dir)
                                    if precip:
                                        datos_por_dia[fecha_key]['precip_total'] += precip
                                        
                                except Exception as e:
                                    continue
                            
                            # Crear estructura final
                            for fecha_key, datos in datos_por_dia.items():
                                if datos['temps']:
                                    forecast = ForecastDay(
                                        fecha=fecha_key,
                                        fecha_obj=datetime.strptime(fecha_key, '%Y-%m-%d'),
                                        temp_max=max(datos['temps']),
                                        temp_min=min(datos['temps']),
                                        viento_vel=sum(datos['vientos_vel'])/len(datos['vientos_vel']) if datos['vientos_vel'] else None,
                                        precipitacion=datos['precip_total'],
                                        fuente="SMN"
                                    )
                                    datos_estructurados[fecha_key] = forecast
                            
                            debug_info = f"OK - {len(datos_estructurados)} días procesados"
                        else:
                            debug_info = "No se encontró CHAPELCO_AERO"
                    else:
                        debug_info = "Estación CHAPELCO_AERO no encontrada"
                else:
                    debug_info = "No hay archivos TXT en el ZIP"
        else:
            debug_info = f"Error descarga: {response.status_code}"
            
    except Exception as e:
        debug_info = f"Error: {str(e)}"
        # Aquí podrías implementar lógica de backup de 24h
    
    return DataSource(
        nombre="SMN",
        datos=datos_estructurados,
        estado=len(datos_estructurados) > 0,
        debug_info=debug_info,
        raw_data=raw_text[:2000]
    )

def extraer_datos_aic() -> DataSource:
    """Extrae datos estructurados del AIC"""
    datos_estructurados = {}
    raw_html = ""
    
    try:
        url = "https://www.aic.gob.ar/sitio/extendido-pdf?a=1029&z=1750130550"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }
        
        response = requests.get(url, headers=headers, verify=False, timeout=30)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            raw_html = str(soup)[:5000]
            
            # Extraer descripción general
            desc_general = ""
            desc_elem = soup.find(id="descripcion-general")
            if desc_elem:
                desc_general = desc_elem.get_text(strip=True)
            
            # Extraer fechas
            fechas = []
            fila_fechas = soup.find(class_="fila-fechas")
            if fila_fechas:
                th_elements = fila_fechas.find_all('th')[1:]  # Excluir primera celda vacía
                for th in th_elements:
                    if th.has_attr('colspan'):
                        fecha_text = th.get_text(strip=True)
                        try:
                            fecha_obj = datetime.strptime(fecha_text, '%d-%m-%Y')
                            fechas.append(fecha_obj.strftime('%Y-%m-%d'))
                        except:
                            continue
            
            # Extraer datos por fila
            datos_filas = {}
            
            # Mapeo de IDs a campos
            mapeo_filas = {
                'fila-cielo': 'cielo',
                'fila-temperatura': 'temperatura',
                'fila-viento': 'viento',
                'fila-rafagas': 'rafagas',
                'fila-direccion': 'direccion',
                'fila-presion': 'presion'
            }
            
            for fila_id, campo in mapeo_filas.items():
                fila = soup.find(id=fila_id)
                if fila:
                    celdas = fila.find_all('td')
                    datos_celdas = [cell.get_text(strip=True) for cell in celdas]
                    datos_filas[campo] = datos_celdas
            
            # Construir datos por día
            for i, fecha in enumerate(fechas[:6]):  # Máximo 6 días
                try:
                    idx_dia = i * 2
                    idx_noche = idx_dia + 1
                    
                    # Temperatura (Día = máxima, Noche = mínima)
                    temp_dia = 0
                    temp_noche = 0
                    
                    if 'temperatura' in datos_filas and len(datos_filas['temperatura']) > idx_noche:
                        temp_dia_str = datos_filas['temperatura'][idx_dia].replace('°C', '').strip()
                        temp_noche_str = datos_filas['temperatura'][idx_noche].replace('°C', '').strip()
                        temp_dia = float(temp_dia_str) if temp_dia_str.replace('.', '').isdigit() else None
                        temp_noche = float(temp_noche_str) if temp_noche_str.replace('.', '').isdigit() else None
                    
                    # Viento
                    viento_vel = None
                    if 'viento' in datos_filas and len(datos_filas['viento']) > idx_dia:
                        viento_str = datos_filas['viento'][idx_dia].replace('km/h', '').strip()
                        viento_vel = float(viento_str) if viento_str.replace('.', '').isdigit() else None
                    
                    # Dirección
                    viento_dir = None
                    if 'direccion' in datos_filas and len(datos_filas['direccion']) > idx_dia:
                        viento_dir = datos_filas['direccion'][idx_dia]
                    
                    # Cielo
                    cielo = ""
                    if 'cielo' in datos_filas and len(datos_filas['cielo']) > idx_dia:
                        cielo = datos_filas['cielo'][idx_dia]
                    
                    # Crear forecast day
                    forecast = ForecastDay(
                        fecha=fecha,
                        fecha_obj=datetime.strptime(fecha, '%Y-%m-%d'),
                        temp_max=temp_dia,
                        temp_min=temp_noche,
                        viento_vel=viento_vel,
                        viento_dir=viento_dir,
                        cielo=cielo,
                        descripcion=desc_general,
                        fuente="AIC"
                    )
                    
                    datos_estructurados[fecha] = forecast
                    
                except Exception as e:
                    continue
            
            debug_info = f"OK - {len(datos_estructurados)} días procesados"
        else:
            debug_info = f"Error HTTP: {response.status_code}"
            
    except Exception as e:
        debug_info = f"Error: {str(e)}"
    
    return DataSource(
        nombre="AIC",
        datos=datos_estructurados,
        estado=len(datos_estructurados) > 0,
        debug_info=debug_info,
        raw_data=raw_html
    )

def obtener_datos_openmeteo() -> DataSource:
    """Obtiene datos de Open-Meteo con múltiples parámetros"""
    datos_estructurados = {}
    raw_json = ""
    
    try:
        # Parámetros completos para análisis detallado
        params = {
            'latitude': -40.15,
            'longitude': -71.35,
            'daily': [
                'temperature_2m_max', 'temperature_2m_min',
                'apparent_temperature_max', 'apparent_temperature_min',
                'precipitation_sum', 'rain_sum', 'snowfall_sum',
                'precipitation_hours', 'weather_code',
                'wind_speed_10m_max', 'wind_gusts_10m_max',
                'wind_direction_10m_dominant',
                'shortwave_radiation_sum', 'et0_fao_evapotranspiration'
            ],
            'hourly': [
                'temperature_2m', 'relative_humidity_2m',
                'dew_point_2m', 'precipitation', 'rain',
                'snowfall', 'weather_code', 'pressure_msl',
                'visibility', 'wind_speed_10m', 'wind_direction_10m',
                'soil_temperature_0cm'
            ],
            'timezone': 'America/Argentina/Buenos_Aires',
            'forecast_days': 7
        }
        
        url = "https://api.open-meteo.com/v1/forecast"
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            raw_json = json.dumps(data, indent=2)[:5000]
            
            # Procesar datos diarios
            daily = data.get('daily', {})
            dates = daily.get('time', [])
            
            for i, date_str in enumerate(dates[:5]):  # Primeros 5 días
                try:
                    fecha_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    
                    # Determinar condiciones del tiempo basado en weather_code
                    weather_code = daily.get('weather_code', [])[i] if i < len(daily.get('weather_code', [])) else 0
                    condiciones = interpretar_weather_code(weather_code)
                    
                    forecast = ForecastDay(
                        fecha=date_str,
                        fecha_obj=fecha_obj,
                        temp_max=daily.get('temperature_2m_max', [])[i] if i < len(daily.get('temperature_2m_max', [])) else None,
                        temp_min=daily.get('temperature_2m_min', [])[i] if i < len(daily.get('temperature_2m_min', [])) else None,
                        viento_vel=daily.get('wind_speed_10m_max', [])[i] if i < len(daily.get('wind_speed_10m_max', [])) else None,
                        precipitacion=daily.get('precipitation_sum', [])[i] if i < len(daily.get('precipitation_sum', [])) else None,
                        cielo=condiciones,
                        fuente="Open-Meteo"
                    )
                    
                    datos_estructurados[date_str] = forecast
                    
                except Exception as e:
                    continue
            
            debug_info = f"OK - {len(datos_estructurados)} días procesados"
        else:
            debug_info = f"Error API: {response.status_code}"
            
    except Exception as e:
        debug_info = f"Error: {str(e)}"
    
    return DataSource(
        nombre="Open-Meteo",
        datos=datos_estructurados,
        estado=len(datos_estructurados) > 0,
        debug_info=debug_info,
        raw_data=raw_json
    )

def interpretar_weather_code(code: int) -> str:
    """Interpreta el código de tiempo de Open-Meteo"""
    weather_codes = {
        0: "Despejado",
        1: "Mayormente despejado",
        2: "Parcialmente nublado",
        3: "Nublado",
        45: "Niebla",
        48: "Niebla con escarcha",
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
        77: "Granizo",
        80: "Chubascos ligeros",
        81: "Chubascos moderados",
        82: "Chubascos violentos",
        85: "Nevadas ligeras",
        86: "Nevadas intensas",
        95: "Tormenta eléctrica",
        96: "Tormenta con granizo ligero",
        99: "Tormenta con granizo intenso"
    }
    return weather_codes.get(code, "Condiciones variables")

# ============================================================================
# 4. FUNCIÓN DE ANÁLISIS CON GEMINI 2.0 FLASH
# ============================================================================

def analizar_con_gemini(datos_combinados: Dict, fecha_inicio: datetime) -> Tuple[str, str]:
    """Analiza los datos combinados usando Gemini 2.0 Flash"""
    
    # Preparar prompt estructurado
    datos_para_ia = []
    for fecha_str, fuentes in datos_combinados.items():
        dia_info = {
            "fecha": fecha_str,
            "fuentes": {}
        }
        for fuente_nombre, datos_fuente in fuentes.items():
            if datos_fuente:
                dia_info["fuentes"][fuente_nombre] = {
                    "temp_max": datos_fuente.temp_max,
                    "temp_min": datos_fuente.temp_min,
                    "viento_vel": datos_fuente.viento_vel,
                    "viento_dir": datos_fuente.viento_dir,
                    "precipitacion": datos_fuente.precipitacion,
                    "cielo": datos_fuente.cielo,
                    "descripcion": datos_fuente.descripcion
                }
        datos_para_ia.append(dia_info)
    
    prompt = f"""
    Eres un meteorólogo experto analizando datos para San Martín de los Andes, Neuquén.
    
    FECHA ACTUAL: {datetime.now().strftime('%A %d de %B de %Y')}
    FECHA DE ANÁLISIS: {fecha_inicio.strftime('%d/%m/%Y')}
    
    DATOS ESTRUCTURADOS POR DÍA Y FUENTE:
    {json.dumps(datos_para_ia, indent=2, ensure_ascii=False)}
    
    INSTRUCCIONES ESPECÍFICAS:
    1. Genera un pronóstico para los próximos 5 días comenzando desde {fecha_inicio.strftime('%d/%m/%Y')}
    2. Para cada día, sigue EXACTAMENTE este formato:
       [Día de la semana] [Día] de [Mes] – San Martín de los Andes: [descripción concisa del tiempo]. 
       Máxima de [X]°C, mínima de [Y]°C. Viento del [dirección] entre [vel_min] y [vel_max] km/h. 
       [Detalles sobre precipitación, tormentas, etc.].
    
    3. Usa estos hashtags: #SanMartínDeLosAndes #ClimaSMA #[CondicionPrincipal]
    4. Combina inteligentemente la información de las 3 fuentes:
       - AIC: Pronóstico oficial local
       - SMN: Datos de estación Chapelco Aero
       - Open-Meteo: Modelos globales
    
    5. Sé específico sobre riesgos meteorológicos: tormentas, granizo, nieve, niebla, vientos fuertes.
    6. Proporciona recomendaciones prácticas si hay condiciones adversas.
    
    Respuesta en español, claro y profesional.
    """
    
    try:
        # Usar Gemini 2.0 Flash específicamente
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(prompt)
        
        if response.text:
            return response.text, "Gemini 2.0 Flash"
        else:
            return "Error: No se recibió respuesta de la IA", "Error"
            
    except Exception as e:
        return f"Error en análisis IA: {str(e)}", "Error"

# ============================================================================
# 5. FUNCIONES AUXILIARES
# ============================================================================

def combinar_datos_fuentes(fuentes: List[DataSource]) -> Dict:
    """Combina datos de múltiples fuentes por fecha"""
    datos_combinados = {}
    
    for fuente in fuentes:
        if fuente.estado:
            for fecha_str, datos_dia in fuente.datos.items():
                if fecha_str not in datos_combinados:
                    datos_combinados[fecha_str] = {}
                datos_combinados[fecha_str][fuente.nombre] = datos_dia
    
    return datos_combinados

def mostrar_resumen_datos(fuentes: List[DataSource]):
    """Muestra resumen visual de los datos obtenidos"""
    st.markdown("### 📊 Resumen de Datos Obtenidos")
    
    cols = st.columns(len(fuentes))
    
    for idx, fuente in enumerate(fuentes):
        with cols[idx]:
            st.markdown(f"""
            <div class="data-source-card">
                <h4>{fuente.nombre}</h4>
                <p><strong>Estado:</strong> {"✅ ONLINE" if fuente.estado else "❌ OFFLINE"}</p>
                <p><strong>Días:</strong> {len(fuente.datos)}</p>
                <p><strong>Info:</strong> {fuente.debug_info}</p>
            </div>
            """, unsafe_allow_html=True)

def mostrar_datos_detallados(datos_combinados: Dict):
    """Muestra datos detallados por día y fuente"""
    st.markdown("### 🔍 Datos Detallados por Día")
    
    for fecha_str, fuentes_dia in datos_combinados.items():
        fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d')
        dia_semana = fecha_obj.strftime('%A')
        dia_mes = fecha_obj.strftime('%d')
        mes = fecha_obj.strftime('%B')
        
        st.markdown(f"""
        <div class="forecast-day">
            <h4>{dia_semana} {dia_mes} de {mes}</h4>
        """, unsafe_allow_html=True)
        
        # Crear tabla con datos por fuente
        datos_tabla = []
        for fuente_nombre, datos in fuentes_dia.items():
            if datos:
                datos_tabla.append({
                    "Fuente": fuente_nombre,
                    "Máx": f"{datos.temp_max}°C" if datos.temp_max else "N/A",
                    "Mín": f"{datos.temp_min}°C" if datos.temp_min else "N/A",
                    "Viento": f"{datos.viento_vel} km/h" if datos.viento_vel else "N/A",
                    "Precip": f"{datos.precipitacion} mm" if datos.precipitacion else "N/A",
                    "Cielo": datos.cielo or "N/A"
                })
        
        if datos_tabla:
            df = pd.DataFrame(datos_tabla)
            st.dataframe(df, use_container_width=True, hide_index=True)
        
        st.markdown("</div>", unsafe_allow_html=True)

# ============================================================================
# 6. INTERFAZ PRINCIPAL
# ============================================================================

def main():
    # Header principal
    st.markdown('<h1 class="main-header">🏔️ Sistema Meteorológico Inteligente SMA</h1>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("### ⚙️ Configuración")
        
        st.markdown('<div class="date-selector">', unsafe_allow_html=True)
        fecha_seleccionada = st.date_input(
            "Fecha de inicio del pronóstico",
            datetime.now(),
            min_value=datetime.now(),
            max_value=datetime.now() + timedelta(days=14)
        )
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown("---")
        
        st.markdown("### 🔧 Opciones")
        mostrar_detalles = st.checkbox("Mostrar datos detallados", value=True)
        mostrar_raw = st.checkbox("Mostrar datos crudos", value=False)
        
        st.markdown("---")
        
        st.markdown("### 📈 Ponderación")
        st.info("""
        **Estrategia de análisis:**
        - AIC: 30% (Pronóstico local oficial)
        - SMN: 30% (Datos de estación)
        - Open-Meteo: 40% (Modelos globales)
        """)
    
    # Botón principal
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚀 GENERAR PRONÓSTICO AVANZADO", 
                    type="primary", 
                    use_container_width=True,
                    help="Click para analizar todas las fuentes meteorológicas"):
            
            try:
                # Configurar API Key
                genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
                
                # Mostrar progreso
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Obtener datos de todas las fuentes
                status_text.text("🔄 Obteniendo datos del SMN...")
                fuente_smn = extraer_datos_smn()
                progress_bar.progress(25)
                
                status_text.text("🔄 Obteniendo datos del AIC...")
                fuente_aic = extraer_datos_aic()
                progress_bar.progress(50)
                
                status_text.text("🔄 Obteniendo datos de Open-Meteo...")
                fuente_om = obtener_datos_openmeteo()
                progress_bar.progress(75)
                
                # Combinar datos
                status_text.text("🔄 Combinando datos de fuentes...")
                datos_combinados = combinar_datos_fuentes([fuente_smn, fuente_aic, fuente_om])
                
                # Mostrar resumen
                mostrar_resumen_datos([fuente_smn, fuente_aic, fuente_om])
                
                if mostrar_detalles and datos_combinados:
                    mostrar_datos_detallados(datos_combinados)
                
                # Análisis con IA
                status_text.text("🧠 Analizando con Gemini 2.0 Flash...")
                pronostico, motor_ia = analizar_con_gemini(datos_combinados, fecha_seleccionada)
                progress_bar.progress(100)
                status_text.text("✅ Análisis completo")
                
                # Mostrar pronóstico
                st.markdown("---")
                st.markdown("### 📋 PRONÓSTICO GENERADO")
                st.markdown(f'<div class="ai-analysis-box">{pronostico}</div>', unsafe_allow_html=True)
                
                # Mostrar motor usado
                st.info(f"**Motor de IA utilizado:** {motor_ia}")
                
                # Mostrar datos crudos si se solicita
                if mostrar_raw:
                    st.markdown("---")
                    st.markdown("### 📄 Datos Crudos por Fuente")
                    
                    tabs = st.tabs(["SMN", "AIC", "Open-Meteo"])
                    
                    with tabs[0]:
                        st.markdown("#### Datos SMN (texto crudo)")
                        st.markdown(f'<div class="raw-data-box">{fuente_smn.raw_data}</div>', unsafe_allow_html=True)
                    
                    with tabs[1]:
                        st.markdown("#### Datos AIC (HTML crudo)")
                        st.markdown(f'<div class="raw-data-box">{fuente_aic.raw_data}</div>', unsafe_allow_html=True)
                    
                    with tabs[2]:
                        st.markdown("#### Datos Open-Meteo (JSON crudo)")
                        st.markdown(f'<div class="raw-data-box">{fuente_om.raw_data}</div>', unsafe_allow_html=True)
                
            except Exception as e:
                st.error(f"Error en el proceso: {str(e)}")
                st.info("Verifica que la API Key de Google Gemini esté configurada en los Secrets de Streamlit.")
    
    # Información adicional
    with st.expander("ℹ️ Acerca de este sistema"):
        st.markdown("""
        **Sistema Meteorológico Inteligente SMA v2026**
        
        Este sistema integra y analiza datos de múltiples fuentes:
        
        1. **SMN (Servicio Meteorológico Nacional)**
           - Datos de la estación Chapelco Aero
           - Pronóstico horario detallado
           - Información oficial argentina
        
        2. **AIC (Aeronáutica Argentina)**
           - Pronóstico extendido oficial
           - Información específica para aviación
           - Datos de presión y vientos
        
        3. **Open-Meteo**
           - Modelos climáticos globales
           - Múltiples parámetros meteorológicos
           - Datos horarios y diarios
        
        **Características:**
        - Análisis inteligente con Gemini 2.0 Flash
        - Combina 3 fuentes con ponderación inteligente
        - Detecta condiciones adversas automáticamente
        - Sistema de backup para fallos de datos
        - Interfaz moderna y responsive
        """)

if __name__ == "__main__":
    main()
