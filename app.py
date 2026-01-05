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
# AIC - PARSEO CORRECTO DE COLUMNAS
# ============================================================================

def obtener_aic_columnas():
    """Parsea el PDF de AIC como columnas, no como filas"""
    
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
        
        # DEBUG: Mostrar todas las líneas
        st.write("**🔍 TODAS LAS LÍNEAS DEL PDF:**")
        for i, linea in enumerate(lineas):
            st.write(f"{i}: {linea}")
        
        # ============================================================
        # 1. FECHAS (Línea 1 - TODAS las fechas en una línea)
        # ============================================================
        if len(lineas) < 1:
            return [], False, "❌ PDF vacío o sin formato esperado"
        
        linea_fechas = lineas[1]  # Línea 1 tiene: "04-01-2026 04-01-2026 05-01-2026..."
        todas_fechas = linea_fechas.split()
        
        # Solo tomar fechas únicas (cada fecha aparece 2 veces: día y noche)
        fechas_unicas = []
        for i in range(0, len(todas_fechas), 2):
            if i < len(todas_fechas):
                fecha = todas_fechas[i]
                if fecha not in fechas_unicas:
                    fechas_unicas.append(fecha)
        
        st.write(f"**📅 Fechas únicas encontradas:** {fechas_unicas}")
        
        # ============================================================
        # 2. PERÍODOS (Línea 2 - Día/Noche alternados)
        # ============================================================
        if len(lineas) < 2:
            return [], False, "❌ Falta línea de períodos"
        
        linea_periodos = lineas[2]  # "Día Noche Día Noche Día Noche..."
        periodos = linea_periodos.split()
        st.write(f"**📊 Períodos:** {periodos}")
        
        # ============================================================
        # 3. CONDICIONES DEL CIELO (Líneas 3-6, combinarlas)
        # ============================================================
        # Las condiciones están repartidas en 4 líneas
        # Línea 3: "Cielo Mayormente"
        # Línea 4: "Despejado"
        # Línea 5: "Lluvias Débiles"
        # Línea 6: "y Dispersas"
        condiciones_combinadas = []
        
        # Tomar líneas 3 a 6 y combinar por columnas
        lineas_cielo = []
        for i in range(3, min(7, len(lineas))):
            lineas_cielo.append(lineas[i])
        
        st.write(f"**☁️ Líneas del cielo:** {lineas_cielo}")
        
        # Combinar las 4 líneas en una lista de condiciones
        # Cada línea tiene palabras separadas por espacios
        palabras_por_linea = [linea.split() for linea in lineas_cielo]
        
        # Determinar cuántas columnas hay (debe ser igual a len(periodos))
        num_columnas = len(periodos)
        
        # Reconstruir cada condición combinando palabras de cada línea
        condiciones = []
        for col in range(num_columnas):
            condicion = ""
            for linea_idx in range(len(palabras_por_linea)):
                if col < len(palabras_por_linea[linea_idx]):
                    condicion += palabras_por_linea[linea_idx][col] + " "
            condiciones.append(condicion.strip())
        
        st.write(f"**☁️ Condiciones reconstruidas ({len(condiciones)}):**")
        for i, cond in enumerate(condiciones):
            st.write(f"  Col {i} ({periodos[i]}): {cond}")
        
        # ============================================================
        # 4. TEMPERATURAS (Línea 7)
        # ============================================================
        if len(lineas) < 7:
            return [], False, "❌ Falta línea de temperaturas"
        
        linea_temperaturas = lineas[7]  # "Temperatura 27 ºC 13 ºC 27 ºC..."
        # Extraer solo los números (temperaturas)
        temperaturas = re.findall(r'(-?\d+)\s*[ºC°C]', linea_temperaturas)
        st.write(f"**🌡️ Temperaturas:** {temperaturas}")
        
        # ============================================================
        # 5. VIENTOS (Línea 8)
        # ============================================================
        if len(lineas) < 8:
            return [], False, "❌ Falta línea de vientos"
        
        linea_vientos = lineas[8]  # "Viento 26 km/h 20 km/h 13 km/h..."
        vientos = re.findall(r'(\d+)\s*km/h', linea_vientos)
        st.write(f"**💨 Vientos:** {vientos}")
        
        # ============================================================
        # 6. RÁFAGAS (Línea 9)
        # ============================================================
        if len(lineas) < 9:
            return [], False, "❌ Falta línea de ráfagas"
        
        linea_rafagas = lineas[9]  # "Ráfagas 30 km/h 20 km/h 19 km/h..."
        rafagas = re.findall(r'(\d+)\s*km/h', linea_rafagas)
        st.write(f"**🌪️ Ráfagas:** {rafagas}")
        
        # ============================================================
        # 7. DIRECCIÓN (Línea 10)
        # ============================================================
        if len(lineas) < 10:
            return [], False, "❌ Falta línea de dirección"
        
        linea_direccion = lineas[10]  # "Dirección NE SE O O O O E SE SO SO O O"
        # Separar por espacios y quitar "Dirección"
        partes = linea_direccion.split()
        direcciones = partes[1:] if partes[0] == "Dirección" else partes
        st.write(f"**🧭 Direcciones:** {direcciones}")
        
        # ============================================================
        # 8. PRESIÓN (Línea 11)
        # ============================================================
        if len(lineas) < 11:
            return [], False, "❌ Falta línea de presión"
        
        linea_presion = lineas[11]  # "Presión 1011 hPa 1013 hPa 1004 hPa..."
        presiones = re.findall(r'(\d+)\s*hPa', linea_presion)
        st.write(f"**📊 Presiones:** {presiones}")
        
        # ============================================================
        # CONSTRUIR TABLA FINAL
        # ============================================================
        tabla = []
        
        # Verificar que tenemos datos para todas las columnas
        num_datos_esperados = len(periodos)
        
        # Asegurar que todas las listas tengan la misma longitud
        listas_datos = {
            'condiciones': condiciones,
            'temperaturas': temperaturas,
            'vientos': vientos,
            'rafagas': rafagas,
            'direcciones': direcciones,
            'presiones': presiones
        }
        
        # Recortar todas las listas al mismo tamaño
        tamaño_minimo = min(
            len(condiciones),
            len(temperaturas),
            len(vientos),
            len(rafagas),
            len(direcciones),
            len(presiones),
            len(periodos)
        )
        
        st.write(f"**📏 Tamaño mínimo de datos:** {tamaño_minimo}")
        
        # Asignar fecha a cada columna
        fecha_idx = 0
        for col_idx in range(tamaño_minimo):
            # Determinar qué fecha corresponde a esta columna
            if col_idx % 2 == 0:  # Columnas pares son Día
                fecha = fechas_unicas[fecha_idx]
            else:  # Columnas impares son Noche (misma fecha)
                fecha = fechas_unicas[fecha_idx]
                fecha_idx += 1
            
            # Obtener datos para esta columna
            momento = periodos[col_idx] if col_idx < len(periodos) else f"Col{col_idx}"
            cielo = condiciones[col_idx] if col_idx < len(condiciones) else "N/D"
            temp = temperaturas[col_idx] if col_idx < len(temperaturas) else "N/D"
            viento = vientos[col_idx] if col_idx < len(vientos) else "N/D"
            rafaga = rafagas[col_idx] if col_idx < len(rafagas) else "N/D"
            direccion = direcciones[col_idx] if col_idx < len(direcciones) else "N/D"
            presion = presiones[col_idx] if col_idx < len(presiones) else "N/D"
            
            # Limpiar texto del cielo
            cielo_limpio = cielo.replace("Cielo ", "").strip()
            
            tabla.append({
                'Fecha': fecha,
                'Momento': momento,
                'Cielo': cielo_limpio,
                'Temperatura': f"{temp} ºC",
                'Viento': f"{viento} km/h",
                'Ráfagas': f"{rafaga} km/h",
                'Dirección': direccion,
                'Presión': f"{presion} hPa"
            })
        
        return tabla, True, f"✅ AIC: {len(tabla)} filas ({len(fechas_unicas)} días)"
        
    except Exception as e:
        st.error(f"❌ Error en AIC: {str(e)}")
        return [], False, f"❌ Error: {str(e)}"

# ============================================================================
# SMN - CON FECHA DINÁMICA
# ============================================================================

def obtener_smn_fecha_dinamica():
    """Descarga el ZIP dinámico del SMN"""
    
    try:
        # Generar URL con fecha actual
        fecha_actual = datetime.now()
        dia = fecha_actual.strftime("%d")
        mes = fecha_actual.strftime("%m")
        año = fecha_actual.strftime("%Y")
        
        # La URL ya incluye la fecha en el parámetro, pero el ZIP se genera dinámicamente
        url = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=pron5d"
        
        st.write(f"**📅 Fecha actual:** {dia}/{mes}/{año}")
        st.write(f"**🔗 URL SMN:** {url}")
        
        response = requests.get(url, timeout=30, verify=False)
        
        if response.status_code != 200:
            return None, False, f"❌ Error HTTP {response.status_code}"
        
        # Verificar contenido
        if len(response.content) < 100:
            return None, False, "❌ Archivo ZIP demasiado pequeño"
        
        # Intentar abrir como ZIP
        try:
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                archivos = zip_file.namelist()
                st.write(f"**📦 Archivos en el ZIP:** {archivos}")
                
                # Buscar archivo .txt
                txt_files = [f for f in archivos if f.endswith('.txt')]
                if not txt_files:
                    return None, False, "❌ No hay archivos .txt en el ZIP"
                
                # Leer el primer archivo .txt
                with zip_file.open(txt_files[0]) as f:
                    contenido_completo = f.read().decode('utf-8', errors='ignore')
                
                # Mostrar parte del contenido
                st.write("**🔍 Primeros 2000 caracteres del archivo TXT:**")
                st.code(contenido_completo[:2000])
                
                # Buscar CHAPELCO_AERO
                if 'CHAPELCO_AERO' in contenido_completo:
                    # Extraer sección completa
                    idx = contenido_completo.find('CHAPELCO_AERO')
                    seccion = contenido_completo[idx:]
                    
                    # Buscar hasta el próximo separador o estación
                    lineas = seccion.split('\n')
                    resultado = []
                    for linea in lineas[:50]:  # Tomar primeras 50 líneas
                        resultado.append(linea.rstrip())
                        if '======' in linea and len(resultado) > 10:
                            break
                    
                    return '\n'.join(resultado), True, "✅ SMN: Sección CHAPELCO_AERO encontrada"
                else:
                    # Buscar cualquier mención a Chapelco
                    contenido_upper = contenido_completo.upper()
                    if 'CHAPELCO' in contenido_upper:
                        idx = contenido_upper.find('CHAPELCO')
                        seccion = contenido_completo[idx:idx+1000]
                        return seccion, True, "✅ SMN: 'CHAPELCO' encontrado"
                    else:
                        return None, False, "❌ No se encontró CHAPELCO_AERO en el archivo"
        
        except zipfile.BadZipFile:
            return None, False, "❌ El archivo descargado no es un ZIP válido"
        
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
            return response.json(), True, "✅ Open-Meteo: OK"
        else:
            return {}, False, f"❌ Error: {response.status_code}"
    except:
        return {}, False, "❌ Error de conexión"

# ============================================================================
# INTERFAZ
# ============================================================================

def main():
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 AIC (Columnas)", type="primary", use_container_width=True):
            st.session_state.fuente = "AIC"
    
    with col2:
        if st.button("⏰ SMN (ZIP dinámico)", type="primary", use_container_width=True):
            st.session_state.fuente = "SMN"
    
    with col3:
        if st.button("🛰️ Open-Meteo", type="primary", use_container_width=True):
            st.session_state.fuente = "OPENMETEO"
    
    st.markdown("---")
    
    if hasattr(st.session_state, 'fuente'):
        fuente = st.session_state.fuente
        
        if fuente == "AIC":
            with st.spinner("Parseando AIC (formato columnas)..."):
                datos, ok, msg = obtener_aic_columnas()
                
                if ok and datos:
                    st.success(msg)
                    
                    # Mostrar como tabla bonita
                    st.write("### 📋 TABLA AIC - FORMATO CORRECTO")
                    
                    # Crear DataFrame
                    df = pd.DataFrame(datos)
                    
                    # Mostrar con estilo
                    st.dataframe(
                        df,
                        column_config={
                            "Fecha": st.column_config.TextColumn("Fecha", width="small"),
                            "Momento": st.column_config.TextColumn("Momento", width="small"),
                            "Cielo": st.column_config.TextColumn("Cielo", width="large"),
                            "Temperatura": st.column_config.TextColumn("Temp", width="small"),
                            "Viento": st.column_config.TextColumn("Viento", width="small"),
                            "Ráfagas": st.column_config.TextColumn("Ráfagas", width="small"),
                            "Dirección": st.column_config.TextColumn("Dir", width="small"),
                            "Presión": st.column_config.TextColumn("Presión", width="small")
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                    
                    # También mostrar en formato texto plano
                    st.write("### 📝 FORMATO TEXTO PLANO (para copiar):")
                    for fila in datos:
                        st.text(f"{fila['Fecha']}\t{fila['Momento']}\t{fila['Cielo']}\t{fila['Temperatura']}\t{fila['Viento']}\t{fila['Ráfagas']}\t{fila['Dirección']}\t{fila['Presión']}")
                else:
                    st.error(msg)
        
        elif fuente == "SMN":
            with st.spinner("Descargando ZIP dinámico del SMN..."):
                datos, ok, msg = obtener_smn_fecha_dinamica()
                
                if ok and datos:
                    st.success(msg)
                    st.write("### ⏰ SECCIÓN SMN - CHAPELCO_AERO")
                    st.code(datos)
                else:
                    st.error(msg)
        
        elif fuente == "OPENMETEO":
            with st.spinner("Obteniendo datos de Open-Meteo..."):
                datos, ok, msg = obtener_openmeteo()
                
                if ok:
                    st.success(msg)
                    st.write("### 🛰️ DATOS OPEN-METEO")
                    st.json(datos)
                else:
                    st.error(msg)

if __name__ == "__main__":
    main()

st.markdown("---")
st.caption("Sistema de Extracción V3.0 | AIC: Parseo por columnas | SMN: ZIP dinámico | Open-Meteo: Funcional")
