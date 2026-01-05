import streamlit as st
import requests
from datetime import datetime
import zipfile
import io
import re
import pandas as pd

# Configuración
st.set_page_config(page_title="Extracción Meteorológica", page_icon="📡", layout="wide")

st.title("📡 Extracción Meteorológica SMA")
st.markdown("---")

# ============================================================================
# AIC - CORREGIDO (CIELO BIEN PARSEADO)
# ============================================================================

def obtener_aic_corregido():
    """AIC con cielo correctamente parseado"""
    
    try:
        url = "https://www.aic.gob.ar/sitio/extendido-pdf?a=1029&z=1750130550"
        response = requests.get(url, timeout=30, verify=False)
        
        if response.status_code != 200:
            return [], False, "❌ Error al descargar PDF"
        
        import pdfplumber
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            texto = pdf.pages[0].extract_text()
        
        lineas = [line.strip() for line in texto.split('\n') if line.strip()]
        
        # DEBUG mínimo
        if len(lineas) < 12:
            return [], False, "❌ PDF con formato inesperado"
        
        # 1. FECHAS (línea 1)
        linea_fechas = lineas[1]
        todas_fechas = linea_fechas.split()
        fechas_unicas = []
        for i in range(0, len(todas_fechas), 2):
            if i < len(todas_fechas):
                fecha = todas_fechas[i]
                if fecha not in fechas_unicas:
                    fechas_unicas.append(fecha)
        
        # 2. PERÍODOS (línea 2)
        periodos = lineas[2].split()
        
        # 3. CONDICIONES - FORMA CORRECTA
        # Las líneas 3-6 tienen las condiciones en columnas
        # Cada línea tiene 12 palabras (una por columna)
        lineas_cielo = lineas[3:7]
        
        # Parsear CORRECTAMENTE: cada línea tiene 12 columnas
        condiciones = []
        for col in range(12):  # Siempre 12 columnas (6 días × 2)
            condicion_completa = ""
            for linea in lineas_cielo:
                palabras = linea.split()
                if col < len(palabras):
                    palabra = palabras[col]
                    # Quitar "Cielo" si está en la primera columna de la primera línea
                    if col == 0 and palabra == "Cielo":
                        continue
                    condicion_completa += palabra + " "
            
            condiciones.append(condicion_completa.strip())
        
        # 4. TEMPERATURAS (línea 7)
        temperaturas = re.findall(r'(-?\d+)\s*[ºC°C]', lineas[7])
        
        # 5. VIENTOS (línea 8)
        vientos = re.findall(r'(\d+)\s*km/h', lineas[8])
        
        # 6. RÁFAGAS (línea 9)
        rafagas = re.findall(r'(\d+)\s*km/h', lineas[9])
        
        # 7. DIRECCIÓN (línea 10)
        partes = lineas[10].split()
        direcciones = partes[1:] if partes and partes[0] == "Dirección" else partes
        
        # 8. PRESIÓN (línea 11)
        presiones = re.findall(r'(\d+)\s*hPa', lineas[11])
        
        # CONSTRUIR TABLA CORRECTA
        tabla = []
        
        for i in range(min(12, len(periodos), len(temperaturas))):
            # Calcular fecha correcta
            fecha_idx = i // 2  # Cada 2 columnas es un nuevo día
            if fecha_idx < len(fechas_unicas):
                fecha = fechas_unicas[fecha_idx]
            else:
                fecha = "N/D"
            
            # Obtener cielo y limpiar
            cielo = condiciones[i] if i < len(condiciones) else ""
            # Quitar palabras repetidas o sin sentido
            cielo = re.sub(r'\bCielo\b', '', cielo).strip()
            cielo = re.sub(r'\s+', ' ', cielo)  # Espacios múltiples
            
            tabla.append({
                'Fecha': fecha,
                'Momento': periodos[i] if i < len(periodos) else "N/D",
                'Cielo': cielo if cielo else "No disponible",
                'Temperatura': f"{temperaturas[i]} ºC" if i < len(temperaturas) else "N/D",
                'Viento': f"{vientos[i]} km/h" if i < len(vientos) else "N/D",
                'Ráfagas': f"{rafagas[i]} km/h" if i < len(rafagas) else "N/D",
                'Presión': f"{presiones[i]} hPa" if i < len(presiones) else "N/D"
            })
        
        return tabla, True, f"✅ AIC: {len(tabla)} registros"
        
    except Exception as e:
        return [], False, f"❌ Error AIC: {str(e)}"

# ============================================================================
# SMN - VERSIÓN MEJORADA (BUSCA EN TODO EL CONTENIDO)
# ============================================================================

def obtener_smn_mejorado():
    """SMN que busca CHAPELCO en todo el contenido"""
    
    try:
        # URL del ZIP dinámico
        url = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=pron5d"
        
        st.write(f"🔗 Descargando ZIP desde: {url}")
        
        response = requests.get(url, timeout=30, verify=False)
        
        if response.status_code != 200:
            return None, False, f"❌ Error HTTP {response.status_code}"
        
        # Verificar tamaño
        if len(response.content) < 100:
            return None, False, "❌ Archivo ZIP demasiado pequeño"
        
        # Abrir ZIP
        try:
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                # Listar TODOS los archivos
                archivos = zip_file.namelist()
                st.write(f"📦 Archivos en ZIP ({len(archivos)}): {archivos}")
                
                # Buscar cualquier archivo .txt
                archivos_txt = [f for f in archivos if f.lower().endswith('.txt')]
                
                if not archivos_txt:
                    return None, False, "❌ No hay archivos .txt en el ZIP"
                
                # Probar cada archivo TXT
                for archivo_txt in archivos_txt:
                    st.write(f"📄 Probando archivo: {archivo_txt}")
                    
                    with zip_file.open(archivo_txt) as f:
                        contenido = f.read().decode('utf-8', errors='ignore')
                    
                    # Mostrar primeras 500 caracteres para debug
                    st.write(f"🔍 Primeros 500 caracteres de {archivo_txt}:")
                    st.code(contenido[:500])
                    
                    # Buscar CHAPELCO de diferentes formas
                    contenido_upper = contenido.upper()
                    
                    if 'CHAPELCO' in contenido_upper:
                        # Encontrar todas las apariciones
                        idx = contenido_upper.find('CHAPELCO')
                        
                        # Tomar 1500 caracteres desde CHAPELCO
                        seccion = contenido[idx:idx + 1500]
                        
                        # Dividir en líneas y tomar las más relevantes
                        lineas = seccion.split('\n')
                        resultado = []
                        
                        for linea in lineas:
                            linea = linea.rstrip()
                            if linea:  # Solo líneas no vacías
                                resultado.append(linea)
                            
                            # Parar si encontramos otro código o muchas líneas
                            if len(resultado) > 30:
                                break
                        
                        if resultado:
                            texto_completo = '\n'.join(resultado)
                            return texto_completo, True, f"✅ SMN: CHAPELCO encontrado en {archivo_txt}"
                
                # Si llegamos aquí, no encontró CHAPELCO en ningún archivo
                return None, False, "❌ CHAPELCO no encontrado en ningún archivo TXT"
        
        except zipfile.BadZipFile:
            # Intentar leer como texto directo
            contenido = response.content.decode('utf-8', errors='ignore')
            if 'CHAPELCO' in contenido.upper():
                idx = contenido.upper().find('CHAPELCO')
                return contenido[idx:idx+1000], True, "✅ SMN: CHAPELCO en texto directo"
            return None, False, "❌ No es ZIP válido ni tiene CHAPELCO"
        
    except Exception as e:
        return None, False, f"❌ Error SMN: {str(e)}"

# ============================================================================
# OPEN-METEO
# ============================================================================

def obtener_openmeteo():
    try:
        url = "https://api.open-meteo.com/v1/forecast?latitude=-40.1579&longitude=-71.3534&hourly=temperature_2m&daily=temperature_2m_max,temperature_2m_min&timezone=America%2FArgentina%2FBuenos_Aires&forecast_days=3"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            datos = response.json()
            dias = len(datos.get('daily', {}).get('time', []))
            return datos, True, f"✅ Open-Meteo: {dias} días"
        else:
            return {}, False, f"❌ Error {response.status_code}"
    except Exception as e:
        return {}, False, f"❌ Error: {str(e)}"

# ============================================================================
# INTERFAZ
# ============================================================================

def main():
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 AIC (corregido)", type="primary", use_container_width=True):
            st.session_state.fuente = "AIC"
    
    with col2:
        if st.button("⏰ SMN (debug)", type="primary", use_container_width=True):
            st.session_state.fuente = "SMN"
    
    with col3:
        if st.button("🛰️ Open-Meteo", type="primary", use_container_width=True):
            st.session_state.fuente = "OPENMETEO"
    
    st.markdown("---")
    
    if hasattr(st.session_state, 'fuente'):
        fuente = st.session_state.fuente
        
        if fuente == "AIC":
            with st.spinner("Parseando AIC..."):
                datos, ok, msg = obtener_aic_corregido()
                
                if ok:
                    st.success(msg)
                    
                    # Mostrar tabla
                    df = pd.DataFrame(datos)
                    st.dataframe(df, hide_index=True, use_container_width=True)
                    
                    # Mostrar en formato texto para verificar
                    st.write("**Formato texto:**")
                    for fila in datos:
                        st.text(f"{fila['Fecha']}\t{fila['Momento']}\t{fila['Cielo']}\t{fila['Temperatura']}\t{fila['Viento']}\t{fila['Ráfagas']}\t{fila['Presión']}")
                else:
                    st.error(msg)
        
        elif fuente == "SMN":
            with st.spinner("Buscando CHAPELCO..."):
                datos, ok, msg = obtener_smn_mejorado()
                
                if ok and datos:
                    st.success(msg)
                    
                    # Mostrar contenido
                    st.text_area("📄 Contenido SMN - CHAPELCO:", datos, height=500)
                    
                    # Contar líneas
                    lineas = datos.split('\n')
                    st.write(f"**📏 Total líneas:** {len(lineas)}")
                    
                    # Mostrar primeras 10 líneas numeradas
                    st.write("**Primeras 10 líneas:**")
                    for i, linea in enumerate(lineas[:10]):
                        st.text(f"{i+1}: {linea}")
                else:
                    st.error(msg)
        
        elif fuente == "OPENMETEO":
            datos, ok, msg = obtener_openmeteo()
            
            if ok:
                st.success(msg)
                
                # Mostrar datos simples
                if 'daily' in datos:
                    st.write("**Pronóstico diario:**")
                    for i in range(min(3, len(datos['daily']['time']))):
                        fecha = datos['daily']['time'][i]
                        temp_max = datos['daily']['temperature_2m_max'][i]
                        temp_min = datos['daily']['temperature_2m_min'][i]
                        st.write(f"**{fecha}:** Máx: {temp_max:.1f}°C, Mín: {temp_min:.1f}°C")
            else:
                st.error(msg)

if __name__ == "__main__":
    main()

st.markdown("---")
st.caption("Sistema de Extracción V5.0 | AIC corregido | SMN con debug")
