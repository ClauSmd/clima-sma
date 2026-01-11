import streamlit as st
import requests
import pdfplumber
import io
import json

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Weather Aggregator SMA", layout="wide")

# --- 2. FUNCIONES DE EXTRACCIÓN (ORDEN CORRECTO) ---

def get_aic_data():
    url = "https://www.aic.gob.ar/sitio/extendido-pdf?a=1029&z=1750130550"
    try:
        response = requests.get(url, timeout=15)
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            pagina = pdf.pages[0]
            tabla = pagina.extract_table({"vertical_strategy": "lines", "horizontal_strategy": "lines"})
            fechas_fila = [f.replace("\n", "") for f in tabla[0] if f]
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
                    "fecha": fechas_fila[idx] if idx < len(fechas_fila) else "S/D",
                    "cielo": cielos[i], "max": float(temps[i]), "min": float(temps[i+1]),
                    "viento": float(v_vel[i]), "rafaga": float(v_raf[i]), "dir": v_dir[i]
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
                "fecha": d["time"][i], "max": d["temperature_2m_max"][i],
                "min": d["temperature_2m_min"][i], "viento": d["windspeed_10m_max"][i],
                "rafaga": d["windgusts_10m_max"][i]
            })
        return {"status": "OK", "datos": procesados}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

def consultar_ia(prompt):
    api_key = st.secrets.get("OPENROUTER_API_KEY")
    modelos = ["google/gemini-2.0-flash-exp:free", "meta-llama/llama-3.1-8b-instruct:free"]
    for modelo in modelos:
        try:
            res = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                data=json.dumps({"model": modelo, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3}),
                timeout=15
            )
            data = res.json()
            if "choices" in data:
                return data['choices'][0]['message']['content']
        except:
            continue
    return None

# --- 3. INTERFAZ ---
st.title("🌤️ Pronóstico Ponderado SMA")

if st.button("🚀 GENERAR REPORTE"):
    d_aic = get_aic_data()
    d_om = get_open_meteo_data()

    if d_aic["status"] == "OK" and d_om["status"] == "OK":
        prompt = f"Meteorólogo: Genera reporte ponderado 50/50. DATOS: {json.dumps({'AIC': d_aic['datos'], 'OM': d_om['datos']})}. FORMATO: [Día Semana] [Día] de [Mes] – San Martín de los Andes: [Condición] con [Cielo], máxima [Max] °C, mínima [Min] °C. Viento [Dir] [Vel]-[Raf] km/h. #ClimaSMA. SÍNTESIS DIARIA: [Texto]"
        
        reporte = consultar_ia(prompt)

        # RESPALDO MATEMÁTICO SI LA IA FALLA
        if not reporte:
            st.warning("⚠️ IA no responde. Generando reporte matemático automático.")
            reporte = "PRONÓSTICO PONDERADO (CÁLCULO AUTOMÁTICO)\n\n"
            for i in range(5):
                p_max = (d_aic['datos'][i]['max'] + d_om['datos'][i]['max']) / 2
                p_min = (d_aic['datos'][i]['min'] + d_om['datos'][i]['min']) / 2
                reporte += f"• Día {i+1}: Máxima {p_max:.1f}°C, Mínima {p_min:.1f}°C. Viento {d_aic['datos'][i]['viento']} km/h. #{d_aic['datos'][i]['cielo'].replace(' ', '')}\n"
            reporte += f"\nSÍNTESIS (AIC): {d_aic['sintesis']}"

        st.info(reporte)
        st.text_area("Copia aquí:", value=reporte, height=300)
    else:
        st.error("Error al obtener datos de las fuentes.")
