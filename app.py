import streamlit as st
import requests
from datetime import datetime
import zipfile
import io
import re

# Configuración
st.set_page_config(page_title="Extracción Meteorológica", page_icon="📡", layout="wide")

st.title("📡 Extracción Meteorológica SMA")
st.markdown("---")

# ============================================================================
# AIC - VERSIÓN SIMPLE Y DIRECTA
# ============================================================================

def obtener_aic_simple():
    """Versión simple y directa de AIC"""
    
    try:
        url = "https://www.aic.gob.ar/sitio/extendido-pdf?a=1029&z=1750130550"
        response = requests.get(url, timeout=30, verify=False)
        
        if response.status_code != 200:
            return [], False, "❌ Error al descargar PDF"
        
        import pdfplumber
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            texto = pdf.pages[0].extract_text()
            
        # SEPARAR LÍNEAS
        lineas = [line.strip() for line in texto.split('\n') if line.strip()]
        
        st.write("**🔍 DEBUG AIC - Primeras 15 líneas:**")
        for i, linea in enumerate(lineas[:15]):
            st.write(f"{i}: {linea}")
        
        # 1. FECHAS (línea 1)
        fechas_linea = lineas[1] if len(lineas) > 1 else ""
        # Separar por espacios y eliminar duplicados consecutivos
        fechas_todas = fechas_linea.split()
        fechas = []
        for fecha in fechas_todas:
            if re.match(r'\d{2}-\d{2}-\d{4}', fecha) and (not fechas or fecha != fechas[-1]):
                fechas.append(fecha)
        
        st.write(f"📅 **Fechas únicas:** {fechas}")
        
        # 2. PERÍODOS (línea 2)
        periodos_linea = lineas[2] if len(lineas) > 2 else ""
        periodos = periodos_linea.split()
        st.write(f"📊 **Períodos:** {periodos}")
        
        # 3. CONDICIONES (líneas 3-6)
        condiciones = []
        for i in range(3, min(7, len(lineas))):
            condiciones.append(lineas[i])
        st.write(f"☁️ **Condiciones crudas:** {condiciones}")
        
        # 4. TEMPERATURAS (línea 7)
        temps_linea = lineas[7] if len(lineas) > 7 else ""
        temperaturas = re.findall(r'(-?\d+)\s*[ºC°C]', temps_linea)
        st.write(f"🌡️ **Temperaturas:** {temperaturas}")
        
        # 5. VIENTOS (línea 8)
        vientos_linea = lineas[8] if len(lineas) > 8 else ""
        vientos = re.findall(r'(\d+)\s*km/h', vientos_linea)
        st.write(f"💨 **Vientos:** {vientos}")
        
        # 6. RÁFAGAS (línea 9)
        rafagas_linea = lineas[9] if len(lineas) > 9 else ""
        rafagas = re.findall(r'(\d+)\s*km/h', rafagas_linea)
        st.write(f"🌪️ **Ráfagas:** {rafagas}")
        
        # 7. DIRECCIÓN (línea 10)
        dir_linea = lineas[10] if len(lineas) > 10 else ""
        # Extraer solo las direcciones (NE, SE, O, etc.)
        direcciones = []
        for palabra in dir_linea.split():
            if re.match(r'^[NSEO]{1,3}$', palabra):
                direcciones.append(palabra)
        st.write(f"🧭 **Direcciones:** {direcciones}")
        
        # 8. PRESIÓN (línea 11)
        pres_linea = lineas[11] if len(lineas) > 11 else ""
        presiones = re.findall(r'(\d+)\s*hPa', pres_linea)
        st.write(f"📊 **Presiones:** {presiones}")
        
        # CONSTRUIR TABLA
        tabla = []
        dia_idx = 0
        
        for fecha in fechas[:3]:  # Solo primeros 3 días
            # DÍA
            if dia_idx * 2 < len(periodos) and periodos[dia_idx * 2] == 'Día':
                cielo_dia = condiciones[0] if len(condiciones) > 0 else "No disponible"
                if len(condiciones) > 3:
                    cielo_dia += " " + condiciones[3]
                
                tabla.append({
                    'Fecha': fecha,
                    'Momento': 'Día',
                    'Cielo': cielo_dia.strip(),
                    'Temperatura': f"{temperaturas[dia_idx * 2]} ºC" if dia_idx * 2 < len(temperaturas) else "N/D",
                    'Viento': f"{vientos[dia_idx * 2]} km/h" if dia_idx * 2 < len(vientos) else "N/D",
                    'Ráfagas': f"{rafagas[dia_idx * 2]} km/h" if dia_idx * 2 < len(rafagas) else "N/D",
                    'Presión': f"{presiones[dia_idx * 2]} hPa" if dia_idx * 2 < len(presiones) else "N/D"
                })
            
            # NOCHE
            if dia_idx * 2 + 1 < len(periodos) and periodos[dia_idx * 2 + 1] == 'Noche':
                cielo_noche = condiciones[1] if len(condiciones) > 1 else "No disponible"
                if len(condiciones) > 4:
                    cielo_noche += " " + condiciones[4]
                if len(condiciones) > 5:
                    cielo_noche += " " + condiciones[5]
                
                tabla.append({
                    'Fecha': fecha,
                    'Momento': 'Noche',
                    'Cielo': cielo_noche.strip(),
                    'Temperatura': f"{temperaturas[dia_idx * 2 + 1]} ºC" if dia_idx * 2 + 1 < len(temperaturas) else "N/D",
                    'Viento': f"{vientos[dia_idx * 2 + 1]} km/h" if dia_idx * 2 + 1 < len(vientos) else "N/D",
                    'Ráfagas': f"{rafagas[dia_idx * 2 + 1]} km/h" if dia_idx * 2 + 1 < len(rafagas) else "N/D",
                    'Presión': f"{presiones[dia_idx * 2 + 1]} hPa" if dia_idx * 2 + 1 < len(presiones) else "N/D"
                })
            
            dia_idx += 1
        
        return tabla, True, f"✅ AIC: {len(tabla)} filas"
        
    except Exception as e:
        return [], False, f"❌ Error AIC: {str(e)}"

# ============================================================================
# SMN - VERSIÓN SIMPLE
# ============================================================================

def obtener_smn_simple():
    """Versión simple de SMN - muestra el contenido completo"""
    
    try:
        url = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=pron5d"
        response = requests.get(url, timeout=30, verify=False)
        
        if response.status_code != 200:
            return None, False, f"❌ Error HTTP {response.status_code}"
        
        # Guardar contenido para análisis
        contenido_bytes = response.content
        
        # Intentar como ZIP
        try:
            with zipfile.ZipFile(io.BytesIO(contenido_bytes)) as zip_file:
                archivos = zip_file.namelist()
                st.write(f"📦 **Archivos en ZIP:** {archivos}")
                
                # Buscar cualquier archivo .txt
                txt_files = [f for f in archivos if f.endswith('.txt')]
                if not txt_files:
                    return None, False, "❌ No hay archivos .txt"
                
                # Leer el primer archivo .txt
                with zip_file.open(txt_files[0]) as f:
                    contenido = f.read().decode('utf-8', errors='ignore')
                
        except zipfile.BadZipFile:
            # Intentar como texto directo
            contenido = contenido_bytes.decode('utf-8', errors='ignore')
        
        # Mostrar contenido completo para debugging
        st.write("**🔍 CONTENIDO COMPLETO SMN (primeros 2000 caracteres):**")
        st.text(contenido[:2000])
        
        # Buscar CHAPELCO_AERO sin importar mayúsculas/minúsculas
        contenido_lower = contenido.lower()
        if 'chapelco_aero' in contenido_lower:
            # Encontrar posición
            idx = contenido_lower.find('chapelco_aero')
            
            # Extraer 1000 caracteres después de CHAPELCO_AERO
            seccion = contenido[idx:idx + 1000]
            
            return seccion, True, "✅ SMN: Sección CHAPELCO_AERO encontrada"
        else:
            # Buscar variantes
            variantes = ['CHAPELCO', 'Chapelco', 'chapelco']
            for var in variantes:
                if var in contenido:
                    idx = contenido.find(var)
                    seccion = contenido[idx:idx + 1000]
                    return seccion, True, f"✅ SMN: '{var}' encontrado"
            
            return None, False, "❌ No se encontró CHAPELCO_AERO ni variantes"
    
    except Exception as e:
        return None, False, f"❌ Error SMN: {str(e)}"

# ============================================================================
# OPEN-METEO (YA FUNCIONA)
# ============================================================================

def obtener_openmeteo():
    try:
        url = "https://api.open-meteo.com/v1/forecast?latitude=-40.1579&longitude=-71.3534&hourly=temperature_2m&daily=temperature_2m_max,temperature_2m_min&timezone=America%2FArgentina%2FBuenos_Aires&forecast_days=3"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            return response.json(), True, "✅ Open-Meteo: OK"
        else:
            return {}, False, f"❌ Error: {response.status_code}"
    except:
        return {}, False, "❌ Error de conexión"

# ============================================================================
# INTERFAZ PRINCIPAL
# ============================================================================

def main():
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 AIC", type="primary", use_container_width=True):
            st.session_state.fuente = "AIC"
    
    with col2:
        if st.button("⏰ SMN", type="primary", use_container_width=True):
            st.session_state.fuente = "SMN"
    
    with col3:
        if st.button("🛰️ Open-Meteo", type="primary", use_container_width=True):
            st.session_state.fuente = "OPENMETEO"
    
    st.markdown("---")
    
    if hasattr(st.session_state, 'fuente'):
        fuente = st.session_state.fuente
        
        if fuente == "AIC":
            with st.spinner("Extrayendo AIC..."):
                datos, ok, msg = obtener_aic_simple()
                
                if ok and datos:
                    st.success(msg)
                    
                    # Mostrar tabla simple
                    st.write("**📋 TABLA AIC:**")
                    for fila in datos:
                        st.write(f"**{fila['Fecha']}** - **{fila['Momento']}**")
                        st.write(f"  Cielo: {fila['Cielo']}")
                        st.write(f"  Temp: {fila['Temperatura']}")
                        st.write(f"  Viento: {fila['Viento']}")
                        st.write(f"  Ráfagas: {fila['Ráfagas']}")
                        st.write(f"  Presión: {fila['Presión']}")
                        st.write("---")
                else:
                    st.error(msg)
        
        elif fuente == "SMN":
            with st.spinner("Extrayendo SMN..."):
                datos, ok, msg = obtener_smn_simple()
                
                if ok and datos:
                    st.success(msg)
                    st.write("**⏰ SECCIÓN SMN:**")
                    st.code(datos)
                else:
                    st.error(msg)
        
        elif fuente == "OPENMETEO":
            with st.spinner("Extrayendo Open-Meteo..."):
                datos, ok, msg = obtener_openmeteo()
                
                if ok:
                    st.success(msg)
                    st.write("**🛰️ DATOS OPEN-METEO:**")
                    st.json(datos)
                else:
                    st.error(msg)

if __name__ == "__main__":
    main()
