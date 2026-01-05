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
# AIC - VERSIÓN LIMPIA
# ============================================================================

def obtener_aic():
    """Versión limpia de AIC - solo tabla final"""
    
    try:
        url = "https://www.aic.gob.ar/sitio/extendido-pdf?a=1029&z=1750130550"
        response = requests.get(url, timeout=30, verify=False)
        
        if response.status_code != 200:
            return [], False, "❌ Error al descargar PDF"
        
        import pdfplumber
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            texto = pdf.pages[0].extract_text()
        
        lineas = [line.strip() for line in texto.split('\n') if line.strip()]
        
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
        
        # 3. CONDICIONES (líneas 3-6)
        lineas_cielo = lineas[3:7]
        palabras_por_linea = [linea.split() for linea in lineas_cielo]
        
        # Reconstruir condiciones
        condiciones = []
        for col in range(len(periodos)):
            condicion = ""
            for linea_idx in range(len(palabras_por_linea)):
                if col < len(palabras_por_linea[linea_idx]):
                    condicion += palabras_por_linea[linea_idx][col] + " "
            condiciones.append(condicion.strip())
        
        # 4. TEMPERATURAS (línea 7)
        temperaturas = re.findall(r'(-?\d+)\s*[ºC°C]', lineas[7])
        
        # 5. VIENTOS (línea 8)
        vientos = re.findall(r'(\d+)\s*km/h', lineas[8])
        
        # 6. RÁFAGAS (línea 9)
        rafagas = re.findall(r'(\d+)\s*km/h', lineas[9])
        
        # 7. DIRECCIÓN (línea 10)
        partes = lineas[10].split()
        direcciones = partes[1:] if partes[0] == "Dirección" else partes
        
        # 8. PRESIÓN (línea 11)
        presiones = re.findall(r'(\d+)\s*hPa', lineas[11])
        
        # CONSTRUIR TABLA
        tabla = []
        fecha_idx = 0
        
        for col_idx in range(min(len(periodos), len(temperaturas), len(vientos), len(rafagas), len(direcciones), len(presiones))):
            # Determinar fecha
            if col_idx % 2 == 0:
                fecha = fechas_unicas[fecha_idx]
            else:
                fecha = fechas_unicas[fecha_idx]
                fecha_idx += 1
            
            # Limpiar "Cielo " del inicio si existe
            cielo = condiciones[col_idx] if col_idx < len(condiciones) else "N/D"
            if cielo.startswith("Cielo "):
                cielo = cielo[6:]
            
            tabla.append({
                'Fecha': fecha,
                'Momento': periodos[col_idx],
                'Cielo': cielo,
                'Temperatura': f"{temperaturas[col_idx]} ºC" if col_idx < len(temperaturas) else "N/D",
                'Viento': f"{vientos[col_idx]} km/h" if col_idx < len(vientos) else "N/D",
                'Ráfagas': f"{rafagas[col_idx]} km/h" if col_idx < len(rafagas) else "N/D",
                'Presión': f"{presiones[col_idx]} hPa" if col_idx < len(presiones) else "N/D"
            })
        
        return tabla, True, f"✅ AIC: {len(tabla)} registros ({len(fechas_unicas)} días)"
        
    except Exception as e:
        return [], False, f"❌ Error AIC: {str(e)}"

# ============================================================================
# SMN - VERSIÓN SIMPLE
# ============================================================================

def obtener_smn():
    """Versión simple de SMN - encuentra el TXT dinámico"""
    
    try:
        url = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=pron5d"
        response = requests.get(url, timeout=30, verify=False)
        
        if response.status_code != 200:
            return None, False, f"❌ Error HTTP {response.status_code}"
        
        # Abrir ZIP
        with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
            # Listar todos los archivos
            archivos = zip_file.namelist()
            
            # Buscar archivo que empiece con "pronostico" y termine en ".txt"
            archivos_txt = [f for f in archivos if f.lower().endswith('.txt') and 'pronostico' in f.lower()]
            
            if not archivos_txt:
                return None, False, f"❌ No hay archivos TXT en el ZIP. Archivos: {archivos}"
            
            # Usar el primer archivo TXT que encontremos
            archivo_txt = archivos_txt[0]
            
            # Leer contenido
            with zip_file.open(archivo_txt) as f:
                contenido = f.read().decode('utf-8', errors='ignore')
            
            # Buscar CHAPELCO
            if 'CHAPELCO' in contenido.upper():
                # Extraer desde CHAPELCO hasta el próximo código o fin
                idx = contenido.upper().find('CHAPELCO')
                seccion = contenido[idx:]
                
                # Tomar hasta el próximo código de estación (4 letras mayúsculas)
                lineas = seccion.split('\n')
                resultado = []
                for linea in lineas:
                    resultado.append(linea.rstrip())
                    # Si encontramos otro código de estación, parar
                    if len(resultado) > 10 and re.match(r'^[A-Z]{4,}_[A-Z]{4,}$', linea.strip()):
                        break
                    if len(resultado) > 50:  # Límite de líneas
                        break
                
                return '\n'.join(resultado), True, f"✅ SMN: Encontrado en {archivo_txt}"
            else:
                return None, False, "❌ No se encontró CHAPELCO en el archivo"
    
    except zipfile.BadZipFile:
        return None, False, "❌ No es un archivo ZIP válido"
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
            return datos, True, f"✅ Open-Meteo: {len(datos.get('daily', {}).get('time', []))} días"
        else:
            return {}, False, f"❌ Error {response.status_code}"
    except Exception as e:
        return {}, False, f"❌ Error: {str(e)}"

# ============================================================================
# INTERFAZ SIMPLE
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
            datos, ok, msg = obtener_aic()
            
            if ok:
                st.success(msg)
                
                # Mostrar tabla
                df = pd.DataFrame(datos)
                st.dataframe(df, hide_index=True, use_container_width=True)
                
                # Botón para descargar
                csv = df.to_csv(index=False, sep='\t')
                st.download_button(
                    "📥 Descargar tabla AIC (TSV)",
                    csv,
                    "aic_datos.tsv",
                    "text/tab-separated-values"
                )
            else:
                st.error(msg)
        
        elif fuente == "SMN":
            datos, ok, msg = obtener_smn()
            
            if ok and datos:
                st.success(msg)
                
                # Mostrar contenido
                st.text_area("Contenido del archivo SMN:", datos, height=400)
                
                # Botón para descargar
                st.download_button(
                    "📥 Descargar texto SMN",
                    datos,
                    "smn_chapelco.txt",
                    "text/plain"
                )
            else:
                st.error(msg)
        
        elif fuente == "OPENMETEO":
            datos, ok, msg = obtener_openmeteo()
            
            if ok:
                st.success(msg)
                
                # Mostrar datos diarios
                if 'daily' in datos and 'time' in datos['daily']:
                    st.write("**Pronóstico diario:**")
                    daily_data = []
                    for i in range(min(3, len(datos['daily']['time']))):
                        daily_data.append({
                            'Fecha': datos['daily']['time'][i],
                            'Máx': f"{datos['daily']['temperature_2m_max'][i]:.1f}°C",
                            'Mín': f"{datos['daily']['temperature_2m_min'][i]:.1f}°C"
                        })
                    
                    st.table(daily_data)
                
                # Botón para descargar JSON
                import json
                json_data = json.dumps(datos, indent=2)
                st.download_button(
                    "📥 Descargar JSON Open-Meteo",
                    json_data,
                    "openmeteo_datos.json",
                    "application/json"
                )
            else:
                st.error(msg)

if __name__ == "__main__":
    main()

st.markdown("---")
st.caption("Sistema de Extracción V4.0 | Simple y funcional")
