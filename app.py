import streamlit as st
import requests
from datetime import datetime, timedelta
import zipfile
import io
import re
import pdfplumber
import time
import urllib3

# Deshabilitar warnings de SSL para requests (útil para AIC)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 1. Configuración de Estética y Diseño Visual
st.set_page_config(page_title="Sintesis climatica sma", page_icon="🏔️", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .reporte-final { background-color: transparent; padding: 15px; font-size: 1.1rem; line-height: 1.6; color: #f0f2f6; }
    hr { margin: 1.5rem 0; border: 0; border-top: 1px solid #444; }
    .status-ok { color: #00cc00; }
    .status-error { color: #ff4444; }
    .status-warning { color: #ffaa00; }
    .datos-raw { font-family: monospace; font-size: 0.8rem; background: #1e1e1e; padding: 10px; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIONES DE CAPTURA DE DATOS ---

def obtener_datos_aic(fecha_base):
    """Extrae datos estructurados del PDF de AIC - DEVUELVE DATOS Y ESTADO"""
    # URLs alternativas
    urls = [
        "https://www.aic.gob.ar/sitio/extendido-pdf?a=1029&z=1750130550",
        "https://www.aic.gob.ar/sitio/extendido-pdf?id_localidad=22&id_pronostico=1",
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/pdf, */*',
        'Accept-Language': 'es-ES,es;q=0.9',
        'Referer': 'https://www.aic.gob.ar/'
    }
    
    for url_idx, url in enumerate(urls):
        for intento in range(2):
            try:
                st.write(f"🔍 Intentando AIC URL {url_idx+1}, intento {intento+1}...")
                response = requests.get(url, headers=headers, verify=False, timeout=30)
                
                st.write(f"📄 Status AIC: {response.status_code}, Tamaño: {len(response.content)} bytes")
                
                if response.status_code != 200:
                    st.warning(f"AIC URL {url_idx+1} falló con status {response.status_code}")
                    continue
                
                if len(response.content) < 1000:
                    st.warning(f"AIC URL {url_idx+1} contenido muy pequeño: {len(response.content)} bytes")
                    continue
                
                if response.content[:4] == b'%PDF':
                    with pdfplumber.open(io.BytesIO(response.content)) as pdf:
                        texto = pdf.pages[0].extract_text()
                        
                        st.write(f"📝 Texto extraído: {len(texto)} caracteres")
                        
                        if texto and len(texto.strip()) > 100:
                            # Guardar para debugging
                            with st.expander("📋 Ver contenido AIC crudo"):
                                st.text_area("Texto del PDF AIC:", texto[:2000], height=200)
                            
                            # Parsear datos estructurados
                            datos_parsed = parsear_aic_texto(texto, fecha_base)
                            if datos_parsed:
                                return datos_parsed, True, f"✅ AIC: {len(datos_parsed)} días obtenidos"
                            else:
                                return [], False, "❌ AIC: No se pudieron parsear los datos"
                        else:
                            st.warning("Texto AIC vacío o muy corto")
                else:
                    st.warning(f"No es PDF válido. Primeros bytes: {response.content[:100]}")
                
                time.sleep(1)
                
            except Exception as e:
                st.error(f"Error en AIC: {str(e)}")
                continue
    
    return [], False, "❌ AIC: No se pudo obtener el PDF"

def parsear_aic_texto(texto, fecha_base):
    """Parsea el texto del PDF de AIC y extrae datos estructurados"""
    try:
        # Guardar texto para debugging
        with st.expander("🔧 Debug AIC parsing"):
            st.write("Texto completo para parsear:")
            st.text(texto[:1000])
        
        lineas = [line.strip() for line in texto.split('\n') if line.strip()]
        
        st.write(f"📊 Líneas encontradas: {len(lineas)}")
        
        if len(lineas) < 10:
            st.warning("Muy pocas líneas en AIC")
            return []
        
        # Mostrar primeras líneas para debugging
        with st.expander("📋 Primeras 15 líneas AIC"):
            for i, linea in enumerate(lineas[:15]):
                st.write(f"{i}: {linea}")
        
        # Extraer datos del PDF
        fechas_line = lineas[1] if len(lineas) > 1 else ""
        st.write(f"📅 Línea de fechas: {fechas_line}")
        todas_fechas = fechas_line.split()
        st.write(f"Fechas encontradas: {todas_fechas}")
        
        periodos_line = lineas[2] if len(lineas) > 2 else ""
        st.write(f"📅 Línea de periodos: {periodos_line}")
        periodos = periodos_line.split()
        st.write(f"Periodos encontrados: {periodos}")
        
        # Temperaturas - buscar en líneas relevantes
        temps = []
        for i in range(max(0, len(lineas)-10), len(lineas)):
            line_temp = lineas[i]
            temp_matches = re.findall(r'(-?\d+)\s*[ºC°C]', line_temp)
            if temp_matches:
                temps.extend([float(t) for t in temp_matches])
                if len(temps) >= len(periodos):  # Tenemos suficientes
                    break
        
        # Si no encontramos, buscar específicamente
        if not temps:
            for linea in lineas:
                if 'ºC' in linea or '°C' in linea:
                    temp_matches = re.findall(r'(-?\d+)\s*[ºC°C]', linea)
                    if temp_matches:
                        temps.extend([float(t) for t in temp_matches])
        
        st.write(f"🌡️ Temperaturas encontradas: {temps}")
        
        # Viento
        winds = []
        for linea in lineas:
            wind_matches = re.findall(r'(\d+)\s*km/h', linea)
            if wind_matches:
                winds.extend([int(w) for w in wind_matches])
        
        st.write(f"💨 Vientos encontrados: {winds}")
        
        # Ráfagas
        gusts = []
        for linea in lineas:
            gust_matches = re.findall(r'(\d+)\s*km/h', linea)
            if gust_matches:
                gusts.extend([int(g) for g in gust_matches])
        
        st.write(f"🌪️ Ráfagas encontradas: {gusts}")
        
        # Dirección - buscar línea con "Dirección"
        dirs = []
        for linea in lineas:
            if 'Dirección' in linea:
                dir_text = linea.replace('Dirección', '').strip()
                dirs = dir_text.split()
                break
        
        st.write(f"🧭 Direcciones encontradas: {dirs}")
        
        # Presión
        pres = []
        for linea in lineas:
            if 'hPa' in linea:
                pres_matches = re.findall(r'(\d+)\s*hPa', linea)
                if pres_matches:
                    pres.extend([int(p) for p in pres_matches])
        
        st.write(f"📊 Presiones encontradas: {pres}")
        
        # Condiciones del cielo - buscar líneas con condiciones
        condiciones = []
        for linea in lineas:
            if any(keyword in linea for keyword in ['Mayor', 'Despej', 'Nubl', 'Torment', 'Lluv', 'Eléctr', 'Inest', 'Parcial']):
                # Limpiar la línea
                clean_line = re.sub(r'\d+', '', linea)  # Quitar números
                clean_line = clean_line.replace('ºC', '').replace('°C', '').replace('km/h', '').replace('hPa', '')
                condiciones.extend([c.strip() for c in clean_line.split(',') if c.strip()])
        
        st.write(f"☁️ Condiciones encontradas: {condiciones}")
        
        # Crear estructura de datos simplificada
        datos = []
        
        for i, periodo in enumerate(periodos):
            if i < len(todas_fechas):
                fecha_str = todas_fechas[i // 2] if (i // 2) < len(todas_fechas) else todas_fechas[0]
                
                try:
                    fecha_dt = datetime.strptime(fecha_str, '%d-%m-%Y').date()
                    
                    # Solo incluir fechas desde fecha_base
                    if fecha_dt >= fecha_base:
                        dato = {
                            'fecha': fecha_str,
                            'fecha_dt': fecha_dt,
                            'periodo': periodo,
                            'condicion': condiciones[i] if i < len(condiciones) else "Datos AIC"
                        }
                        
                        # Agregar temperaturas si están disponibles
                        if i < len(temps):
                            dato['temp'] = temps[i]
                        
                        # Para día/noche, asignar max/min
                        if periodo == 'Día' and i < len(temps):
                            dato['temp_max'] = temps[i]
                            if i+1 < len(temps):
                                dato['temp_min'] = temps[i+1]
                        
                        datos.append(dato)
                        
                        # Limitar a 3 días
                        if len(datos) >= 3:
                            break
                            
                except ValueError as e:
                    st.warning(f"Error parseando fecha {fecha_str}: {e}")
                    continue
        
        st.write(f"📋 Datos AIC parseados: {len(datos)} registros")
        return datos
        
    except Exception as e:
        st.error(f"❌ Error parseando AIC: {e}")
        import traceback
        st.error(traceback.format_exc())
        return []

def obtener_datos_smn():
    """Obtiene datos de SMN - VERSIÓN MEJORADA"""
    url = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=pron5d"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'es-ES,es;q=0.9',
    }
    
    try:
        st.write("🔍 Intentando obtener datos SMN...")
        
        # Intentar con timeout más largo
        r = requests.get(url, headers=headers, timeout=25, verify=False)
        st.write(f"📡 Status SMN: {r.status_code}, Tamaño: {len(r.content)} bytes")
        
        if r.status_code != 200:
            st.warning(f"SMN respondió con status {r.status_code}")
            return {}, False, f"❌ SMN: Error HTTP {r.status_code}"
        
        if len(r.content) < 100:
            st.warning("Contenido SMN muy pequeño")
            return {}, False, "❌ SMN: Contenido vacío"
        
        # Verificar si es un zip
        try:
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                st.write(f"📦 Archivos en ZIP SMN: {z.namelist()}")
                
                # Buscar archivo txt
                txt_files = [f for f in z.namelist() if f.endswith('.txt')]
                if not txt_files:
                    st.warning("No hay archivos .txt en el ZIP")
                    # Guardar contenido para debugging
                    with st.expander("📋 Ver contenido ZIP SMN"):
                        st.write("Primeros 500 bytes del ZIP:")
                        st.text(r.content[:500].decode('latin-1', errors='ignore'))
                    return {}, False, "❌ SMN: No hay archivos txt en el ZIP"
                
                nombre_txt = txt_files[0]
                st.write(f"📄 Archivo TXT encontrado: {nombre_txt}")
                
                with z.open(nombre_txt) as f:
                    contenido = f.read().decode('utf-8', errors='ignore')
                    st.write(f"📝 Contenido TXT: {len(contenido)} caracteres")
                    
                    # Mostrar parte del contenido
                    with st.expander("📋 Ver contenido SMN crudo"):
                        st.text_area("Contenido del TXT SMN:", contenido[:2000], height=200)
                    
                    # Buscar Chapelco de diferentes formas
                    chapelco_patterns = [
                        'CHAPELCO_AERO',
                        'CHAPELCO',
                        'Chapelco',
                        'AERO CHAPELCO'
                    ]
                    
                    for pattern in chapelco_patterns:
                        if pattern in contenido.upper():
                            st.write(f"✅ Encontrado: {pattern}")
                            
                            # Extraer bloque
                            partes = contenido.upper().split(pattern)
                            if len(partes) > 1:
                                bloque = partes[1]
                                # Tomar hasta el próximo código de estación o fin
                                next_station = re.search(r'[A-Z]{4,}_[A-Z]{4,}|[A-Z]{4,}', bloque)
                                if next_station:
                                    bloque = bloque[:next_station.start()]
                                
                                st.write(f"📊 Tamaño del bloque Chapelco: {len(bloque)} caracteres")
                                
                                datos_smn = procesar_bloque_smn(bloque)
                                if datos_smn:
                                    return datos_smn, True, f"✅ SMN: {len(datos_smn)} días obtenidos"
                                else:
                                    # Intentar parseo alternativo
                                    datos_alternativos = parsear_smn_alternativo(bloque)
                                    if datos_alternativos:
                                        return datos_alternativos, True, f"✅ SMN (alt): {len(datos_alternativos)} días"
                                    else:
                                        return {}, False, f"❌ SMN: No se pudo parsear {pattern}"
                    
                    st.warning("No se encontró Chapelco en el contenido")
                    # Buscar cualquier estación de Neuquén
                    if 'NEUQUEN' in contenido.upper():
                        st.write("⚠️ Encontrado NEUQUEN, buscando estaciones cercanas...")
                        neuquen_parte = contenido.upper().split('NEUQUEN')[1][:2000]
                        with st.expander("📋 Ver contenido cerca de NEUQUEN"):
                            st.text(neuquen_parte)
                    
                    return {}, False, "❌ SMN: No se encontraron datos de Chapelco"
        
        except zipfile.BadZipFile:
            st.warning("No es un archivo ZIP válido")
            # Intentar parsear como texto directo
            try:
                contenido = r.content.decode('utf-8', errors='ignore')
                st.write("Intentando parsear como texto directo...")
                with st.expander("📋 Ver contenido directo"):
                    st.text(contenido[:1000])
                
                # Buscar Chapelco
                if 'CHAPELCO' in contenido.upper():
                    return parsear_contenido_directo_smn(contenido), True, "✅ SMN: Datos obtenidos (directo)"
            except:
                pass
            
            return {}, False, "❌ SMN: Archivo no es ZIP válido"
        
    except requests.exceptions.Timeout:
        st.error("⚠️ Timeout al obtener SMN")
        return {}, False, "❌ SMN: Timeout en la conexión"
    except requests.exceptions.ConnectionError:
        st.error("⚠️ Error de conexión con SMN")
        return {}, False, "❌ SMN: Error de conexión"
    except Exception as e:
        st.error(f"⚠️ Error general SMN: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return {}, False, f"❌ Error SMN: {str(e)}"

def procesar_bloque_smn(bloque):
    """Convierte el texto SMN en datos estructurados"""
    if not bloque:
        return {}
    
    dias_datos = {}
    lineas = [l.strip() for l in bloque.split('\n') if l.strip()]
    
    st.write(f"📊 Líneas en bloque SMN: {len(lineas)}")
    
    for i, linea in enumerate(lineas[:20]):  # Limitar a 20 líneas para debugging
        st.write(f"Línea {i}: {linea}")
        
        # Múltiples patrones para detectar fechas
        patrones = [
            r'(\d{2})/([A-Z]{3})/(\d{4})',  # 01/ENE/2024
            r'(\d{2})-([A-Z]{3})-(\d{4})',  # 01-ENE-2024
            r'(\d{2})\s+([A-Z]{3})\s+(\d{4})',  # 01 ENE 2024
        ]
        
        for patron in patrones:
            match = re.search(patron, linea)
            if match:
                dia = match.group(1)
                mes = match.group(2)
                año = match.group(3)
                
                # Extraer temperatura (buscar número con decimales)
                temp_match = re.search(r'(-?\d+\.?\d*)', linea[match.end():])
                if temp_match:
                    temp = float(temp_match.group(1))
                    
                    # Extraer viento (buscar números después de | o km/h)
                    viento_match = re.search(r'\|.*?(\d+)', linea)
                    if not viento_match:
                        viento_match = re.search(r'(\d+)\s*km/h', linea)
                    
                    viento = int(viento_match.group(1)) if viento_match else 0
                    
                    try:
                        fecha_dt = datetime.strptime(f"{dia}/{mes}/{año}", '%d/%b/%Y')
                        fecha_str = fecha_dt.strftime('%d-%m-%Y')
                        
                        if fecha_str not in dias_datos:
                            dias_datos[fecha_str] = {
                                't_max': temp,
                                't_min': temp,
                                'v_max': viento,
                                'fecha_dt': fecha_dt.date()
                            }
                        else:
                            dias_datos[fecha_str]['t_max'] = max(dias_datos[fecha_str]['t_max'], temp)
                            dias_datos[fecha_str]['t_min'] = min(dias_datos[fecha_str]['t_min'], temp)
                            dias_datos[fecha_str]['v_max'] = max(dias_datos[fecha_str]['v_max'], viento)
                        
                        st.write(f"✅ Parseado: {fecha_str} - Temp: {temp} - Viento: {viento}")
                        
                    except ValueError as e:
                        st.warning(f"Error con fecha {dia}/{mes}/{año}: {e}")
                        continue
    
    st.write(f"📋 Total días SMN parseados: {len(dias_datos)}")
    return dias_datos

def parsear_smn_alternativo(bloque):
    """Método alternativo para parsear SMN"""
    try:
        # Buscar líneas con formato de pronóstico
        lineas = bloque.split('\n')
        datos = {}
        
        for linea in lineas:
            # Buscar algo como: "VIE 05/01 Tmax=28 Tmin=15"
            if any(dia in linea.upper() for dia in ['LUN', 'MAR', 'MIE', 'JUE', 'VIE', 'SAB', 'DOM']):
                # Extraer fecha
                fecha_match = re.search(r'(\d{2})/(\d{2})', linea)
                if fecha_match:
                    dia = fecha_match.group(1)
                    mes = fecha_match.group(2)
                    año = datetime.now().year
                    
                    # Extraer temperaturas
                    tmax_match = re.search(r'Tmax=(-?\d+\.?\d*)', linea)
                    tmin_match = re.search(r'Tmin=(-?\d+\.?\d*)', linea)
                    
                    if tmax_match and tmin_match:
                        try:
                            fecha_str = f"{dia}-{mes}-{año}"
                            fecha_dt = datetime.strptime(fecha_str, '%d-%m-%Y')
                            
                            datos[fecha_str] = {
                                't_max': float(tmax_match.group(1)),
                                't_min': float(tmin_match.group(1)),
                                'v_max': 0,  # No disponible
                                'fecha_dt': fecha_dt.date()
                            }
                        except:
                            continue
        
        return datos
    except:
        return {}

def parsear_contenido_directo_smn(contenido):
    """Parsear contenido directo (no ZIP)"""
    try:
        # Buscar sección de pronóstico
        if 'PRONOSTICO' in contenido.upper():
            partes = contenido.upper().split('PRONOSTICO')
            if len(partes) > 1:
                pronostico_texto = partes[1]
                return parsear_smn_alternativo(pronostico_texto)
    except:
        pass
    return {}

def obtener_datos_satelital(fecha_base):
    """Obtiene datos satelitales - DEVUELVE DATOS ESTRUCTURADOS Y ESTADO"""
    start_s = fecha_base.strftime("%Y-%m-%d")
    end_s = (fecha_base + timedelta(days=2)).strftime("%Y-%m-%d")
    
    try:
        st.write("🌐 Solicitando datos satelitales...")
        
        # Usar coordenadas de San Martín de los Andes
        url_sat = (f"https://api.open-meteo.com/v1/forecast?latitude=-40.1579&longitude=-71.3534"
                   f"&daily=temperature_2m_max,temperature_2m_min,windspeed_10m_max,windgusts_10m_max"
                   f"&timezone=America%2FArgentina%2FBuenos_Aires"
                   f"&start_date={start_s}&end_date={end_s}")
        
        st.write(f"🔗 URL Satélite: {url_sat}")
        
        response = requests.get(url_sat, timeout=15)
        st.write(f"📡 Status Satélite: {response.status_code}")
        
        datos_sat = response.json()
        
        if 'daily' in datos_sat:
            fechas = datos_sat['daily']['time']
            t_max = datos_sat['daily']['temperature_2m_max']
            t_min = datos_sat['daily']['temperature_2m_min']
            viento = datos_sat['daily']['windspeed_10m_max']
            rafagas = datos_sat['daily']['windgusts_10m_max']
            
            st.write(f"📅 Fechas satélite: {fechas}")
            st.write(f"🌡️ Temp max: {t_max}")
            st.write(f"🌡️ Temp min: {t_min}")
            st.write(f"💨 Viento: {viento}")
            st.write(f"🌪️ Ráfagas: {rafagas}")
            
            datos_finales = {}
            for i, fecha_str in enumerate(fechas):
                try:
                    fecha_dt = datetime.strptime(fecha_str, '%Y-%m-%d')
                    fecha_key = fecha_dt.strftime('%d-%m-%Y')
                    
                    if i < len(t_max) and i < len(t_min) and i < len(viento) and i < len(rafagas):
                        datos_finales[fecha_key] = {
                            't_max': t_max[i],
                            't_min': t_min[i],
                            'v_prom': viento[i],
                            'v_max': rafagas[i],
                            'fecha_dt': fecha_dt.date()
                        }
                        st.write(f"✅ Satélite {fecha_key}: {t_min[i]}°C/{t_max[i]}°C")
                except ValueError:
                    continue
            
            return datos_finales, True, f"✅ Satélite: {len(datos_finales)} días obtenidos"
        
        else:
            st.warning("No se encontró 'daily' en respuesta satélite")
            with st.expander("📋 Ver respuesta satélite completa"):
                st.json(datos_sat)
        
        return {}, False, "❌ Satélite: No se obtuvieron datos válidos"
        
    except Exception as e:
        st.error(f"❌ Error Satélite: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return {}, False, f"❌ Error Satélite: {str(e)}"

def fusionar_datos_manual(fecha_base, datos_aic, datos_smn, datos_sat, fuentes_estado):
    """Fusión manual de datos sin IA"""
    
    resultado = "## 📊 VERIFICACIÓN DE FUENTES - MODO DEBUG\n\n"
    
    resultado += f"**Fecha base:** {fecha_base.strftime('%d/%m/%Y')}\n\n"
    
    resultado += "### ✅ Fuentes activas:\n"
    for fuente, estado in fuentes_estado.items():
        if estado:
            resultado += f"🟢 {fuente}\n"
        else:
            resultado += f"🔴 {fuente}\n"
    
    # Resumen de datos por fuente
    resultado += "\n### 📈 Resumen de datos:\n"
    
    if datos_aic:
        resultado += f"**AIC:** {len(datos_aic)} días\n"
        for d in datos_aic[:3]:
            temp_info = f"{d.get('temp_min', 'N/D')}°C/{d.get('temp_max', 'N/D')}°C" if 'temp_min' in d or 'temp_max' in d else f"{d.get('temp', 'N/D')}°C"
            resultado += f"  - {d['fecha']} ({d['periodo']}): {d['condicion'][:30]}... | Temp: {temp_info}\n"
    else:
        resultado += "**AIC:** ❌ Sin datos\n"
    
    if datos_smn:
        resultado += f"\n**SMN:** {len(datos_smn)} días\n"
        for fecha, vals in list(datos_smn.items())[:3]:
            resultado += f"  - {fecha}: {vals['t_min']:.1f}°C/{vals['t_max']:.1f}°C | Viento: {vals['v_max']} km/h\n"
    else:
        resultado += "\n**SMN:** ❌ Sin datos\n"
    
    if datos_sat:
        resultado += f"\n**Satélite:** {len(datos_sat)} días\n"
        for fecha, vals in list(datos_sat.items())[:3]:
            resultado += f"  - {fecha}: {vals['t_min']:.1f}°C/{vals['t_max']:.1f}°C | Viento: {vals['v_prom']:.1f} km/h\n"
    else:
        resultado += "\n**Satélite:** ❌ Sin datos\n"
    
    # Síntesis simple si hay datos
    resultado += "\n---\n"
    resultado += "## 🧪 SÍNTESIS MANUAL (BÁSICA)\n\n"
    
    # Usar satélite como base (si está disponible)
    if datos_sat:
        resultado += "Basado en datos satelitales:\n"
        for fecha, vals in list(datos_sat.items())[:3]:
            # Buscar datos de AIC para esta fecha
            condicion_aic = "Parcialmente nublado"
            viento_aic = vals['v_prom']
            
            if datos_aic:
                for d in datos_aic:
                    if d['fecha'] == fecha:
                        condicion_aic = d['condicion']
                        if 'viento' in d and isinstance(d['viento'], str) and 'km/h' in d['viento']:
                            try:
                                viento_num = int(re.search(r'(\d+)', d['viento']).group(1))
                                viento_aic = max(viento_aic, viento_num)
                            except:
                                pass
            
            resultado += f"**{fecha}**: {condicion_aic}. Máx: {vals['t_max']:.1f}°C, Mín: {vals['t_min']:.1f}°C. Viento: {viento_aic:.1f} km/h\n"
    elif datos_aic:
        resultado += "Basado en datos AIC:\n"
        for d in datos_aic[:3]:
            resultado += f"**{d['fecha']} ({d['periodo']})**: {d['condicion']}. "
            if 'temp_max' in d and 'temp_min' in d:
                resultado += f"Temp: {d['temp_min']}°C/{d['temp_max']}°C\n"
            elif 'temp' in d:
                resultado += f"Temp: {d['temp']}°C\n"
            else:
                resultado += "\n"
    else:
        resultado += "⚠️ No hay datos suficientes para síntesis\n"
    
    resultado += "\n---\n"
    resultado += "**🔧 Estado:** Modo verificación - IA desactivada\n"
    
    return resultado

# --- INTERFAZ PRINCIPAL ---

st.title("🏔️ Sistema Climático SMA - DEBUG MODE")
st.caption("🔧 Modo diagnóstico - Verificando todas las fuentes")

st.sidebar.header("🗓️ Configuración")
fecha_base = st.sidebar.date_input("Fecha de inicio", datetime.now().date())

st.sidebar.divider()
st.sidebar.subheader("⚙️ Opciones de Debug")
mostrar_raw = st.sidebar.checkbox("Mostrar datos crudos", True)
modo_agresivo = st.sidebar.checkbox("Modo agresivo", False)

st.sidebar.divider()
st.sidebar.warning("⚠️ MODO DEBUG ACTIVADO")
st.sidebar.info("Este modo muestra todos los detalles técnicos para diagnosticar problemas.")

if st.button("🔬 EJECUTAR DIAGNÓSTICO COMPLETO", type="primary"):
    
    with st.spinner("Iniciando diagnóstico..."):
        # Inicializar estados
        fuentes_estado = {"AIC": False, "SMN": False, "SAT": False}
        mensajes_estado = {"AIC": "", "SMN": "", "SAT": ""}
        
        # Contenedor principal
        main_container = st.container()
        
        with main_container:
            st.subheader("📡 CAPTURA DE DATOS EN TIEMPO REAL")
            
            # Crear columnas para progreso
            col_prog1, col_prog2, col_prog3 = st.columns(3)
            
            with col_prog1:
                status_aic = st.empty()
                status_aic.info("⏳ Esperando AIC...")
            
            with col_prog2:
                status_smn = st.empty()
                status_smn.info("⏳ Esperando SMN...")
            
            with col_prog3:
                status_sat = st.empty()
                status_sat.info("⏳ Esperando Satélite...")
            
            # 1. AIC
            status_aic.warning("🔍 Capturando AIC...")
            datos_aic, fuentes_estado["AIC"], mensajes_estado["AIC"] = obtener_datos_aic(fecha_base)
            if fuentes_estado["AIC"]:
                status_aic.success(f"✅ AIC: {len(datos_aic)} días")
            else:
                status_aic.error(f"❌ AIC: {mensajes_estado['AIC']}")
            
            # 2. SMN
            status_smn.warning("🔍 Capturando SMN...")
            datos_smn, fuentes_estado["SMN"], mensajes_estado["SMN"] = obtener_datos_smn()
            if fuentes_estado["SMN"]:
                status_smn.success(f"✅ SMN: {len(datos_smn)} días")
            else:
                status_smn.error(f"❌ SMN: {mensajes_estado['SMN']}")
            
            # 3. Satélite
            status_sat.warning("🔍 Capturando Satélite...")
            datos_sat, fuentes_estado["SAT"], mensajes_estado["SAT"] = obtener_datos_satelital(fecha_base)
            if fuentes_estado["SAT"]:
                status_sat.success(f"✅ Satélite: {len(datos_sat)} días")
            else:
                status_sat.error(f"❌ Satélite: {mensajes_estado['SAT']}")
            
            # Resumen
            st.divider()
            st.subheader("📊 RESUMEN DEL DIAGNÓSTICO")
            
            # Mostrar fusión manual
            resultado = fusionar_datos_manual(fecha_base, datos_aic, datos_smn, datos_sat, fuentes_estado)
            st.markdown(resultado)
            
            # Mostrar datos crudos si está habilitado
            if mostrar_raw:
                st.divider()
                st.subheader("📋 DATOS CRUDOS PARA DEBUGGING")
                
                tabs = st.tabs(["AIC", "SMN", "SATÉLITE", "ESTADO"])
                
                with tabs[0]:
                    if datos_aic:
                        st.write(f"📁 {len(datos_aic)} registros AIC:")
                        for i, d in enumerate(datos_aic):
                            with st.expander(f"Registro AIC {i+1}: {d['fecha']} ({d['periodo']})"):
                                st.json(d)
                    else:
                        st.error("No hay datos AIC")
                
                with tabs[1]:
                    if datos_smn:
                        st.write(f"📁 {len(datos_smn)} días SMN:")
                        for fecha, vals in datos_smn.items():
                            with st.expander(f"Día SMN: {fecha}"):
                                st.json(vals)
                    else:
                        st.error("No hay datos SMN")
                
                with tabs[2]:
                    if datos_sat:
                        st.write(f"📁 {len(datos_sat)} días Satélite:")
                        for fecha, vals in datos_sat.items():
                            with st.expander(f"Día Satélite: {fecha}"):
                                st.json(vals)
                    else:
                        st.error("No hay datos Satélite")
                
                with tabs[3]:
                    st.write("**Estado de conexiones:**")
                    st.json(fuentes_estado)
                    
                    st.write("**Mensajes de estado:**")
                    st.json(mensajes_estado)
            
            # Recomendaciones
            st.divider()
            st.subheader("💡 RECOMENDACIONES")
            
            fuentes_activas = sum(fu
