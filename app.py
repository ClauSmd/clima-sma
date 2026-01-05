import streamlit as st
import requests
from datetime import datetime, timedelta
import zipfile
import io
import re
import pdfplumber
import time

# 1. Configuración de Estética y Diseño Visual
st.set_page_config(page_title="Sintesis climatica sma", page_icon="🏔️", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .reporte-final { background-color: transparent; padding: 15px; font-size: 1.1rem; line-height: 1.6; color: #f0f2f6; }
    hr { margin: 1.5rem 0; border: 0; border-top: 1px solid #444; }
    .status-ok { color: #00cc00; }
    .status-error { color: #ff4444; }
    .status-warning { color: #ffaa00; }
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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/pdf, */*',
        'Accept-Language': 'es-ES,es;q=0.9',
    }
    
    for url_idx, url in enumerate(urls):
        for intento in range(2):
            try:
                response = requests.get(url, headers=headers, verify=False, timeout=30)
                
                if response.status_code != 200:
                    continue
                
                if response.content[:4] == b'%PDF':
                    with pdfplumber.open(io.BytesIO(response.content)) as pdf:
                        texto = pdf.pages[0].extract_text()
                        
                        if texto and len(texto.strip()) > 100:
                            # Parsear datos estructurados
                            datos_parsed = parsear_aic_texto(texto, fecha_base)
                            if datos_parsed:
                                return datos_parsed, True, f"✅ AIC: {len(datos_parsed)} días obtenidos"
                            else:
                                return [], False, "❌ AIC: No se pudieron parsear los datos"
                
                time.sleep(1)
                
            except Exception:
                continue
    
    return [], False, "❌ AIC: No se pudo obtener el PDF"

def parsear_aic_texto(texto, fecha_base):
    """Parsea el texto del PDF de AIC y extrae datos estructurados"""
    try:
        lineas = [line.strip() for line in texto.split('\n') if line.strip()]
        
        if len(lineas) < 10:
            return []
        
        # Extraer datos del PDF
        fechas_line = lineas[1]
        todas_fechas = fechas_line.split()
        
        periodos_line = lineas[2]
        periodos = periodos_line.split()
        
        # Temperaturas
        temps = re.findall(r'(-?\d+)\s*[ºC°C]', lineas[7])
        temps = [float(t) for t in temps]
        
        # Viento
        winds = re.findall(r'(\d+)\s*km/h', lineas[8])
        winds = [int(w) for w in winds]
        
        # Ráfagas
        gusts = re.findall(r'(\d+)\s*km/h', lineas[9])
        gusts = [int(g) for g in gusts]
        
        # Dirección
        dirs = lineas[10].replace('Dirección', '').strip().split()
        
        # Presión
        pres = re.findall(r'(\d+)\s*hPa', lineas[11])
        pres = [int(p) for p in pres]
        
        # Condiciones del cielo
        cond_text = ' '.join(lineas[3:7]).replace('Cielo', '').strip()
        palabras = cond_text.split()
        condiciones = []
        actual = []
        
        for p in palabras:
            if any(p.startswith(k[:4]) for k in ['Mayor', 'Despej', 'Nubl', 'Torment', 'Lluv', 'Eléctr', 'Inest', 'Parcial']):
                actual.append(p)
                if p.endswith(','):
                    condiciones.append(' '.join(actual))
                    actual = []
            elif actual:
                condiciones.append(' '.join(actual))
                actual = []
        
        if actual:
            condiciones.append(' '.join(actual))
        
        # Crear estructura de datos
        datos = []
        fecha_actual = None
        
        for i in range(len(periodos)):
            fecha_idx = i // 2 * 2
            if fecha_idx < len(todas_fechas):
                fecha_str = todas_fechas[fecha_idx]
                
                # Convertir fecha a datetime.date para comparación
                try:
                    fecha_dt = datetime.strptime(fecha_str, '%d-%m-%Y').date()
                    
                    # CORREGIDO: Comparar date con date
                    if fecha_dt >= fecha_base:
                        if fecha_str != fecha_actual:  # Nuevo día
                            # Para día
                            if periodos[i] == 'Día' and i < len(temps):
                                datos.append({
                                    'fecha': fecha_str,
                                    'fecha_dt': fecha_dt,
                                    'temp_max': temps[i] if i < len(temps) else None,
                                    'temp_min': temps[i+1] if i+1 < len(temps) else None,
                                    'viento': f"{winds[i]} {dirs[i]}" if i < len(winds) and i < len(dirs) else f"{winds[i]} km/h" if i < len(winds) else "N/D",
                                    'rafagas': gusts[i] if i < len(gusts) else None,
                                    'presion': pres[i] if i < len(pres) else None,
                                    'condicion': condiciones[i] if i < len(condiciones) else "Datos AIC",
                                    'periodo': 'Día'
                                })
                            # Para noche (siguiente registro)
                            elif i+1 < len(periodos) and periodos[i+1] == 'Noche':
                                datos.append({
                                    'fecha': fecha_str,
                                    'fecha_dt': fecha_dt,
                                    'temp_max': temps[i] if i < len(temps) else None,  # Temp del día como max
                                    'temp_min': temps[i+1] if i+1 < len(temps) else None,  # Temp de noche como min
                                    'viento': f"{winds[i+1]} {dirs[i+1]}" if i+1 < len(winds) and i+1 < len(dirs) else f"{winds[i+1]} km/h" if i+1 < len(winds) else "N/D",
                                    'rafagas': gusts[i+1] if i+1 < len(gusts) else None,
                                    'presion': pres[i+1] if i+1 < len(pres) else None,
                                    'condicion': condiciones[i+1] if i+1 < len(condiciones) else "Datos AIC",
                                    'periodo': 'Noche'
                                })
                            
                            fecha_actual = fecha_str
                
                except ValueError:
                    continue
        
        # Limitar a 3 días desde fecha_base
        datos_filtrados = []
        for dia in datos:
            if len(datos_filtrados) >= 3:
                break
            datos_filtrados.append(dia)
        
        return datos_filtrados
        
    except Exception as e:
        st.warning(f"Error parseando AIC: {e}")
        return []

def obtener_datos_smn():
    """Obtiene datos de SMN - DEVUELVE DATOS ESTRUCTURADOS Y ESTADO"""
    url = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=pron5d"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            nombre_txt = [f for f in z.namelist() if f.endswith('.txt')][0]
            with z.open(nombre_txt) as f:
                contenido = f.read().decode('utf-8', errors='ignore')
                if "CHAPELCO_AERO" in contenido:
                    bloque = contenido.split("CHAPELCO_AERO")[1].split("=")[0]
                    datos_smn = procesar_bloque_smn(bloque)
                    if datos_smn:
                        return datos_smn, True, f"✅ SMN: {len(datos_smn)} días obtenidos"
        
        return {}, False, "❌ SMN: No se encontraron datos de Chapelco"
        
    except Exception as e:
        return {}, False, f"❌ Error SMN: {str(e)}"

def procesar_bloque_smn(bloque):
    """Convierte el texto SMN en datos estructurados"""
    if not bloque:
        return {}
    
    dias_datos = {}
    lineas = bloque.strip().split('\n')
    
    for linea in lineas:
        # Mejor regex para SMN
        match = re.search(r'(\d{2})/([A-Z]{3})/(\d{4}).*?(\d+\.?\d*).*?\|.*?(\d+)', linea)
        if match:
            dia = match.group(1)
            mes = match.group(2)
            año = match.group(3)
            fecha_key = f"{dia} {mes} {año}"
            
            # Convertir a fecha datetime
            try:
                fecha_dt = datetime.strptime(f"{dia}/{mes}/{año}", '%d/%b/%Y')
                fecha_str = fecha_dt.strftime('%d-%m-%Y')
                
                temp = float(match.group(4))
                viento = int(match.group(5))
                
                if fecha_str not in dias_datos:
                    dias_datos[fecha_str] = {
                        't_max': temp,
                        't_min': temp,
                        'v_max': viento,
                        'fecha_dt': fecha_dt.date()  # Convertir a date
                    }
                else:
                    dias_datos[fecha_str]['t_max'] = max(dias_datos[fecha_str]['t_max'], temp)
                    dias_datos[fecha_str]['t_min'] = min(dias_datos[fecha_str]['t_min'], temp)
                    dias_datos[fecha_str]['v_max'] = max(dias_datos[fecha_str]['v_max'], viento)
            except ValueError:
                continue
    
    return dias_datos

def obtener_datos_satelital(fecha_base):
    """Obtiene datos satelitales - DEVUELVE DATOS ESTRUCTURADOS Y ESTADO"""
    start_s = fecha_base.strftime("%Y-%m-%d")
    end_s = (fecha_base + timedelta(days=2)).strftime("%Y-%m-%d")
    
    try:
        url_sat = (f"https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35"
                   f"&daily=temperature_2m_max,temperature_2m_min,windspeed_10m_max,windgusts_10m_max"
                   f"&timezone=America%2FArgentina%2FBuenos_Aires&start_date={start_s}&end_date={end_s}")
        
        response = requests.get(url_sat, timeout=15)
        datos_sat = response.json()
        
        if 'daily' in datos_sat:
            fechas = datos_sat['daily']['time']
            t_max = datos_sat['daily']['temperature_2m_max']
            t_min = datos_sat['daily']['temperature_2m_min']
            viento = datos_sat['daily']['windspeed_10m_max']
            rafagas = datos_sat['daily']['windgusts_10m_max']
            
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
                            'fecha_dt': fecha_dt.date()  # Convertir a date
                        }
                except ValueError:
                    continue
            
            return datos_finales, True, f"✅ Satélite: {len(datos_finales)} días obtenidos"
        
        return {}, False, "❌ Satélite: No se obtuvieron datos válidos"
        
    except Exception as e:
        return {}, False, f"❌ Error Satélite: {str(e)}"

def fusionar_datos_manual(fecha_base, datos_aic, datos_smn, datos_sat, fuentes_estado):
    """Fusión manual de datos sin IA - solo para verificación"""
    
    # Preparar resultado simple
    resultado = "## 📊 VERIFICACIÓN DE FUENTES\n\n"
    
    resultado += f"**Fecha base:** {fecha_base.strftime('%d/%m/%Y')}\n\n"
    
    resultado += "### Fuentes activas:\n"
    for fuente, estado in fuentes_estado.items():
        if estado:
            resultado += f"✅ {fuente}\n"
        else:
            resultado += f"❌ {fuente}\n"
    
    resultado += "\n### Datos disponibles:\n"
    
    # AIC
    if datos_aic:
        resultado += "**AIC:**\n"
        for d in datos_aic[:3]:
            resultado += f"- {d['fecha']}: {d['condicion'][:40]}... | Temp: {d.get('temp_min', 'N/D')}°C/{d.get('temp_max', 'N/D')}°C\n"
    else:
        resultado += "**AIC:** Sin datos\n"
    
    # SMN
    if datos_smn:
        resultado += "\n**SMN:**\n"
        for fecha, vals in list(datos_smn.items())[:3]:
            resultado += f"- {fecha}: {vals['t_min']:.1f}°C/{vals['t_max']:.1f}°C | Viento: {vals['v_max']} km/h\n"
    else:
        resultado += "\n**SMN:** Sin datos\n"
    
    # Satélite
    if datos_sat:
        resultado += "\n**Satélite:**\n"
        for fecha, vals in list(datos_sat.items())[:3]:
            resultado += f"- {fecha}: {vals['t_min']:.1f}°C/{vals['t_max']:.1f}°C | Viento: {vals['v_prom']:.1f} km/h (ráf: {vals['v_max']:.1f} km/h)\n"
    else:
        resultado += "\n**Satélite:** Sin datos\n"
    
    resultado += "\n---\n"
    resultado += "**Estado:** Modo verificación - IA desactivada\n"
    resultado += "Cuando todas las fuentes funcionen, activar la IA para la síntesis completa."
    
    return resultado

def preparar_prompt_ponderado(fecha_base, datos_aic, datos_smn, datos_sat, fuentes_estado):
    """Prepara el prompt para la ponderación 40/60 - SOLO PARA REFERENCIA"""
    
    # Formatear datos para el prompt
    datos_aic_str = "No disponible"
    if datos_aic:
        datos_aic_str = "\n".join([
            f"  - {d['fecha']} ({d['periodo']}): {d['condicion']}. "
            f"Temp: {d.get('temp_min', 'N/D')}°C/{d.get('temp_max', 'N/D')}°C. "
            f"Viento: {d.get('viento', 'N/D')}"
            for d in datos_aic
        ])
    
    datos_smn_str = "No disponible"
    if datos_smn:
        datos_smn_str = "\n".join([
            f"  - {fecha}: Temp: {vals['t_min']:.1f}°C/{vals['t_max']:.1f}°C. "
            f"Viento máx: {vals['v_max']} km/h"
            for fecha, vals in datos_smn.items()
        ])
    
    datos_sat_str = "No disponible"
    if datos_sat:
        datos_sat_str = "\n".join([
            f"  - {fecha}: Temp: {vals['t_min']:.1f}°C/{vals['t_max']:.1f}°C. "
            f"Viento: {vals['v_prom']:.1f} km/h (ráf: {vals['v_max']:.1f} km/h)"
            for fecha, vals in datos_sat.items()
        ])
    
    prompt = f"""
    SISTEMA DE PONDERACIÓN METEOROLÓGICA - SAN MARTÍN DE LOS ANDES
    
    FECHA BASE: {fecha_base.strftime('%A %d de %B %Y')}
    
    FUENTES DISPONIBLES:
    - AIC (Oficial Argentina): {'✅ ACTIVA' if fuentes_estado['AIC'] else '❌ INACTIVA'}
    - SMN Chapelco (Oficial): {'✅ ACTIVA' if fuentes_estado['SMN'] else '❌ INACTIVA'}
    - Modelos Satelitales: {'✅ ACTIVA' if fuentes_estado['SAT'] else '❌ INACTIVA'}
    
    DATOS CRUDOS POR FUENTE:
    
    AIC (40% peso - fenómenos locales):
    {datos_aic_str}
    
    SMN Chapelco (40% peso - datos oficiales):
    {datos_smn_str}
    
    Satélites (60% peso - curva térmica):
    {datos_sat_str}
    
    [CONTINUACIÓN DEL PROMPT...]
    """
    
    return prompt

# --- INTERFAZ ---

st.title("🏔️ Sintesis climatica sma V4.0")
st.caption("MODO VERIFICACIÓN - IA DESACTIVADA")

st.sidebar.header("🗓️ Configuración")
fecha_base = st.sidebar.date_input("Fecha de inicio", datetime.now().date())

st.sidebar.divider()
st.sidebar.subheader("🔗 Calibración Local")
st.sidebar.info("Las fuentes se sincronizan automáticamente.")

st.sidebar.warning("⚠️ IA DESACTIVADA")
st.sidebar.caption("Activar solo cuando todas las fuentes funcionen correctamente.")

if st.button("🔍 Verificar fuentes de datos", type="primary"):
    
    # Inicializar estados
    fuentes_estado = {"AIC": False, "SMN": False, "SAT": False}
    mensajes_estado = {"AIC": "", "SMN": "", "SAT": ""}
    
    # Contenedor para progreso
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # 1. Capturar datos de todas las fuentes
    status_text.text("📡 Capturando datos AIC...")
    datos_aic, fuentes_estado["AIC"], mensajes_estado["AIC"] = obtener_datos_aic(fecha_base)
    progress_bar.progress(30)
    
    status_text.text("📡 Capturando datos SMN...")
    datos_smn, fuentes_estado["SMN"], mensajes_estado["SMN"] = obtener_datos_smn()
    progress_bar.progress(60)
    
    status_text.text("📡 Capturando datos satelitales...")
    datos_sat, fuentes_estado["SAT"], mensajes_estado["SAT"] = obtener_datos_satelital(fecha_base)
    progress_bar.progress(90)
    
    # 2. Verificar que tenemos datos suficientes
    fuentes_activas = sum(fuentes_estado.values())
    
    if fuentes_activas >= 1:
        status_text.text("📊 Mostrando resultados de verificación...")
        
        # 3. Mostrar fusión manual
        resultado = fusionar_datos_manual(
            fecha_base, datos_aic, datos_smn, datos_sat, fuentes_estado
        )
        
        progress_bar.progress(100)
        status_text.text("✅ Verificación completada")
        
        # 4. Mostrar resultados
        st.markdown("---")
        st.markdown(resultado)
        
        # 5. Mostrar status de verdad
        with st.expander("🔍 Detalles técnicos de cada fuente", expanded=False):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if fuentes_estado["AIC"]:
                    st.markdown('<p class="status-ok">✅ AIC ACTIVO</p>', unsafe_allow_html=True)
                    if datos_aic:
                        st.write(f"Días obtenidos: {len(datos_aic)}")
                        for d in datos_aic[:3]:
                            st.caption(f"**{d['fecha']}** ({d['periodo']})")
                            st.caption(f"Cond: {d['condicion'][:50]}...")
                            st.caption(f"Temp: {d.get('temp_min', 'N/D')}°C/{d.get('temp_max', 'N/D')}°C")
                else:
                    st.markdown('<p class="status-error">❌ AIC INACTIVO</p>', unsafe_allow_html=True)
                st.caption(mensajes_estado["AIC"])
            
            with col2:
                if fuentes_estado["SMN"]:
                    st.markdown('<p class="status-ok">✅ SMN ACTIVO</p>', unsafe_allow_html=True)
                    if datos_smn:
                        st.write(f"Días obtenidos: {len(datos_smn)}")
                        for fecha, vals in list(datos_smn.items())[:3]:
                            st.caption(f"**{fecha}**")
                            st.caption(f"Temp: {vals['t_min']:.1f}°C/{vals['t_max']:.1f}°C")
                            st.caption(f"Viento: {vals['v_max']} km/h")
                else:
                    st.markdown('<p class="status-error">❌ SMN INACTIVO</p>', unsafe_allow_html=True)
                st.caption(mensajes_estado["SMN"])
            
            with col3:
                if fuentes_estado["SAT"]:
                    st.markdown('<p class="status-ok">✅ SATÉLITE ACTIVO</p>', unsafe_allow_html=True)
                    if datos_sat:
                        st.write(f"Días obtenidos: {len(datos_sat)}")
                        for fecha, vals in list(datos_sat.items())[:3]:
                            st.caption(f"**{fecha}**")
                            st.caption(f"Temp: {vals['t_min']:.1f}°C/{vals['t_max']:.1f}°C")
                            st.caption(f"Viento: {vals['v_prom']:.1f} km/h")
                else:
                    st.markdown('<p class="status-error">❌ SATÉLITE INACTIVO</p>', unsafe_allow_html=True)
                st.caption(mensajes_estado["SAT"])
            
            # Resumen
            st.markdown("---")
            st.markdown("**📈 Estado de fuentes:**")
            
            if fuentes_activas == 3:
                st.success("✅ Todas las fuentes funcionando correctamente")
                st.info("Ya puedes activar la IA para la síntesis completa")
            elif fuentes_activas == 2:
                st.warning("⚠️ 2 de 3 fuentes activas")
                if not fuentes_estado["AIC"]:
                    st.error("Problema con AIC - verificar PDF disponible")
                elif not fuentes_estado["SMN"]:
                    st.error("Problema con SMN - verificar conexión")
                else:
                    st.error("Problema con Satélite - verificar API")
            else:
                st.error("❌ Solo 1 fuente activa - verificar conexiones")
        
        # Mostrar datos crudos para debugging
        with st.expander("📋 Datos crudos para debugging", expanded=False):
            tab1, tab2, tab3 = st.tabs(["AIC", "SMN", "Satélite"])
            
            with tab1:
                if datos_aic:
                    for d in datos_aic:
                        st.json(d)
                else:
                    st.write("Sin datos AIC")
            
            with tab2:
                if datos_smn:
                    st.json(datos_smn)
                else:
                    st.write("Sin datos SMN")
            
            with tab3:
                if datos_sat:
                    st.json(datos_sat)
                else:
                    st.write("Sin datos Satélite")
    
    else:
        progress_bar.progress(100)
        st.error("❌ No se pudo obtener datos de ninguna fuente")
        st.info("Estados individuales:")
        
        for fuente, estado in fuentes_estado.items():
            st.error(f"❌ {fuente}: {mensajes_estado[fuente]}")
        
        st.warning("""
        Posibles soluciones:
        1. Verificar conexión a internet
        2. AIC: El PDF puede no estar disponible temporalmente
        3. SMN: El servidor puede estar caído
        4. Satélite: La API de Open-Meteo puede tener problemas
        """)

# Footer
st.markdown("---")
st.caption("Sistema de verificación V4.0 | Modo sin IA - Para debugging")

# Información adicional
with st.expander("ℹ️ Instrucciones para activar IA"):
    st.markdown("""
    **Para activar la IA una vez que todo funcione:**
    
    1. **Corregir el error de fechas:** Ya corregido en este código
    2. **Verificar que las 3 fuentes funcionen:** Usa el botón "Verificar fuentes de datos"
    3. **Agregar la clave API de Google:** En `st.secrets["GOOGLE_API_KEY"]`
    4. **Restaurar las funciones de IA:** Descomentar:
       - `import google.generativeai as genai`
       - `ejecutar_sintesis()`
       - Configuración de API al inicio
    5. **Cambiar el botón:** De "Verificar" a "Generar síntesis ponderada"
    
    **Errores comunes solucionados:**
    - ✅ `'datetime.datetime' and 'datetime.date' comparison` - Corregido
    - ✅ Configuración redundante de IA - Eliminada
    """)
