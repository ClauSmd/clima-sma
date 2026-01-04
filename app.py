import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime, timedelta
import zipfile
import io
import pdfplumber
import re
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 1. Configuración de Estética
st.set_page_config(page_title="Sintesis Climática SMA", page_icon="🏔️")

# 2. Configuración de API - DESCOMENTA ESTO PARA USAR LA IA
# genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

def obtener_datos_smn():
    url = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=pron5d"
    try:
        r = requests.get(url, timeout=15)
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            nombre_txt = [f for f in z.namelist() if f.endswith('.txt')][0]
            with z.open(nombre_txt) as f:
                return f.read().decode('utf-8', errors='ignore').split("CHAPELCO_AERO")[1].split("=")[0]
    except: return None

def obtener_datos_aic_sync():
    """Obtiene datos del PDF de AIC - VERSIÓN CORREGIDA"""
    # URLs alternativas por si una falla
    urls = [
        "https://www.aic.gob.ar/sitio/extendido-pdf?a=1029&z=1750130550",  # URL original con parámetros
        "https://www.aic.gob.ar/sitio/extendido-pdf?id_localidad=22&id_pronostico=1",  # URL alternativa
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/pdf, */*',
        'Referer': 'https://www.aic.gob.ar/'
    }
    
    for url in urls:
        try:
            # Intentar descargar el PDF
            response = requests.get(url, headers=headers, verify=False, timeout=30)
            
            if response.status_code != 200:
                continue  # Intentar con la siguiente URL
            
            pdf_bytes = response.content
            
            # Verificar que sea un PDF válido (mínimo 1000 bytes)
            if len(pdf_bytes) < 1000:
                continue
            
            # Extraer texto del PDF
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                texto = pdf.pages[0].extract_text()
                
                if texto and len(texto) > 100:  # Verificar que haya texto suficiente
                    return texto
            
        except Exception as e:
            continue  # Intentar con la siguiente URL
    
    # Si todas las URLs fallan
    return "Error: No se pudo obtener el pronóstico de AIC. El servidor puede estar temporalmente no disponible."

def obtener_satelital(fecha_inicio):
    start = fecha_inicio.strftime("%Y-%m-%d")
    end = (fecha_inicio + timedelta(days=5)).strftime("%Y-%m-%d")
    url = (f"https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35"
           f"&daily=temperature_2m_max,temperature_2m_min,windspeed_10m_max,windgusts_10m_max"
           f"&timezone=America%2FArgentina%2FBuenos_Aires&start_date={start}&end_date={end}")
    return requests.get(url).json()

# --- INTERFAZ ---
st.title("🏔️ Síntesis Climática SMA")
fecha_base = st.sidebar.date_input("Fecha de inicio", datetime.now())

if st.button("🚀 Generar Reporte"):
    with st.status("Sincronizando fuentes locales...") as status:
        smn = obtener_datos_smn()
        aic = obtener_datos_aic_sync()
        sat = obtener_satelital(fecha_base)
        status.update(label="Datos obtenidos. Procesando...", state="complete")

    # MODO TEST: Si quieres ver los datos crudos antes de gastar IA
    with st.expander("Ver datos crudos (Debug)"):
        st.write("**SMN:**")
        st.text(smn[:500] + "..." if smn and len(smn) > 500 else smn)
        
        st.write("**AIC:**")
        st.text(aic[:500] + "..." if aic and len(aic) > 500 else aic)
        
        st.write("**SAT:**")
        st.json(sat)

    # --- BLOQUE DE IA (DESCOMENTAR CUANDO AIC DE 'OK') ---
    # prompt = f"FECHA: {fecha_base}. DATOS: AIC:{aic}, SMN:{smn}, SAT:{sat}. TAREA: Generar sintesis de 6 días estilo: 'Sábado 20 de Diciembre – San Martín de los Andes: tiempo estable...'"
    # model = genai.GenerativeModel('gemini-1.5-flash')
    # res = model.generate_content(prompt)
    # st.markdown(res.text)
    
    # Mostrar datos parseados del AIC
    if aic and not aic.startswith("Error:"):
        st.subheader("📊 Datos Parseados del AIC")
        
        # Intentar parsear el texto del PDF
        lineas = [line.strip() for line in aic.split('\n') if line.strip()]
        
        if len(lineas) >= 13:
            try:
                # Fechas
                fechas_line = lineas[1]
                fechas = fechas_line.split()
                
                # Periodos
                periodos_line = lineas[2]
                periodos = periodos_line.split()
                
                # Temperaturas
                temps = re.findall(r'(-?\d+)\s*[ºC°C]', lineas[7])
                temps = [f"{t}°C" for t in temps]
                
                # Viento
                winds = re.findall(r'(\d+)\s*km/h', lineas[8])
                winds = [f"{w} km/h" for w in winds]
                
                # Dirección
                dirs = lineas[10].replace('Dirección', '').strip().split()
                
                # Mostrar tabla
                if temps and winds:
                    st.write("**Primeros días pronosticados:**")
                    
                    for i in range(min(4, len(periodos))):
                        fecha_idx = i // 2 * 2
                        fecha = fechas[fecha_idx] if fecha_idx < len(fechas) else "N/D"
                        
                        if i % 2 == 0:  # Solo mostrar una vez por fecha
                            st.write(f"**{fecha}**")
                            
                            # Día
                            if i < len(periodos) and periodos[i] == 'Día':
                                st.write(f"  ☀️ **Día**: {temps[i]} | Viento: {winds[i]} {dirs[i] if i < len(dirs) else ''}")
                            
                            # Noche (siguiente registro)
                            if i+1 < len(periodos) and periodos[i+1] == 'Noche':
                                st.write(f"  🌙 **Noche**: {temps[i+1]} | Viento: {winds[i+1]} {dirs[i+1] if i+1 < len(dirs) else ''}")
                            
                            st.write("---")
            except Exception as e:
                st.warning(f"No se pudieron parsear todos los datos del AIC: {e}")
                st.text_area("Contenido crudo del AIC:", aic[:1000], height=200)
