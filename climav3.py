import streamlit as st
import requests
import pdfplumber
import io
import json
from datetime import datetime

# --- 1. CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="Weather Aggregator SMA", layout="wide")

# --- 2. FUNCIONES DE EXTRACCIÓN (ORDENADAS) ---

def get_aic_data():
    url = "https://www.aic.gob.ar/sitio/extendido-pdf?a=1029&z=1750130550"
    try:
        response = requests.get(url, timeout=15)
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            pagina = pdf.pages[0]
            tabla = pagina.extract_table({"vertical_strategy": "lines", "horizontal_strategy": "lines"})
            fechas_raw = [f.replace("\n", "") for f in tabla[0] if f]
            cielos = [c.replace("\n", " ") for c in tabla[2][1:] if c]
            temps = [t.replace("\n", "").replace(" ºC", "").strip() for t in tabla[3][1:] if t]
            v_vel = [v.replace("\n", "").replace(" km/h", "").strip() for v in tabla[4][1:] if v]
            v_raf = [r.replace("\n", "").replace(" km/h", "").strip() for r in tabla[5][1:] if r]
            v_dir = [d.replace("\n", "") for d in tabla[6][1:] if d]
            
            texto = pagina.extract_text()
            sintesis = texto.split("hPa")[-1].split("www.aic.gob.ar")[0].strip() if "hPa" in texto else ""

            dias_dict = []
            for i in range(0, min(10, len(cielos)), 2):
                idx = i // 2
                dias_dict.append({
                    "fecha": fechas_raw[idx] if idx < len(fechas_raw) else "S/D",
                    "cielo": cielos[i],
                    "max": float(temps[i]),
                    "min": float(temps[i+1]),
                    "viento": float(v_vel[i]),
                    "rafaga": float(v_raf[i]),
                    "dir": v_dir[i]
                })
            return {"status": "OK", "datos": dias_dict, "sintesis": sintesis}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

def get_open_meteo_data():
    url = "https://api.open-meteo.com/v1/forecast?latitude=-40.15&longitude=-71.35&daily=temperature_2m_max,temperature_2m_min,windspeed_10m_max,windgusts_10m_max&timezone=America%2FArgentina%2FSalta&forecast_days=5"
    try:
        r = requests.get(url, timeout=15)
        d = r.json()["daily"]
        procesados = []
        for i in range(len(d["time"])):
            procesados.append({
                "fecha": d["time"][i],
                "max": d["temperature_2m_max"][i],
                "min": d["temperature_2m_min"][i],
                "viento": d["windspeed_10m_max"][i],
                "rafaga": d["windgusts_10m_max"][i]
            })
        return {"status": "OK", "datos": procesados}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

def consultar_ia(prompt):
    api_key = st.secrets.get("OPENROUTER_API_KEY")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://clima-sma.streamlit.app", # Requerido para validar tu key
        "Content-Type": "application/json"
    }
    # Intentamos con un modelo robusto que no suele saturarse
    modelos = ["google/gemini-flash-1.5", "meta-llama/llama-3.1-8b-instruct:free"]
    
    for modelo in modelos:
        try:
            res = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                data=json.dumps({"model": modelo, "messages": [{"role": "user", "content": prompt}], "temperature": 0.4}),
                timeout=25
            )
            if res.status_code == 200:
                return res.json()['choices'][0]['message']['content']
        except:
            continue
    return None

# --- 3. INTERFAZ Y LÓGICA PRINCIPAL ---

st.title("🌤️ Weather Aggregator SMA")
st.markdown("---")

if st.button("🚀 GENERAR PRONÓSTICO PONDERADO"):
    with st.spinner("Ponderando AIC y Open-Meteo..."):
        d_aic = get_aic_data()
        d_om = get_open_meteo_data()

        if d_aic["status"] == "OK" and d_om["status"] == "OK":
            # PREPARAR DATOS PARA IA
            prompt = f"""
            Actúa como meteorólogo. Genera el pronóstico ponderado al 50/50.
            DATOS AIC: {json.dumps(d_aic['datos'])}
            DATOS OPENMETEO: {json.dumps(d_om['datos'])}
            SINTESIS REGIONAL: {d_aic['sintesis']}
            
            FORMATO OBLIGATORIO:
            [Día Semana] [Día] de [Mes] – San Martín de los Andes: [Condición] con [Cielo], máxima [Max] °C, mínima [Min] °C. Viento del [Dir] entre [Vel] y [Raf] km/h, [Lluvias]. #SanMartínDeLosAndes #ClimaSMA
            
            SÍNTESIS DIARIA:
            [Análisis narrativo unificado]
            """

            resultado = consultar_ia(prompt)

            if resultado:
                # ÉXITO: Mostramos el formato estético que logramos antes
                st.subheader("📍 Resultado Ponderado Unificado")
                st.info(resultado)
                st.text_area("Copia el reporte aquí:", value=resultado, height=350)
            else:
                # FALLO DE IA: Reconstrucción manual con el formato de las CAPTURAS
                st.error("La IA no respondió, usando generador de estructura local...")
                meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
                dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
                
                final_text = ""
                for i in range(5):
                    # Ponderación manual
                    p_max = (d_aic['datos'][i]['max'] + d_om['datos'][i]['max']) / 2
                    p_min = (d_aic['datos'][i]['min'] + d_om['datos'][i]['min']) / 2
                    
                    f_dt = datetime.strptime(d_aic['datos'][i]['fecha'], "%d-%m-%Y")
                    linea = (f"**{dias_semana[f_dt.weekday()]} {f_dt.day} de {meses[f_dt.month-1]} – San Martín de los Andes:** "
                             f"{d_aic['datos'][i]['cielo']} con cielo parcial, máxima {p_max:.1f} °C, mínima {p_min:.1f} °C. "
                             f"Viento del {d_aic['datos'][i]['dir']} a {d_aic['datos'][i]['viento']} km/h. "
                             f"#SanMartínDeLosAndes #ClimaSMA\n\n")
                    final_text += linea
                
                final_text += f"**SÍNTESIS DIARIA:**\n{d_aic['sintesis']}"
                st.info(final_text)
        else:
            st.error("Error al obtener datos de las fuentes PDF o API.")
