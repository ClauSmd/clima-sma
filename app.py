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

# Título principal
st.title("📡 Extracción Meteorológica - Formatos Específicos")
st.markdown("**AIC (2 filas/día) + SMN (sección Chapelco) + Open-Meteo**")
st.markdown("---")

# ============================================================================
# AIC - SOLO 2 FILAS POR DÍA (DÍA Y NOCHE)
# ============================================================================

def obtener_datos_aic_tabla_correcta():
    """Obtiene datos de AIC con formato: 2 filas por día (Día y Noche)"""
    
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
                        tabla = parsear_aic_2_filas_por_dia(texto)
                        if tabla and len(tabla) > 0:
                            return tabla, True, f"✅ AIC: {len(tabla)} filas ({len(tabla)//2} días)"
            
            time.sleep(1)
        except Exception as e:
            continue
    
    return [], False, "❌ No se pudo obtener el PDF de AIC"

def parsear_aic_2_filas_por_dia(texto):
    """Parsea AIC para devolver solo 2 filas por día: Día y Noche"""
    
    tabla = []
    
    try:
        # Limpiar y separar texto
        lineas = [line.strip() for line in texto.split('\n') if line.strip()]
        
        # DEBUG: Mostrar primeras líneas
        st.write("🔍 **DEBUG AIC - Primeras 15 líneas:**")
        for i, linea in enumerate(lineas[:15]):
            st.write(f"{i}: {linea}")
        
        # 1. BUSCAR FECHAS (formato DD-MM-YYYY)
        fechas = []
        for linea in lineas[:10]:  # Buscar en primeras líneas
            matches = re.findall(r'\d{2}-\d{2}-\d{4}', linea)
            if matches:
                fechas = matches
                st.write(f"📅 Fechas encontradas: {fechas}")
                break
        
        if not fechas:
            st.warning("No se encontraron fechas en formato DD-MM-YYYY")
            return []
        
        # 2. BUSCAR LÍNEA DE PERÍODOS (Día/Noche)
        periodos_line_idx = -1
        for i, linea in enumerate(lineas):
            if 'Día' in linea and 'Noche' in linea:
                periodos_line_idx = i
                st.write(f"📊 Línea de períodos encontrada (línea {i}): {linea}")
                break
        
        if periodos_line_idx == -1:
            st.warning("No se encontró línea de períodos (Día/Noche)")
            return []
        
        # 3. BUSCAR DATOS EN LAS LÍNEAS SIGUIENTES
        # Temperaturas (buscar línea con ºC después de períodos)
        temperaturas = []
        for i in range(periodos_line_idx + 1, min(periodos_line_idx + 10, len(lineas))):
            if 'ºC' in lineas[i] or '°C' in lineas[i]:
                temps = re.findall(r'(-?\d+)\s*[ºC°C]', lineas[i])
                if temps:
                    temperaturas = temps
                    st.write(f"🌡️ Temperaturas encontradas: {temperaturas}")
                    break
        
        # Viento (km/h)
        vientos = []
        for i in range(periodos_line_idx + 1, min(periodos_line_idx + 15, len(lineas))):
            if 'km/h' in lineas[i] and 'Dirección' not in lineas[i] and 'Ráfaga' not in lineas[i]:
                vientos_temp = re.findall(r'(\d+)\s*km/h', lineas[i])
                if vientos_temp:
                    vientos = vientos_temp
                    st.write(f"💨 Vientos encontrados: {vientos}")
                    break
        
        # Ráfagas
        rafagas = []
        for i in range(periodos_line_idx + 1, min(periodos_line_idx + 15, len(lineas))):
            if 'Ráfaga' in lineas[i] or 'ráfaga' in lineas[i]:
                rafagas_temp = re.findall(r'(\d+)\s*km/h', lineas[i])
                if rafagas_temp:
                    rafagas = rafagas_temp
                    st.write(f"🌪️ Ráfagas encontradas: {rafagas}")
                    break
        
        # Dirección del viento
        direcciones = []
        for i in range(periodos_line_idx + 1, min(periodos_line_idx + 15, len(lineas))):
            if 'Dirección' in lineas[i]:
                partes = lineas[i].replace('Dirección', '').strip().split()
                if partes:
                    direcciones = partes
                    st.write(f"🧭 Direcciones encontradas: {direcciones}")
                    break
        
        # Presión
        presiones = []
        for i in range(periodos_line_idx + 1, min(periodos_line_idx + 15, len(lineas))):
            if 'hPa' in lineas[i]:
                presiones_temp = re.findall(r'(\d+)\s*hPa', lineas[i])
                if presiones_temp:
                    presiones = presiones_temp
                    st.write(f"📊 Presiones encontradas: {presiones}")
                    break
        
        # 4. BUSCAR CONDICIONES DEL CIELO (líneas después de "Cielo")
        condiciones = []
        for i, linea in enumerate(lineas):
            if 'Cielo' in linea:
                # Tomar las siguientes 4 líneas como condiciones
                for j in range(i+1, min(i+5, len(lineas))):
                    if lineas[j] and not re.search(r'\d', lineas[j]):  # Línea sin números
                        cond_limpia = lineas[j].strip('., ')
                        if cond_limpia and len(cond_limpia) > 2:
                            condiciones.append(cond_limpia)
                break
        
        st.write(f"☁️ Condiciones encontradas: {condiciones}")
        
        # 5. CREAR TABLA CON 2 FILAS POR DÍA
        for i, fecha in enumerate(fechas[:3]):  # Máximo 3 días
            # Calcular índices
            idx_dia = i * 2
            idx_noche = i * 2 + 1
            
            # FILA DÍA
            cielo_dia = condiciones[idx_dia] if idx_dia < len(condiciones) else "No disponible"
            temp_dia = temperaturas[idx_dia] if idx_dia < len(temperaturas) else "N/D"
            viento_dia = vientos[idx_dia] if idx_dia < len(vientos) else "N/D"
            rafaga_dia = rafagas[idx_dia] if idx_dia < len(rafagas) else "N/D"
            dir_dia = direcciones[idx_dia] if idx_dia < len(direcciones) else "N/D"
            presion_dia = presiones[idx_dia] if idx_dia < len(presiones) else "N/D"
            
            # FILA NOCHE
            cielo_noche = condiciones[idx_noche] if idx_noche < len(condiciones) else "No disponible"
            temp_noche = temperaturas[idx_noche] if idx_noche < len(temperaturas) else "N/D"
            viento_noche = vientos[idx_noche] if idx_noche < len(vientos) else "N/D"
            rafaga_noche = rafagas[idx_noche] if idx_noche < len(rafagas) else "N/D"
            dir_noche = direcciones[idx_noche] if idx_noche < len(direcciones) else "N/D"
            presion_noche = presiones[idx_noche] if idx_noche < len(presiones) else "N/D"
            
            # Agregar a tabla
            tabla.append({
                'Fecha': fecha,
                'Momento': 'Día',
                'Cielo': cielo_dia,
                'Temperatura': f"{temp_dia} ºC",
                'Viento': f"{viento_dia} km/h",
                'Ráfagas': f"{rafaga_dia} km/h",
                'Presión': f"{presion_dia} hPa"
            })
            
            tabla.append({
                'Fecha': fecha,
                'Momento': 'Noche',
                'Cielo': cielo_noche,
                'Temperatura': f"{temp_noche} ºC",
                'Viento': f"{viento_noche} km/h",
                'Ráfagas': f"{rafaga_noche} km/h",
                'Presión': f"{presion_noche} hPa"
            })
        
        return tabla
        
    except Exception as e:
        st.error(f"❌ Error parseando AIC: {str(e)}")
        return []

# ============================================================================
# SMN - EXTRACCIÓN EXACTA DE LA SECCIÓN CHAPELCO
# ============================================================================

def obtener_datos_smn_exactos():
    """Extrae EXACTAMENTE la sección de Chapelco del archivo SMN"""
    
    url = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=pron5d"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/zip, */*',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=40, verify=False)
        
        if response.status_code != 200:
            return None, False, f"❌ Error HTTP {response.status_code}"
        
        # Intentar como ZIP
        try:
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                txt_files = [f for f in zip_file.namelist() if f.endswith('.txt')]
                
                if not txt_files:
                    return None, False, "❌ No hay archivos TXT"
                
                # Leer TODO el contenido del primer archivo
                with zip_file.open(txt_files[0]) as f:
                    contenido_completo = f.read().decode('utf-8', errors='ignore')
                    
                    # Extraer sección EXACTA de Chapelco
                    seccion_chapelco = extraer_seccion_chapelco_exacta(contenido_completo)
                    
                    if seccion_chapelco:
                        return seccion_chapelco, True, f"✅ SMN: Sección Chapelco encontrada ({len(seccion_chapelco)} líneas)"
                    else:
                        return None, False, "❌ No se encontró la sección CHAPELCO_AERO"
        
        except zipfile.BadZipFile:
            # Intentar como texto directo
            contenido = response.content.decode('utf-8', errors='ignore')
            seccion_chapelco = extraer_seccion_chapelco_exacta(contenido)
            if seccion_chapelco:
                return seccion_chapelco, True, f"✅ SMN (texto): Sección encontrada"
            else:
                return None, False, "❌ No es ZIP válido ni tiene sección Chapelco"
    
    except Exception as e:
        return None, False, f"❌ Error SMN: {str(e)}"

def extraer_seccion_chapelco_exacta(contenido):
    """Extrae EXACTAMENTE la sección de Chapelco como está en el archivo"""
    
    # Buscar "CHAPELCO_AERO" en el contenido
    contenido_upper = contenido.upper()
    
    if 'CHAPELCO_AERO' not in contenido_upper:
        return None
    
    # Encontrar posición exacta
    idx_inicio = contenido_upper.find('CHAPELCO_AERO')
    
    if idx_inicio == -1:
        return None
    
    # Buscar desde el inicio hasta el próximo código de estación o fin de sección
    # Los códigos de estación suelen ser como "XXXX_XXXX" o "XXXXX"
    seccion = contenido[idx_inicio:]
    
    # Buscar próxima estación (patrón: línea con solo mayúsculas y guiones/barras bajas)
    lines = seccion.split('\n')
    seccion_final = []
    
    # Tomar desde CHAPELCO_AERO hasta encontrar línea vacía o próxima estación
    for i, line in enumerate(lines):
        if i == 0:
            seccion_final.append(line.strip())
            continue
        
        # Si encontramos otra estación (todo mayúsculas con _) o línea de separación
        if line.strip() and '=====' in line:
            break
        if re.match(r'^[A-Z]{4,}_[A-Z]{4,}$', line.strip()):
            break
        if re.match(r'^[A-Z]{4,}$', line.strip()) and 'CHAPELCO' not in line.upper():
            break
        
        seccion_final.append(line.rstrip())  # Mantener espacios al final
    
    return '\n'.join(seccion_final)

# ============================================================================
# OPEN-METEO - YA FUNCIONA
# ============================================================================

def obtener_datos_openmeteo():
    """Obtiene datos de Open-Meteo"""
    
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
        
        return datos_raw, True, "✅ Open-Meteo: Datos obtenidos"
    
    except Exception as e:
        return {}, False, f"❌ Error: {str(e)}"

# ============================================================================
# INTERFAZ PRINCIPAL
# ============================================================================

def main():
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 Extraer AIC", type="primary", use_container_width=True):
            st.session_state['fuente'] = 'AIC'
    
    with col2:
        if st.button("⏰ Extraer SMN", type="primary", use_container_width=True):
            st.session_state['fuente'] = 'SMN'
    
    with col3:
        if st.button("🛰️ Extraer Open-Meteo", type="primary", use_container_width=True):
            st.session_state['fuente'] = 'OPENMETEO'
    
    st.markdown("---")
    
    if 'fuente' in st.session_state:
        fuente = st.session_state['fuente']
        
        with st.spinner(f"🔍 Extrayendo datos de {fuente}..."):
            
            if fuente == 'AIC':
                datos, estado, mensaje = obtener_datos_aic_tabla_correcta()
                
                if estado and datos:
                    st.success(f"✅ {mensaje}")
                    mostrar_tabla_aic_correcta(datos)
                else:
                    st.error(f"❌ {mensaje}")
            
            elif fuente == 'SMN':
                datos, estado, mensaje = obtener_datos_smn_exactos()
                
                if estado and datos:
                    st.success(f"✅ {mensaje}")
                    mostrar_seccion_smn_exacta(datos)
                else:
                    st.error(f"❌ {mensaje}")
            
            elif fuente == 'OPENMETEO':
                datos, estado, mensaje = obtener_datos_openmeteo()
                
                if estado and datos:
                    st.success(f"✅ {mensaje}")
                    mostrar_datos_openmeteo(datos)
                else:
                    st.error(f"❌ {mensaje}")

def mostrar_tabla_aic_correcta(tabla):
    """Muestra la tabla de AIC con 2 filas por día"""
    
    st.subheader("📋 Tabla AIC - Día y Noche por Fecha")
    
    if not tabla:
        st.warning("No hay datos para mostrar")
        return
    
    # Verificar que tenemos filas pares
    if len(tabla) % 2 != 0:
        st.warning(f"Número impar de filas: {len(tabla)}")
    
    # Mostrar como tabla simple
    st.write("**Formato tabla:**")
    
    # Crear HTML para mejor visualización
    html = """
    <div style="background-color: #1a1a1a; border-radius: 8px; padding: 15px; overflow-x: auto;">
    <table style="width: 100%; border-collapse: collapse; color: white; font-family: monospace;">
        <thead>
            <tr style="background-color: #2d2d2d;">
                <th style="padding: 10px; border: 1px solid #444; text-align: left;">Fecha</th>
                <th style="padding: 10px; border: 1px solid #444; text-align: left;">Momento</th>
                <th style="padding: 10px; border: 1px solid #444; text-align: left;">Cielo</th>
                <th style="padding: 10px; border: 1px solid #444; text-align: left;">Temp</th>
                <th style="padding: 10px; border: 1px solid #444; text-align: left;">Viento</th>
                <th style="padding: 10px; border: 1px solid #444; text-align: left;">Ráfagas</th>
                <th style="padding: 10px; border: 1px solid #444; text-align: left;">Presión</th>
            </tr>
        </thead>
        <tbody>
    """
    
    for i, fila in enumerate(tabla):
        bg_color = "#252525" if i % 2 == 0 else "#1a1a1a"
        
        html += f"""
        <tr style="background-color: {bg_color};">
            <td style="padding: 8px; border: 1px solid #444;">{fila['Fecha']}</td>
            <td style="padding: 8px; border: 1px solid #444; font-weight: bold;">{fila['Momento']}</td>
            <td style="padding: 8px; border: 1px solid #444;">{fila['Cielo']}</td>
            <td style="padding: 8px; border: 1px solid #444;">{fila['Temperatura']}</td>
            <td style="padding: 8px; border: 1px solid #444;">{fila['Viento']}</td>
            <td style="padding: 8px; border: 1px solid #444;">{fila['Ráfagas']}</td>
            <td style="padding: 8px; border: 1px solid #444;">{fila['Presión']}</td>
        </tr>
        """
    
    html += """
        </tbody>
    </table>
    </div>
    """
    
    st.markdown(html, unsafe_allow_html=True)
    
    # También mostrar como texto plano para verificar
    st.write("**Datos en texto plano:**")
    for fila in tabla:
        st.text(f"{fila['Fecha']}\t{fila['Momento']}\t{fila['Cielo']}\t{fila['Temperatura']}\t{fila['Viento']}\t{fila['Ráfagas']}\t{fila['Presión']}")

def mostrar_seccion_smn_exacta(seccion):
    """Muestra la sección EXACTA de Chapelco del SMN"""
    
    st.subheader("⏰ Sección CHAPELCO_AERO - SMN")
    
    if not seccion:
        st.warning("No hay sección para mostrar")
        return
    
    # Mostrar exactamente como está en el archivo
    st.write("**Contenido exacto del archivo:**")
    
    # Usar un contenedor con estilo monospace
    st.markdown(f"""
    <div style="
        background-color: #1a1a1a;
        border-radius: 8px;
        padding: 15px;
        font-family: 'Courier New', monospace;
        white-space: pre-wrap;
        color: #f0f0f0;
        border-left: 4px solid #2196F3;
        overflow-x: auto;
    ">
    {seccion}
    </div>
    """, unsafe_allow_html=True)
    
    # Contar líneas
    lineas = seccion.split('\n')
    st.write(f"**Total líneas:** {len(lineas)}")
    
    # Mostrar primeras líneas como ejemplo
    st.write("**Primeras 10 líneas:**")
    for i, linea in enumerate(lineas[:10]):
        st.text(f"{i+1}: {linea}")

def mostrar_datos_openmeteo(datos):
    """Muestra datos de Open-Meteo"""
    
    st.subheader("🛰️ Datos Open-Meteo")
    
    # Mostrar resumen simple
    st.write("**Resumen de datos disponibles:**")
    
    if 'daily' in datos and 'time' in datos['daily']:
        st.write(f"📅 **Días pronosticados:** {len(datos['daily']['time'])}")
        
        # Mostrar primeros 3 días
        for i in range(min(3, len(datos['daily']['time']))):
            st.write(f"**{datos['daily']['time'][i]}:**")
            st.write(f"  - Temp máx: {datos['daily']['temperature_2m_max'][i]:.1f}°C")
            st.write(f"  - Temp mín: {datos['daily']['temperature_2m_min'][i]:.1f}°C")
            st.write(f"  - Precipitación: {datos['daily']['precipitation_sum'][i]:.1f} mm")
            st.write(f"  - Viento máx: {datos['daily']['windspeed_10m_max'][i]:.1f} km/h")
    
    if 'hourly' in datos and 'time' in datos['hourly']:
        st.write(f"⏰ **Horas pronosticadas:** {len(datos['hourly']['time'])}")

# Ejecutar aplicación
if __name__ == "__main__":
    main()

# Footer
st.markdown("---")
st.caption("""
**Sistema de Extracción V2.1** | 
AIC: 2 filas/día (Día+Noche) | 
SMN: Sección exacta CHAPELCO_AERO | 
Open-Meteo: Funcional
""")
