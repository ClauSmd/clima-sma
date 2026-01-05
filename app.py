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
st.set_page_config(page_title="Extracción Meteorológica SMA", page_icon="📡", layout="wide")

# CSS personalizado
st.markdown("""
<style>
    .data-card {
        background-color: #1a1a1a;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        border-left: 4px solid;
    }
    .card-aic { border-left-color: #4CAF50; }
    .card-smn { border-left-color: #2196F3; }
    .card-om { border-left-color: #FF9800; }
    .day-header {
        background-color: #2d2d2d;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
        font-weight: bold;
    }
    .hour-row {
        background-color: #252525;
        padding: 8px;
        margin: 2px 0;
        border-radius: 3px;
        font-family: monospace;
    }
</style>
""", unsafe_allow_html=True)

# Título principal
st.title("📡 Extracción Individual de Fuentes Meteorológicas")
st.markdown("**AIC + SMN + Open-Meteo funcionando por separado**")
st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuración")
    fecha_base = st.date_input("Fecha de inicio", datetime.now().date())
    
    st.markdown("---")
    st.header("🔧 Opciones")
    mostrar_crudo = st.checkbox("Mostrar datos crudos", False)
    
    st.markdown("---")
    st.info("""
    **Modo: Extracción Individual**
    
    - AIC: Formato específico con día/noche
    - SMN: Datos horarios de Chapelco
    - Open-Meteo: Conexión y datos crudos
    - Sin IA por ahora
    """)

# ============================================================================
# AIC - FORMATO ESPECÍFICO
# ============================================================================

def obtener_datos_aic_formateados():
    """Obtiene datos de AIC con formato específico: Día/Noche separados"""
    
    urls = [
        "https://www.aic.gob.ar/sitio/extendido-pdf?a=1029&z=1750130550",
        "https://www.aic.gob.ar/sitio/extendido-pdf?id_localidad=22&id_pronostico=1",
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/pdf, */*',
        'Referer': 'https://www.aic.gob.ar/'
    }
    
    for url in urls:
        try:
            response = requests.get(url, headers=headers, verify=False, timeout=30)
            
            if response.status_code == 200 and response.content[:4] == b'%PDF':
                with pdfplumber.open(io.BytesIO(response.content)) as pdf:
                    texto = pdf.pages[0].extract_text()
                    
                    if texto and len(texto.strip()) > 200:
                        datos_formateados = parsear_aic_formato_especifico(texto)
                        if datos_formateados:
                            return datos_formateados, True, f"✅ AIC: {len(datos_formateados)} días formateados"
            
            time.sleep(1)
        except Exception:
            continue
    
    return [], False, "❌ No se pudo obtener el PDF de AIC"

def parsear_aic_formato_especifico(texto):
    """Parsea AIC en el formato específico requerido"""
    
    datos_dias = []
    
    try:
        # Separar por líneas
        lineas = [line.strip() for line in texto.split('\n') if line.strip()]
        
        # Buscar líneas de fechas (generalmente línea 1 o 2)
        lineas_fechas = []
        for i, linea in enumerate(lineas[:10]):
            if re.search(r'\d{2}-\d{2}-\d{4}', linea) or re.search(r'\d{2}/\d{2}/\d{4}', linea):
                lineas_fechas.append((i, linea))
        
        if not lineas_fechas:
            return []
        
        # Tomar primera línea con fechas
        idx_fechas, linea_fechas = lineas_fechas[0]
        
        # Extraer todas las fechas de esa línea
        fechas = re.findall(r'\d{2}-\d{2}-\d{4}', linea_fechas)
        if not fechas:
            fechas = re.findall(r'\d{2}/\d{2}/\d{4}', linea_fechas)
            # Convertir formato si es necesario
            fechas = [f.replace('/', '-') for f in fechas]
        
        # Buscar línea de periodos (Día/Noche)
        lineas_periodos = []
        for i in range(idx_fechas + 1, min(idx_fechas + 5, len(lineas))):
            if 'Día' in lineas[i] or 'Noche' in lineas[i]:
                lineas_periodos.append((i, lineas[i]))
        
        if not lineas_periodos:
            return []
        
        # Parsear cada día
        for i, fecha_str in enumerate(fechas[:3]):  # Máximo 3 días
            try:
                # Convertir fecha
                fecha_dt = datetime.strptime(fecha_str, '%d-%m-%Y')
                fecha_formateada = fecha_dt.strftime('%d/%m/%Y')
                
                # Buscar datos para este día
                dia_data = buscar_datos_dia_aic(lineas, fecha_str, i)
                
                if dia_data:
                    datos_dias.append({
                        'fecha': fecha_formateada,
                        'fecha_dt': fecha_dt.date(),
                        'cielo_dia': dia_data.get('cielo_dia', 'No disponible'),
                        'cielo_noche': dia_data.get('cielo_noche', 'No disponible'),
                        'temp_max': dia_data.get('temp_dia', 'N/D'),
                        'temp_min': dia_data.get('temp_noche', 'N/D'),
                        'viento_dia': dia_data.get('viento_dia', 'N/D'),
                        'viento_noche': dia_data.get('viento_noche', 'N/D'),
                        'rafaga_dia': dia_data.get('rafaga_dia', 'N/D'),
                        'rafaga_noche': dia_data.get('rafaga_noche', 'N/D'),
                        'direccion_dia': dia_data.get('dir_dia', 'N/D'),
                        'direccion_noche': dia_data.get('dir_noche', 'N/D'),
                        'presion_dia': dia_data.get('presion_dia', 'N/D'),
                        'presion_noche': dia_data.get('presion_noche', 'N/D')
                    })
                    
            except Exception:
                continue
        
        return datos_dias
        
    except Exception as e:
        st.error(f"Error parseando AIC: {str(e)}")
        return []

def buscar_datos_dia_aic(lineas, fecha_str, idx_dia):
    """Busca datos específicos para un día en las líneas del AIC"""
    
    datos = {}
    
    # Buscar la fecha en las líneas
    for i, linea in enumerate(lineas):
        if fecha_str in linea:
            # Buscar 10 líneas alrededor
            for j in range(max(0, i-5), min(len(lineas), i+10)):
                linea_actual = lineas[j]
                
                # Temperaturas
                if 'ºC' in linea_actual or '°C' in linea_actual:
                    temps = re.findall(r'(-?\d+)\s*[ºC°C]', linea_actual)
                    if len(temps) >= 2:
                        if idx_dia * 2 < len(temps):
                            datos['temp_dia'] = temps[idx_dia * 2]
                        if idx_dia * 2 + 1 < len(temps):
                            datos['temp_noche'] = temps[idx_dia * 2 + 1]
                
                # Viento
                if 'km/h' in linea_actual and 'Dirección' not in linea_actual:
                    vientos = re.findall(r'(\d+)\s*km/h', linea_actual)
                    if len(vientos) >= 2:
                        if idx_dia * 2 < len(vientos):
                            datos['viento_dia'] = vientos[idx_dia * 2]
                        if idx_dia * 2 + 1 < len(vientos):
                            datos['viento_noche'] = vientos[idx_dia * 2 + 1]
                
                # Ráfagas
                if 'Ráfaga' in linea_actual or 'ráfaga' in linea_actual:
                    rafagas = re.findall(r'(\d+)\s*km/h', linea_actual)
                    if len(rafagas) >= 2:
                        if idx_dia * 2 < len(rafagas):
                            datos['rafaga_dia'] = rafagas[idx_dia * 2]
                        if idx_dia * 2 + 1 < len(rafagas):
                            datos['rafaga_noche'] = rafagas[idx_dia * 2 + 1]
                
                # Dirección
                if 'Dirección' in linea_actual:
                    # Separar por espacios y tomar elementos
                    partes = linea_actual.replace('Dirección', '').strip().split()
                    if len(partes) >= 2:
                        if idx_dia * 2 < len(partes):
                            datos['dir_dia'] = partes[idx_dia * 2]
                        if idx_dia * 2 + 1 < len(partes):
                            datos['dir_noche'] = partes[idx_dia * 2 + 1]
                
                # Presión
                if 'hPa' in linea_actual:
                    presiones = re.findall(r'(\d+)\s*hPa', linea_actual)
                    if len(presiones) >= 2:
                        if idx_dia * 2 < len(presiones):
                            datos['presion_dia'] = presiones[idx_dia * 2]
                        if idx_dia * 2 + 1 < len(presiones):
                            datos['presion_noche'] = presiones[idx_dia * 2 + 1]
                
                # Cielo (condiciones)
                if 'Cielo' in linea_actual:
                    # Tomar descripción general
                    if 'cielo_dia' not in datos:
                        datos['cielo_dia'] = linea_actual.replace('Cielo', '').strip()
                    elif 'cielo_noche' not in datos:
                        datos['cielo_noche'] = linea_actual.replace('Cielo', '').strip()
    
    return datos

# ============================================================================
# SMN - DATOS HORARIOS DE CHAPELCO
# ============================================================================

def obtener_datos_smn_horarios():
    """Obtiene datos horarios de Chapelco del SMN en formato específico"""
    
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
                
                # Leer primer archivo TXT
                with zip_file.open(txt_files[0]) as f:
                    contenido = f.read().decode('utf-8', errors='ignore')
                    
                    # Extraer datos horarios de Chapelco
                    datos_horarios = extraer_datos_horarios_smn(contenido)
                    
                    if datos_horarios:
                        return datos_horarios, True, f"✅ SMN: {len(datos_horarios)} horas de datos"
                    else:
                        return {}, False, "❌ No se encontraron datos horarios de Chapelco"
        
        except zipfile.BadZipFile:
            # Intentar como texto directo
            contenido = response.content.decode('utf-8', errors='ignore')
            datos_horarios = extraer_datos_horarios_smn(contenido)
            if datos_horarios:
                return datos_horarios, True, f"✅ SMN (texto): {len(datos_horarios)} horas"
            else:
                return {}, False, "❌ No es ZIP válido ni tiene datos"
    
    except Exception as e:
        return {}, False, f"❌ Error SMN: {str(e)}"

def extraer_datos_horarios_smn(contenido):
    """Extrae datos horarios en formato específico del SMN"""
    
    datos = {}
    
    # Buscar sección de Chapelco
    if 'CHAPELCO' not in contenido.upper():
        return datos
    
    # Separar por líneas
    lineas = contenido.split('\n')
    
    current_date = None
    horas_dia = []
    
    for linea in lineas:
        linea = linea.strip()
        
        # Buscar fecha en formato 04/ENE/2026
        fecha_match = re.search(r'(\d{2})/([A-Z]{3})/(\d{4})', linea, re.IGNORECASE)
        if fecha_match:
            dia = fecha_match.group(1)
            mes_abr = fecha_match.group(2).upper()
            año = fecha_match.group(3)
            
            # Convertir mes
            meses = {
                'ENE': '01', 'FEB': '02', 'MAR': '03', 'ABR': '04',
                'MAY': '05', 'JUN': '06', 'JUL': '07', 'AGO': '08',
                'SEP': '09', 'OCT': '10', 'NOV': '11', 'DIC': '12'
            }
            
            if mes_abr in meses:
                fecha_str = f"{dia}/{mes_abr}/{año}"
                fecha_dt = datetime.strptime(f"{dia}/{mes_abr}/{año}", '%d/%b/%Y')
                
                # Nueva fecha encontrada
                if fecha_str != current_date:
                    if current_date and horas_dia:
                        datos[current_date] = {
                            'fecha': current_date,
                            'fecha_dt': datetime.strptime(current_date, '%d/%b/%Y').date(),
                            'horas': horas_dia.copy()
                        }
                    current_date = fecha_str
                    horas_dia = []
        
        # Si tenemos fecha actual, buscar horas
        if current_date and 'Hs.' in linea:
            # Formato: 04/ENE/2026 00Hs.        17.1       126 |   7         0.0
            hora_match = re.search(r'(\d{2})Hs\.\s+(-?\d+\.?\d*)\s+(\d+)\s*\|\s*(\d+)\s+(-?\d+\.?\d*)', linea)
            if hora_match:
                hora = hora_match.group(1)
                temperatura = hora_match.group(2)
                direccion_viento = hora_match.group(3)
                velocidad_viento = hora_match.group(4)
                precipitacion = hora_match.group(5)
                
                horas_dia.append({
                    'hora': f"{hora.zfill(2)}Hs.",
                    'temperatura': float(temperatura),
                    'direccion_viento': int(direccion_viento),
                    'velocidad_viento': int(velocidad_viento),
                    'precipitacion': float(precipitacion),
                    'linea_original': linea
                })
    
    # Agregar último día
    if current_date and horas_dia:
        datos[current_date] = {
            'fecha': current_date,
            'fecha_dt': datetime.strptime(current_date, '%d/%b/%Y').date(),
            'horas': horas_dia.copy()
        }
    
    return datos

# ============================================================================
# OPEN-METEO - VERSIÓN SIMPLIFICADA Y FUNCIONAL
# ============================================================================

def obtener_datos_openmeteo_simple():
    """Obtiene datos simples de Open-Meteo (sin error 400)"""
    
    try:
        # URL CORREGIDA - sin forecast_days cuando usamos start_date/end_date
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude=-40.1579&longitude=-71.3534&"
            f"hourly=temperature_2m,relativehumidity_2m,precipitation,"
            f"weathercode,windspeed_10m,winddirection_10m&"
            f"daily=weathercode,temperature_2m_max,temperature_2m_min,"
            f"precipitation_sum,windspeed_10m_max,windgusts_10m_max&"
            f"timezone=America%2FArgentina%2FBuenos_Aires&"
            f"past_days=1&forecast_days=3"  # ¡CORREGIDO! forecast_days SOLO
        )
        
        st.write(f"🔗 URL Open-Meteo (corregida):")
        st.code(url)
        
        response = requests.get(url, timeout=20)
        
        st.write(f"📡 Status Open-Meteo: {response.status_code}")
        
        if response.status_code != 200:
            error_text = response.text[:200] if response.text else "Sin mensaje de error"
            st.error(f"❌ Error {response.status_code}: {error_text}")
            return {}, False, f"❌ Error API: {response.status_code}"
        
        datos_raw = response.json()
        
        # Verificar estructura básica
        if 'hourly' not in datos_raw or 'daily' not in datos_raw:
            st.warning("⚠️ Estructura de datos incompleta")
            return {}, False, "❌ Datos incompletos"
        
        return datos_raw, True, "✅ Open-Meteo: Datos obtenidos correctamente"
    
    except requests.exceptions.Timeout:
        st.error("⏱️ Timeout al conectar con Open-Meteo")
        return {}, False, "❌ Timeout"
    except requests.exceptions.ConnectionError:
        st.error("🔌 Error de conexión con Open-Meteo")
        return {}, False, "❌ Error de conexión"
    except Exception as e:
        st.error(f"❌ Error Open-Meteo: {str(e)}")
        return {}, False, f"❌ Error: {str(e)}"

# ============================================================================
# INTERFAZ PRINCIPAL
# ============================================================================

def main():
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📄 Extraer AIC", type="primary", use_container_width=True):
            st.session_state['fuente'] = 'AIC'
    
    with col2:
        if st.button("📊 Extraer SMN", type="primary", use_container_width=True):
            st.session_state['fuente'] = 'SMN'
    
    with col3:
        if st.button("🛰️ Extraer Open-Meteo", type="primary", use_container_width=True):
            st.session_state['fuente'] = 'OPENMETEO'
    
    st.markdown("---")
    
    if 'fuente' in st.session_state:
        fuente = st.session_state['fuente']
        
        with st.spinner(f"🔍 Extrayendo datos de {fuente}..."):
            
            if fuente == 'AIC':
                datos, estado, mensaje = obtener_datos_aic_formateados()
                
                if estado and datos:
                    st.success(f"✅ {mensaje}")
                    mostrar_datos_aic(datos)
                else:
                    st.error(f"❌ {mensaje}")
            
            elif fuente == 'SMN':
                datos, estado, mensaje = obtener_datos_smn_horarios()
                
                if estado and datos:
                    st.success(f"✅ {mensaje}")
                    mostrar_datos_smn(datos)
                else:
                    st.error(f"❌ {mensaje}")
            
            elif fuente == 'OPENMETEO':
                datos, estado, mensaje = obtener_datos_openmeteo_simple()
                
                if estado and datos:
                    st.success(f"✅ {mensaje}")
                    mostrar_datos_openmeteo(datos)
                else:
                    st.error(f"❌ {mensaje}")

def mostrar_datos_aic(datos):
    """Muestra datos de AIC en formato específico"""
    
    st.subheader("📄 Datos AIC Formateados")
    
    for dia in datos:
        st.markdown(f'<div class="day-header">📅 {dia["fecha"]}</div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**DÍA:**")
            st.markdown(f"""
            <div class="data-card card-aic">
            <strong>Cielo:</strong> {dia['cielo_dia']}<br>
            <strong>Temperatura:</strong> {dia['temp_max']}°C<br>
            <strong>Viento:</strong> {dia['viento_dia']} km/h<br>
            <strong>Ráfaga:</strong> {dia['rafaga_dia']} km/h<br>
            <strong>Dirección:</strong> {dia['direccion_dia']}<br>
            <strong>Presión:</strong> {dia['presion_dia']} hPa
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("**NOCHE:**")
            st.markdown(f"""
            <div class="data-card card-aic">
            <strong>Cielo:</strong> {dia['cielo_noche']}<br>
            <strong>Temperatura:</strong> {dia['temp_min']}°C<br>
            <strong>Viento:</strong> {dia['viento_noche']} km/h<br>
            <strong>Ráfaga:</strong> {dia['rafaga_noche']} km/h<br>
            <strong>Dirección:</strong> {dia['direccion_noche']}<br>
            <strong>Presión:</strong> {dia['presion_noche']} hPa
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")

def mostrar_datos_smn(datos):
    """Muestra datos horarios del SMN"""
    
    st.subheader("📊 Datos Horarios SMN - Chapelco")
    
    for fecha_str, info_dia in datos.items():
        st.markdown(f'<div class="day-header">📅 {fecha_str}</div>', unsafe_allow_html=True)
        
        # Mostrar cada hora
        for hora in info_dia['horas']:
            st.markdown(f"""
            <div class="hour-row">
            <strong>{hora['hora']}</strong> | 
            Temp: <strong>{hora['temperatura']}°C</strong> | 
            Viento: {hora['velocidad_viento']} km/h ({hora['direccion_viento']}°) | 
            Precip: {hora['precipitacion']} mm
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")

def mostrar_datos_openmeteo(datos):
    """Muestra datos crudos de Open-Meteo"""
    
    st.subheader("🛰️ Datos Open-Meteo (Crudos)")
    
    # Mostrar estructura básica
    if 'hourly' in datos:
        st.write("**📈 Datos Horarios:**")
        
        if 'time' in datos['hourly']:
            horas = len(datos['hourly']['time'])
            st.write(f"- {horas} horas disponibles")
            
            # Mostrar algunas horas como ejemplo
            st.write("**Primeras 5 horas:**")
            for i in range(min(5, horas)):
                hora_data = {}
                for key in datos['hourly'].keys():
                    if key != 'time' and i < len(datos['hourly'][key]):
                        hora_data[key] = datos['hourly'][key][i]
                
                hora_str = datos['hourly']['time'][i]
                st.write(f"**{hora_str}:** {hora_data}")
    
    if 'daily' in datos:
        st.write("**📅 Datos Diarios:**")
        
        if 'time' in datos['daily']:
            dias = len(datos['daily']['time'])
            st.write(f"- {dias} días disponibles")
            
            # Mostrar datos diarios
            for i in range(min(3, dias)):
                dia_data = {}
                for key in datos['daily'].keys():
                    if key != 'time' and i < len(datos['daily'][key]):
                        dia_data[key] = datos['daily'][key][i]
                
                fecha_str = datos['daily']['time'][i]
                st.write(f"**{fecha_str}:**")
                st.json(dia_data, expanded=False)
    
    # Mostrar datos crudos completos si se solicita
    if mostrar_crudo:
        st.write("**📋 Datos Crudos Completos:**")
        st.json(datos, expanded=False)

# Ejecutar aplicación
if __name__ == "__main__":
    main()

# Footer
st.markdown("---")
st.caption("""
**Sistema de Extracción Individual V1.0** | 
AIC: Formato día/noche específico | 
SMN: Datos horarios Chapelco | 
Open-Meteo: Conexión funcional (sin error 400)
""")
