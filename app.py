import streamlit as st
import requests
import time
from datetime import datetime, timedelta
import zipfile
import io
import pdfplumber
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 1. Configuración de Estética
st.set_page_config(page_title="Debug de Fuentes SMA", page_icon="🔍")

# --- FUNCIONES DE SCRAPING ---

def obtener_datos_smn():
    url = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=pron5d"
    try:
        r = requests.get(url, timeout=15)
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            nombre_txt = [f for f in z.namelist() if f.endswith('.txt')][0]
            with z.open(nombre_txt) as f:
                contenido = f.read().decode('utf-8', errors='ignore')
                if "CHAPELCO_AERO" in contenido:
                    return contenido.split("CHAPELCO_AERO")[1].split("=")[0].strip()
        return "❌ Chapelco Aero no encontrado."
    except Exception as e:
        return f"❌ Error SMN: {e}"

def obtener_datos_aic_sync():
    """Obtiene datos de AIC con manejo robusto de errores"""
    # URLs alternativas - probamos diferentes formatos
    urls = [
        "https://www.aic.gob.ar/sitio/extendido-pdf?a=1029&z=1750130550",  # URL original con timestamp
        "https://www.aic.gob.ar/sitio/extendido-pdf?id_localidad=22&id_pronostico=1",  # URL con IDs
        "https://www.aic.gob.ar/sitio/extendido-pdf?localidad=22&pronostico=1",  # Variante
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Accept': 'application/pdf, text/html, application/xhtml+xml, */*',
        'Accept-Language': 'es-ES,es;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache'
    }
    
    for url_idx, url in enumerate(urls):
        st.info(f"🔍 Intentando URL {url_idx + 1}: {url}")
        
        for intento in range(2):  # 2 intentos por URL
            try:
                # Hacer la solicitud
                response = requests.get(
                    url, 
                    headers=headers, 
                    verify=False, 
                    timeout=30,
                    allow_redirects=True
                )
                
                # DEBUG: Mostrar información de la respuesta
                st.write(f"  Intento {intento + 1}: Status {response.status_code}, Tamaño: {len(response.content)} bytes")
                
                # Verificar que sea un PDF (mira los primeros bytes)
                if response.content[:4] == b'%PDF':
                    try:
                        # Intentar abrir como PDF
                        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
                            texto = pdf.pages[0].extract_text()
                            if texto and len(texto.strip()) > 100:
                                st.success(f"✅ PDF válido obtenido de URL {url_idx + 1}")
                                return texto
                            else:
                                st.warning("  PDF vacío o con poco texto")
                    except Exception as pdf_error:
                        st.warning(f"  Error al leer PDF: {pdf_error}")
                        # Guardar el contenido para análisis
                        with open(f"aic_error_{url_idx}.bin", "wb") as f:
                            f.write(response.content[:1000])
                
                # Si no es PDF, mostrar lo que es
                else:
                    content_start = response.content[:500].decode('utf-8', errors='ignore')
                    if '<!DOCTYPE html>' in content_start or '<html' in content_start:
                        st.warning("  El servidor devolvió HTML, no PDF")
                        # Intentar extraer mensaje de error del HTML
                        if 'Error' in content_start or 'error' in content_start:
                            error_msg = re.search(r'<title>(.*?)</title>', content_start, re.IGNORECASE)
                            if error_msg:
                                return f"❌ Error AIC: {error_msg.group(1)}"
                    else:
                        st.warning(f"  Formato desconocido. Inicio: {content_start[:100]}...")
                
                time.sleep(1)  # Pequeña pausa entre intentos
                
            except requests.exceptions.Timeout:
                st.warning(f"  Timeout en URL {url_idx + 1}")
            except Exception as e:
                st.warning(f"  Error general: {str(e)[:100]}")
    
    # Si todas las URLs fallaron
    return "❌ Error: No se pudo obtener un PDF válido de AIC. Posibles causas:\n" \
           "1. El servidor de AIC está caído\n" \
           "2. La URL ha cambiado\n" \
           "3. Requiere autenticación o cookies de sesión\n" \
           "4. Bloqueo por geolocalización"

def obtener_satelital(fecha_inicio):
    start = fecha_inicio.strftime("%Y-%m-%d")
    end = (fecha_inicio + timedelta(days=5)).strftime("%Y-%m-%d")
    url = (f"https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35"
           f"&daily=temperature_2m_max,temperature_2m_min,windspeed_10m_max,windgusts_10m_max"
           f"&timezone=America%2FArgentina%2FBuenos_Aires&start_date={start}&end_date={end}")
    try:
        return requests.get(url, timeout=15).json()
    except Exception as e:
        return {"error": str(e)}

# --- INTERFAZ ---
st.title("🔍 Verificador de Datos SMA")
fecha_base = st.sidebar.date_input("Fecha de inicio", datetime.now())

if st.button("🧪 PROBAR TODAS LAS FUENTES"):
    st.info("🔍 Iniciando prueba de todas las fuentes...")
    
    with st.status("Solicitando datos SMN...") as status:
        smn_res = obtener_datos_smn()
        status.update(label=f"SMN: {'✅ OK' if '❌' not in smn_res else '❌ Error'}", state="running")
    
    with st.status("Solicitando datos AIC...") as status:
        aic_res = obtener_datos_aic_sync()
        status.update(label=f"AIC: {'✅ OK' if '❌' not in aic_res else '❌ Error'}", state="running")
    
    with st.status("Solicitando datos satelitales...") as status:
        sat_res = obtener_satelital(fecha_base)
        status.update(label=f"Satélite: {'✅ OK' if 'error' not in sat_res else '❌ Error'}", state="complete")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📡 SMN")
        if "❌" not in smn_res:
            st.success("✅ CONEXIÓN EXITOSA")
            st.text_area("Datos obtenidos:", smn_res, height=200)
        else: 
            st.error("❌ FALLÓ LA CONEXIÓN")
            st.text(smn_res)
            
    with col2:
        st.subheader("📄 AIC")
        if "❌" not in aic_res:
            st.success("✅ CONEXIÓN EXITOSA")
            st.text_area("Datos obtenidos:", aic_res, height=200)
            
            # Mostrar análisis del contenido
            if "Temperatura" in aic_res:
                st.info("📊 Análisis rápido:")
                lineas = aic_res.split('\n')
                for i, linea in enumerate(lineas[:10]):
                    st.write(f"{i}: {linea[:80]}{'...' if len(linea) > 80 else ''}")
        else: 
            st.error("❌ FALLÓ LA CONEXIÓN")
            st.text(aic_res)

    st.subheader("🌍 Modelos Satelitales (Open-Meteo)")
    if "daily" in sat_res:
        st.success("✅ CONEXIÓN EXITOSA")
        
        # Mostrar datos en tabla
        if "time" in sat_res["daily"]:
            import pandas as pd
            datos = {
                "Fecha": sat_res["daily"]["time"],
                "Temp Máx (°C)": sat_res["daily"]["temperature_2m_max"],
                "Temp Mín (°C)": sat_res["daily"]["temperature_2m_min"],
                "Viento (km/h)": sat_res["daily"]["windspeed_10m_max"],
                "Ráfagas (km/h)": sat_res["daily"]["windgusts_10m_max"]
            }
            df = pd.DataFrame(datos)
            st.dataframe(df, use_container_width=True)
    else: 
        st.error("❌ FALLÓ LA CONEXIÓN")
        st.json(sat_res)
    
    # Resumen
    st.markdown("---")
    st.subheader("📈 RESUMEN DE CONEXIONES")
    
    conexiones_ok = 0
    if "❌" not in smn_res: conexiones_ok += 1
    if "❌" not in aic_res: conexiones_ok += 1
    if "daily" in sat_res: conexiones_ok += 1
    
    if conexiones_ok == 3:
        st.success(f"✅ {conexiones_ok}/3 fuentes funcionando correctamente")
    elif conexiones_ok >= 1:
        st.warning(f"⚠️ {conexiones_ok}/3 fuentes funcionando")
    else:
        st.error(f"❌ {conexiones_ok}/3 fuentes funcionando")
