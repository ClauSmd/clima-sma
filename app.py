import streamlit as st
import requests
import google.generativeai as genai
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

# 2. Configuración de Inteligencia
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except Exception as e:
    st.error(f"Error de API: {e}")

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
                
                # Convertir fecha a datetime
                try:
                    fecha_dt = datetime.strptime(fecha_str, '%d-%m-%Y')
                    
                    # Filtrar por fecha_base
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
                        'fecha_dt': fecha_dt
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
                            'fecha_dt': fecha_dt
                        }
                except ValueError:
                    continue
            
            return datos_finales, True, f"✅ Satélite: {len(datos_finales)} días obtenidos"
        
        return {}, False, "❌ Satélite: No se obtuvieron datos válidos"
        
    except Exception as e:
        return {}, False, f"❌ Error Satélite: {str(e)}"

def ejecutar_sintesis(prompt, datos_aic, datos_smn, datos_sat, fuentes_estado):
    """Ejecuta la síntesis con failover de modelos"""
    
    modelos = [
        ('gemini-3-flash-preview', 'Gemini 3 Flash'),
        ('gemini-2.5-flash-lite', 'Gemini 2.5 Flash Lite'),
        ('gemini-pro', 'Gemini Pro')
    ]
    
    for modelo_id, modelo_nombre in modelos:
        try:
            model_ai = genai.GenerativeModel(modelo_id)
            response = model_ai.generate_content(prompt)
            return response.text, modelo_nombre
        except Exception:
            continue
    
    return None, None

def preparar_prompt_ponderado(fecha_base, datos_aic, datos_smn, datos_sat, fuentes_estado):
    """Prepara el prompt para la ponderación 40/60"""
    
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
    
    INSTRUCCIONES DE PONDERACIÓN:
    
    1. ESTRATEGIA DE FUSIÓN 40/60:
       - 40%: Fuentes locales (AIC + SMN) para fenómenos específicos
       - 60%: Modelos satelitales para tendencia térmica
    
    2. PRIORIDAD LOCAL (40%):
       - Tormentas eléctricas (si AIC reporta "Eléctricas")
       - Ráfagas de viento > 30 km/h
       - Nevadas o precipitación sólida
       - Cambios bruscos reportados
    
    3. PRIORIDAD SATELITAL (60%):
       - Curva de temperaturas máximas/mínimas
       - Tendencia térmica diaria
       - Humedad y nubosidad base
    
    4. REGLAS DE DECISIÓN:
       a) TEMPERATURAS: Promedio ponderado
          - Si AIC y SMN coinciden: usar ese valor con peso 40%
          - Satélite: peso 60% para suavizar curva
       
       b) VIENTOS: Tomar el MÁXIMO reportado
          - AIC/SMN para ráfagas locales
          - Satélite para velocidad base
       
       c) CONDICIONES:
          - Si AIC reporta fenómeno específico (tormenta, lluvia): confirmar al 80%
          - Si solo satélite sugiere precipitación: probabilidad 40%
    
    5. FORMATO DE SALIDA (3 días máximo):
       [Emoji clima] [Día] de [Mes] – San Martín de los Andes: [condiciones fusionadas]. 
       Máxima de [temp_max_fusionada]°C, mínima de [temp_min_fusionada]°C. 
       Viento [viento_prom] km/h con ráfagas de [rafaga_max] km/h.
       
       [Emoji alerta] ALERTA: [Solo si condiciones extremas: ráfagas >45km/h, temp >30°C, tormenta eléctrica]
       
       #[SanMartínDeLosAndes] #ClimaSMA #PronósticoFusionado
       ---
    
    6. RESTRICCIONES:
       - NO inventar valores no respaldados por los datos
       - Si falta una fuente, ajustar ponderación proporcionalmente
       - Priorizar seguridad: si hay alerta potencial, mencionarla
       - Mantener lenguaje natural pero preciso
    """
    
    return prompt

# --- INTERFAZ ---

st.title("🏔️ Sintesis climatica sma V4.0")
st.caption("Sistema de ponderación AIC/SMN 40% + Satelital 60%")

st.sidebar.header("🗓️ Configuración")
fecha_base = st.sidebar.date_input("Fecha de inicio", datetime.now())

st.sidebar.divider()
st.sidebar.subheader("🔗 Calibración Local")
st.sidebar.info("Las fuentes se sincronizan automáticamente.")

if st.button("🚀 Generar síntesis ponderada", type="primary"):
    
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
    
    if fuentes_activas >= 2:
        status_text.text("🧠 Generando síntesis ponderada...")
        
        # 3. Preparar prompt con ponderación
        prompt = preparar_prompt_ponderado(
            fecha_base, datos_aic, datos_smn, datos_sat, fuentes_estado
        )
        
        # 4. Ejecutar síntesis con failover
        resultado, modelo_usado = ejecutar_sintesis(
            prompt, datos_aic, datos_smn, datos_sat, fuentes_estado
        )
        
        progress_bar.progress(100)
        status_text.text("✅ Síntesis completada")
        
        if resultado:
            # 5. Mostrar resultados
            st.markdown("---")
            st.subheader("📊 Pronóstico Ponderado (40/60)")
            st.markdown(f'<div class="reporte-final">{resultado}</div>', unsafe_allow_html=True)
            st.caption(f"🧠 Motor: {modelo_usado} | 🔄 Ponderación: 40% Local / 60% Satelital")
            
            # 6. Mostrar status de verdad
            with st.expander("🔍 Status de Verificación de Fuentes", expanded=False):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if fuentes_estado["AIC"]:
                        st.markdown('<p class="status-ok">✅ AIC ACTIVO</p>', unsafe_allow_html=True)
                        if datos_aic:
                            st.write(f"Días: {len(datos_aic)}")
                            for d in datos_aic[:2]:
                                st.caption(f"{d['fecha']}: {d['condicion'][:30]}...")
                    else:
                        st.markdown('<p class="status-error">❌ AIC INACTIVO</p>', unsafe_allow_html=True)
                    st.caption(mensajes_estado["AIC"])
                
                with col2:
                    if fuentes_estado["SMN"]:
                        st.markdown('<p class="status-ok">✅ SMN ACTIVO</p>', unsafe_allow_html=True)
                        if datos_smn:
                            st.write(f"Días: {len(datos_smn)}")
                            for fecha, vals in list(datos_smn.items())[:2]:
                                st.caption(f"{fecha}: {vals['t_min']:.1f}°C/{vals['t_max']:.1f}°C")
                    else:
                        st.markdown('<p class="status-error">❌ SMN INACTIVO</p>', unsafe_allow_html=True)
                    st.caption(mensajes_estado["SMN"])
                
                with col3:
                    if fuentes_estado["SAT"]:
                        st.markdown('<p class="status-ok">✅ SATÉLITE ACTIVO</p>', unsafe_allow_html=True)
                        if datos_sat:
                            st.write(f"Días: {len(datos_sat)}")
                            for fecha, vals in list(datos_sat.items())[:2]:
                                st.caption(f"{fecha}: {vals['t_min']:.1f}°C/{vals['t_max']:.1f}°C")
                    else:
                        st.markdown('<p class="status-error">❌ SATÉLITE INACTIVO</p>', unsafe_allow_html=True)
                    st.caption(mensajes_estado["SAT"])
                
                # Resumen de ponderación
                st.markdown("---")
                st.markdown("**📈 Estrategia de Ponderación Aplicada:**")
                
                if fuentes_activas == 3:
                    st.success("✅ Ponderación completa 40/60 (3/3 fuentes)")
                    st.markdown("- **40% AIC + SMN:** Fenómenos locales, tormentas, ráfagas")
                    st.markdown("- **60% Satélite:** Curva térmica, tendencias")
                elif fuentes_activas == 2:
                    st.warning("⚠️ Ponderación parcial (2/3 fuentes)")
                    if fuentes_estado["AIC"] and fuentes_estado["SMN"]:
                        st.markdown("- **60% AIC + SMN:** Solo fuentes locales")
                        st.markdown("- **40% Ajuste térmico:** Basado en patrones regionales")
                    else:
                        st.markdown("- Ponderación ajustada por fuentes disponibles")
                else:
                    st.error("❌ Ponderación insuficiente para fusión")
        
        else:
            st.error("❌ No se pudo generar la síntesis con ningún modelo disponible")
    
    else:
        progress_bar.progress(100)
        st.error("❌ No hay suficientes fuentes activas para la ponderación")
        st.info("Se requieren al menos 2 fuentes de datos. Estados:")
        
        for fuente, estado in fuentes_estado.items():
            if estado:
                st.success(f"✅ {fuente}: Activo - {mensajes_estado[fuente]}")
            else:
                st.error(f"❌ {fuente}: Inactivo - {mensajes_estado[fuente]}")

# Footer
st.markdown("---")
st.caption("Sistema de fusión meteorológica V4.0 | Ponderación 40/60 Local/Satelital")
