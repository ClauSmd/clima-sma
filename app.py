import streamlit as st
import requests
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

# Configuración de página
st.set_page_config(page_title="Extracción Meteorológica SMA", page_icon="📡", layout="wide")

# CSS personalizado
st.markdown("""
<style>
    .data-table {
        background-color: #1a1a1a;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
    }
    .table-header {
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
    .success-box {
        background-color: #1a3c1a;
        padding: 15px;
        border-radius: 8px;
        border-left: 5px solid #4CAF50;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# Título principal
st.title("📡 Extracción Meteorológica - Formatos Específicos")
st.markdown("**AIC (tabla) + SMN (horarios) + Open-Meteo (crudo)**")
st.markdown("---")

# ============================================================================
# AIC - FORMATO TABLA EXACTO
# ============================================================================

def obtener_datos_aic_tabla():
    """Obtiene datos de AIC y los formatea en tabla exacta"""
    
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
                        tabla = parsear_aic_a_tabla(texto)
                        if tabla:
                            return tabla, True, f"✅ AIC: Tabla con {len(tabla)} filas"
            
            time.sleep(1)
        except Exception as e:
            st.error(f"Error AIC: {str(e)}")
            continue
    
    return [], False, "❌ No se pudo obtener el PDF de AIC"

def parsear_aic_a_tabla(texto):
    """Convierte el texto del PDF de AIC a tabla exacta"""
    
    tabla = []
    
    try:
        lineas = [line.strip() for line in texto.split('\n') if line.strip()]
        
        # Buscar línea con fechas
        fechas = []
        for linea in lineas[:10]:
            # Buscar formato DD-MM-YYYY
            matches = re.findall(r'\d{2}-\d{2}-\d{4}', linea)
            if matches:
                fechas = matches
                break
        
        if not fechas:
            return []
        
        # Buscar períodos (Día/Noche)
        periodos_line = None
        for i, linea in enumerate(lineas):
            if 'Día' in linea and 'Noche' in linea:
                periodos_line = i
                break
        
        if periodos_line is None:
            return []
        
        # Buscar líneas de datos
        lineas_datos = {}
        
        # Temperaturas (buscar línea con ºC)
        for i, linea in enumerate(lineas):
            if 'ºC' in linea or '°C' in linea:
                temps = re.findall(r'(-?\d+)\s*[ºC°C]', linea)
                if temps:
                    lineas_datos['temperaturas'] = {'idx': i, 'valores': temps}
        
        # Vientos (buscar línea con km/h y sin "Dirección")
        for i, linea in enumerate(lineas):
            if 'km/h' in linea and 'Dirección' not in linea:
                vientos = re.findall(r'(\d+)\s*km/h', linea)
                if vientos:
                    lineas_datos['vientos'] = {'idx': i, 'valores': vientos}
        
        # Ráfagas (buscar línea con "Ráfaga" o "ráfaga")
        for i, linea in enumerate(lineas):
            if 'Ráfaga' in linea or 'ráfaga' in linea:
                rafagas = re.findall(r'(\d+)\s*km/h', linea)
                if rafagas:
                    lineas_datos['rafagas'] = {'idx': i, 'valores': rafagas}
        
        # Dirección del viento
        for i, linea in enumerate(lineas):
            if 'Dirección' in linea:
                # Limpiar y separar
                partes = linea.replace('Dirección', '').strip().split()
                if partes:
                    lineas_datos['direccion'] = {'idx': i, 'valores': partes}
        
        # Presión
        for i, linea in enumerate(lineas):
            if 'hPa' in linea:
                presiones = re.findall(r'(\d+)\s*hPa', linea)
                if presiones:
                    lineas_datos['presion'] = {'idx': i, 'valores': presiones}
        
        # Condiciones del cielo (buscar líneas con descripciones)
        condiciones_lineas = []
        palabras_clave = ['Mayormente', 'Despejado', 'Nublado', 'Tormenta', 'Lluvia', 
                         'Inestable', 'Parcialmente', 'Cubierto', 'Posibles', 'Eléctricas']
        
        for i, linea in enumerate(lineas[3:15]):  # Buscar en primeras líneas después del título
            for palabra in palabras_clave:
                if palabra in linea:
                    # Limpiar línea
                    clean_line = linea
                    # Quitar números y unidades
                    clean_line = re.sub(r'\d+[ºC°C]', '', clean_line)
                    clean_line = re.sub(r'\d+\s*km/h', '', clean_line)
                    clean_line = re.sub(r'\d+\s*hPa', '', clean_line)
                    clean_line = clean_line.strip()
                    
                    if clean_line and len(clean_line) > 3:
                        condiciones_lineas.append(clean_line)
                    break
        
        # Crear tabla
        for i, fecha in enumerate(fechas[:5]):  # Máximo 5 días
            # DÍA
            if len(condiciones_lineas) > i*2:
                cielo_dia = condiciones_lineas[i*2]
            else:
                cielo_dia = "No disponible"
            
            # NOCHE
            if len(condiciones_lineas) > i*2 + 1:
                cielo_noche = condiciones_lineas[i*2 + 1]
            else:
                cielo_noche = "No disponible"
            
            # Extraer valores para este día
            temp_dia = extraer_valor(lineas_datos, 'temperaturas', i*2)
            temp_noche = extraer_valor(lineas_datos, 'temperaturas', i*2 + 1)
            viento_dia = extraer_valor(lineas_datos, 'vientos', i*2)
            viento_noche = extraer_valor(lineas_datos, 'vientos', i*2 + 1)
            rafaga_dia = extraer_valor(lineas_datos, 'rafagas', i*2)
            rafaga_noche = extraer_valor(lineas_datos, 'rafagas', i*2 + 1)
            dir_dia = extraer_valor(lineas_datos, 'direccion', i*2)
            dir_noche = extraer_valor(lineas_datos, 'direccion', i*2 + 1)
            presion_dia = extraer_valor(lineas_datos, 'presion', i*2)
            presion_noche = extraer_valor(lineas_datos, 'presion', i*2 + 1)
            
            # Agregar filas a la tabla
            tabla.append({
                'Fecha': fecha,
                'Momento': 'Día',
                'Cielo': limpiar_texto_cielo(cielo_dia),
                'Temperatura': f"{temp_dia} ºC" if temp_dia != 'N/D' else 'N/D',
                'Viento': f"{viento_dia} km/h" if viento_dia != 'N/D' else 'N/D',
                'Ráfagas': f"{rafaga_dia} km/h" if rafaga_dia != 'N/D' else 'N/D',
                'Presión': f"{presion_dia} hPa" if presion_dia != 'N/D' else 'N/D'
            })
            
            tabla.append({
                'Fecha': fecha,
                'Momento': 'Noche',
                'Cielo': limpiar_texto_cielo(cielo_noche),
                'Temperatura': f"{temp_noche} ºC" if temp_noche != 'N/D' else 'N/D',
                'Viento': f"{viento_noche} km/h" if viento_noche != 'N/D' else 'N/D',
                'Ráfagas': f"{rafaga_noche} km/h" if rafaga_noche != 'N/D' else 'N/D',
                'Presión': f"{presion_noche} hPa" if presion_noche != 'N/D' else 'N/D'
            })
        
        return tabla
        
    except Exception as e:
        st.error(f"Error parseando AIC: {str(e)}")
        return []

def extraer_valor(lineas_datos, clave, idx):
    """Extrae un valor específico de los datos parseados"""
    if clave in lineas_datos:
        valores = lineas_datos[clave]['valores']
        if idx < len(valores):
            return valores[idx]
    return 'N/D'

def limpiar_texto_cielo(texto):
    """Limpia el texto del cielo para que sea legible"""
    if texto == 'No disponible':
        return texto
    
    # Quitar puntos y comas al final
    texto = texto.strip('., ')
    
    # Capitalizar primera letra
    if texto:
        texto = texto[0].upper() + texto[1:]
    
    return texto

# ============================================================================
# SMN - DATOS HORARIOS (YA ESTÁN PERFECTOS)
# ============================================================================

def obtener_datos_smn_horarios():
    """Obtiene datos horarios de Chapelco del SMN"""
    
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
                    
                    # Extraer datos horarios
                    datos_horarios = extraer_datos_horarios_smn(contenido)
                    
                    if datos_horarios:
                        return datos_horarios, True, f"✅ SMN: {len(datos_horarios)} registros horarios"
                    else:
                        return {}, False, "❌ No se encontraron datos horarios"
        
        except zipfile.BadZipFile:
            # Intentar como texto directo
            contenido = response.content.decode('utf-8', errors='ignore')
            datos_horarios = extraer_datos_horarios_smn(contenido)
            if datos_horarios:
                return datos_horarios, True, f"✅ SMN (texto): {len(datos_horarios)} registros"
            else:
                return {}, False, "❌ No es ZIP válido"
    
    except Exception as e:
        return {}, False, f"❌ Error SMN: {str(e)}"

def extraer_datos_horarios_smn(contenido):
    """Extrae datos horarios del contenido del SMN"""
    
    datos = []
    
    # Buscar sección de Chapelco
    if 'CHAPELCO_AERO' not in contenido:
        return datos
    
    # Separar por líneas
    lineas = contenido.split('\n')
    
    # Buscar desde CHAPELCO_AERO
    inicio = -1
    for i, linea in enumerate(lineas):
        if 'CHAPELCO_AERO' in linea:
            inicio = i
            break
    
    if inicio == -1:
        return datos
    
    # Buscar líneas de datos (después de los separadores)
    for i in range(inicio + 1, min(inicio + 100, len(lineas))):
        linea = lineas[i].strip()
        
        # Buscar formato: 04/ENE/2026 00Hs.        17.1       126 |   7         0.0
        match = re.match(r'(\d{2}/[A-Z]{3}/\d{4})\s+(\d{2})Hs\.\s+(-?\d+\.?\d*)\s+(\d+)\s*\|\s*(\d+)\s+(-?\d+\.?\d*)', linea)
        
        if match:
            fecha = match.group(1)
            hora = match.group(2)
            temperatura = float(match.group(3))
            direccion = int(match.group(4))
            velocidad = int(match.group(5))
            precipitacion = float(match.group(6))
            
            datos.append({
                'Fecha_Hora': f"{fecha} {hora}Hs.",
                'Fecha': fecha,
                'Hora': f"{hora}Hs.",
                'Temperatura': temperatura,
                'Direccion_Viento': direccion,
                'Velocidad_Viento': velocidad,
                'Precipitacion': precipitacion,
                'Linea_Original': linea
            })
    
    return datos

# ============================================================================
# OPEN-METEO - VERSIÓN FUNCIONAL
# ============================================================================

def obtener_datos_openmeteo():
    """Obtiene datos simples de Open-Meteo"""
    
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude=-40.1579&longitude=-71.3534&"
            f"hourly=temperature_2m,relativehumidity_2m,precipitation,"
            f"weathercode,windspeed_10m,winddirection_10m&"
            f"daily=weathercode,temperature_2m_max,temperature_2m_min,"
            f"precipitation_sum,windspeed_10m_max,windgusts_10m_max&"
            f"timezone=America%2FArgentina%2FBuenos_Aires&"
            f"forecast_days=3"
        )
        
        response = requests.get(url, timeout=20)
        
        if response.status_code != 200:
            return {}, False, f"❌ Error API: {response.status_code}"
        
        datos_raw = response.json()
        
        # Verificar estructura básica
        if 'hourly' not in datos_raw or 'daily' not in datos_raw:
            return {}, False, "❌ Datos incompletos"
        
        return datos_raw, True, "✅ Open-Meteo: Datos obtenidos"
    
    except Exception as e:
        return {}, False, f"❌ Error: {str(e)}"

# ============================================================================
# INTERFAZ PRINCIPAL
# ============================================================================

def main():
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 Extraer AIC (Tabla)", type="primary", use_container_width=True):
            st.session_state['fuente'] = 'AIC'
            st.session_state['mostrar'] = True
    
    with col2:
        if st.button("⏰ Extraer SMN (Horarios)", type="primary", use_container_width=True):
            st.session_state['fuente'] = 'SMN'
            st.session_state['mostrar'] = True
    
    with col3:
        if st.button("🛰️ Extraer Open-Meteo", type="primary", use_container_width=True):
            st.session_state['fuente'] = 'OPENMETEO'
            st.session_state['mostrar'] = True
    
    st.markdown("---")
    
    if 'fuente' in st.session_state and st.session_state.get('mostrar', False):
        fuente = st.session_state['fuente']
        
        with st.spinner(f"🔍 Extrayendo datos de {fuente}..."):
            
            if fuente == 'AIC':
                datos, estado, mensaje = obtener_datos_aic_tabla()
                
                if estado and datos:
                    st.markdown(f'<div class="success-box"><strong>{mensaje}</strong></div>', unsafe_allow_html=True)
                    mostrar_tabla_aic(datos)
                else:
                    st.error(f"❌ {mensaje}")
            
            elif fuente == 'SMN':
                datos, estado, mensaje = obtener_datos_smn_horarios()
                
                if estado and datos:
                    st.markdown(f'<div class="success-box"><strong>{mensaje}</strong></div>', unsafe_allow_html=True)
                    mostrar_tabla_smn(datos)
                else:
                    st.error(f"❌ {mensaje}")
            
            elif fuente == 'OPENMETEO':
                datos, estado, mensaje = obtener_datos_openmeteo()
                
                if estado and datos:
                    st.markdown(f'<div class="success-box"><strong>{mensaje}</strong></div>', unsafe_allow_html=True)
                    mostrar_datos_openmeteo(datos)
                else:
                    st.error(f"❌ {mensaje}")

def mostrar_tabla_aic(tabla):
    """Muestra la tabla de AIC en formato exacto"""
    
    st.subheader("📋 Tabla AIC - Pronóstico por Día y Noche")
    
    if not tabla:
        st.warning("No hay datos para mostrar")
        return
    
    # Convertir a DataFrame para mejor visualización
    df = pd.DataFrame(tabla)
    
    # Mostrar tabla con estilo
    st.markdown('<div class="data-table">', unsafe_allow_html=True)
    
    # Crear HTML table manualmente para más control
    html_table = """
    <table style="width:100%; border-collapse: collapse; color: white;">
        <thead>
            <tr style="background-color: #2d2d2d;">
                <th style="padding: 10px; border: 1px solid #444; text-align: left;">Fecha</th>
                <th style="padding: 10px; border: 1px solid #444; text-align: left;">Momento</th>
                <th style="padding: 10px; border: 1px solid #444; text-align: left;">Cielo</th>
                <th style="padding: 10px; border: 1px solid #444; text-align: left;">Temperatura</th>
                <th style="padding: 10px; border: 1px solid #444; text-align: left;">Viento</th>
                <th style="padding: 10px; border: 1px solid #444; text-align: left;">Ráfagas</th>
                <th style="padding: 10px; border: 1px solid #444; text-align: left;">Presión</th>
            </tr>
        </thead>
        <tbody>
    """
    
    for i, fila in enumerate(tabla):
        # Alternar colores de fila
        bg_color = "#1a1a1a" if i % 2 == 0 else "#252525"
        
        html_table += f"""
        <tr style="background-color: {bg_color};">
            <td style="padding: 8px; border: 1px solid #444;">{fila['Fecha']}</td>
            <td style="padding: 8px; border: 1px solid #444;">{fila['Momento']}</td>
            <td style="padding: 8px; border: 1px solid #444;">{fila['Cielo']}</td>
            <td style="padding: 8px; border: 1px solid #444;">{fila['Temperatura']}</td>
            <td style="padding: 8px; border: 1px solid #444;">{fila['Viento']}</td>
            <td style="padding: 8px; border: 1px solid #444;">{fila['Ráfagas']}</td>
            <td style="padding: 8px; border: 1px solid #444;">{fila['Presión']}</td>
        </tr>
        """
    
    html_table += """
        </tbody>
    </table>
    </div>
    """
    
    st.markdown(html_table, unsafe_allow_html=True)
    
    # También mostrar como DataFrame simple
    st.write("**Vista DataFrame:**")
    st.dataframe(df, use_container_width=True, hide_index=True)

def mostrar_tabla_smn(datos):
    """Muestra los datos horarios del SMN"""
    
    st.subheader("⏰ Datos Horarios SMN - Chapelco Aero")
    
    if not datos:
        st.warning("No hay datos para mostrar")
        return
    
    # Agrupar por fecha
    fechas = {}
    for registro in datos:
        fecha = registro['Fecha']
        if fecha not in fechas:
            fechas[fecha] = []
        fechas[fecha].append(registro)
    
    # Mostrar por fecha
    for fecha, registros in fechas.items():
        st.markdown(f'<div class="table-header">📅 {fecha}</div>', unsafe_allow_html=True)
        
        # Mostrar cada hora
        for registro in registros:
            st.markdown(f"""
            <div class="hour-row">
            <strong>{registro['Hora']}</strong> | 
            Temp: <strong>{registro['Temperatura']}°C</strong> | 
            Viento: {registro['Velocidad_Viento']} km/h ({registro['Direccion_Viento']}°) | 
            Precip: {registro['Precipitacion']} mm
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")

def mostrar_datos_openmeteo(datos):
    """Muestra datos de Open-Meteo"""
    
    st.subheader("🛰️ Datos Open-Meteo")
    
    # Datos diarios
    if 'daily' in datos and 'time' in datos['daily']:
        st.write("**📅 Pronóstico Diario:**")
        
        daily_data = []
        for i in range(min(3, len(datos['daily']['time']))):
            daily_data.append({
                'Fecha': datos['daily']['time'][i],
                'Temp Máx': f"{datos['daily']['temperature_2m_max'][i]:.1f}°C" if i < len(datos['daily']['temperature_2m_max']) else 'N/D',
                'Temp Mín': f"{datos['daily']['temperature_2m_min'][i]:.1f}°C" if i < len(datos['daily']['temperature_2m_min']) else 'N/D',
                'Precipitación': f"{datos['daily']['precipitation_sum'][i]:.1f} mm" if i < len(datos['daily']['precipitation_sum']) else 'N/D',
                'Viento Máx': f"{datos['daily']['windspeed_10m_max'][i]:.1f} km/h" if i < len(datos['daily']['windspeed_10m_max']) else 'N/D'
            })
        
        st.table(daily_data)
    
    # Datos horarios (resumen)
    if 'hourly' in datos and 'time' in datos['hourly']:
        st.write("**📈 Datos Horarios (primeras 12 horas):**")
        
        hourly_data = []
        for i in range(min(12, len(datos['hourly']['time']))):
            hourly_data.append({
                'Hora': datos['hourly']['time'][i],
                'Temp': f"{datos['hourly']['temperature_2m'][i]:.1f}°C" if i < len(datos['hourly']['temperature_2m']) else 'N/D',
                'Humedad': f"{datos['hourly']['relativehumidity_2m'][i]:.0f}%" if i < len(datos['hourly']['relativehumidity_2m']) else 'N/D',
                'Precip': f"{datos['hourly']['precipitation'][i]:.1f} mm" if i < len(datos['hourly']['precipitation']) else 'N/D',
                'Viento': f"{datos['hourly']['windspeed_10m'][i]:.1f} km/h" if i < len(datos['hourly']['windspeed_10m']) else 'N/D'
            })
        
        st.table(hourly_data)

# Ejecutar aplicación
if __name__ == "__main__":
    main()

# Footer
st.markdown("---")
st.caption("""
**Sistema de Extracción V2.0** | 
AIC: Tabla formato exacto (Fecha+Momento) | 
SMN: Datos horarios Chapelco | 
Open-Meteo: Conexión estable
""")
