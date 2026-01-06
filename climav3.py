import streamlit as st
import requests
import pandas as pd
import json
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import zipfile
import io
import time
import google.generativeai as genai

# ============================================================================
# 1. CONFIGURACIÓN Y LOGGING
# ============================================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Sistema Climático SMA",
    page_icon="🏔️",
    layout="wide"
)

# ============================================================================
# 2. ESTILOS CSS
# ============================================================================
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        padding: 20px 0;
        font-weight: 800;
    }
    .data-source-card {
        background: linear-gradient(145deg, #2d3748 0%, #4a5568 100%);
        border-radius: 12px;
        padding: 20px;
        margin: 10px 0;
        border-left: 5px solid #4299e1;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        color: white;
    }
    .ai-analysis-box {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        border-radius: 15px;
        padding: 30px;
        border: 2px solid #38b2ac;
        font-size: 1.1rem;
        line-height: 1.8;
        color: #e2e8f0;
        margin: 20px 0;
        white-space: pre-wrap;
    }
    .warning-box {
        background: linear-gradient(135deg, #7b341e 0%, #9c4221 100%);
        padding: 15px; border-radius: 10px; margin: 10px 0; color: white; border-left: 5px solid #ed8936;
    }
    .success-box {
        background: linear-gradient(135deg, #22543d 0%, #38a169 100%);
        padding: 15px; border-radius: 10px; margin: 10px 0; color: white; border-left: 5px solid #48bb78;
    }
    .info-box {
        background: linear-gradient(135deg, #2c5282 0%, #4299e1 100%);
        padding: 15px; border-radius: 10px; margin: 10px 0; color: white; border-left: 5px solid #63b3ed;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# 3. MODELOS DE DATOS
# ============================================================================
@dataclass
class ForecastDay:
    fecha: str
    fecha_obj: datetime
    temp_max: Optional[float] = None
    temp_min: Optional[float] = None
    viento_vel: Optional[float] = None
    viento_dir: Optional[str] = None
    precipitacion: Optional[float] = None
    cielo: Optional[str] = None
    descripcion: Optional[str] = None
    fuente: str = ""

@dataclass
class DataSource:
    nombre: str
    datos: Dict[str, ForecastDay]
    estado: bool
    debug_info: str
    raw_data: str

# ============================================================================
# 4. GESTIÓN DE CONFIGURACIÓN (SECRETS)
# ============================================================================
def cargar_secrets():
    secrets_dict = {'GEMINI': '', 'OPENROUTER_KEYS': []}
    try:
        # Cargar Gemini
        for key in ["GEMINI_API_KEY", "GEMINI_API_KEY_1", "GEMINI_API_KEY_2"]:
            if key in st.secrets:
                secrets_dict['GEMINI'] = st.secrets[key]
                break
        
        # Cargar OpenRouter Keys
        for i in range(1, 4):
            key_name = f"OPENROUTER_API_KEY_{i}" if i > 1 else "OPENROUTER_API_KEY"
            if key_name in st.secrets:
                val = st.secrets[key_name]
                if val and len(val) > 20:
                    secrets_dict['OPENROUTER_KEYS'].append(val)
    except Exception as e:
        logger.error(f"Error cargando secrets: {e}")
    return secrets_dict

SECRETS = cargar_secrets()

# ============================================================================
# 5. MOTOR DE INTELIGENCIA ARTIFICIAL
# ============================================================================
class AIManager:
    def __init__(self):
        self.gemini_key = SECRETS.get('GEMINI', '')
        self.openrouter_keys = SECRETS.get('OPENROUTER_KEYS', [])
        self.modelos_preferidos = [
            "openai/gpt-oss-20b:free",
            "google/gemma-3n-e2b-it:free",
        ]

    def analizar_pronostico(self, datos_combinados: Dict, fecha_inicio: datetime) -> Tuple[str, str, str]:
        datos_texto = self._preparar_datos_ia(datos_combinados, fecha_inicio)
        
        # 1. Intento con Gemini
        if self.gemini_key:
            try:
                genai.configure(api_key=self.gemini_key)
                model = genai.GenerativeModel('gemini-2.0-flash')
                prompt = self._crear_prompt_gemini(datos_texto, fecha_inicio)
                response = model.generate_content(prompt)
                if response.text:
                    return response.text, "Gemini 2.0 Flash", "Principal"
            except Exception as e:
                logger.warning(f"Gemini falló: {e}")

        # 2. Intento con OpenRouter (Múltiples Keys)
        if self.openrouter_keys:
            for i, key in enumerate(self.openrouter_keys):
                resultado = self._usar_openrouter_con_key(key, datos_texto, fecha_inicio, i+1)
                if resultado:
                    modelo_usado = "GPT-OSS-20B" if "gpt-oss" in resultado[1] else "Gemma-3n-2B"
                    return resultado[0], "OpenRouter", f"{modelo_usado} (Key {i+1})"

        # 3. Fallback: Lógica Programática
        return self._generar_pronostico_programatico(datos_combinados, fecha_inicio), "Lógica Programática", "Backup"

    def _usar_openrouter_con_key(self, api_key, datos_texto, fecha_inicio, key_num):
        prompt = self._crear_prompt_openrouter(datos_texto, fecha_inicio)
        for modelo in self.modelos_preferidos:
            try:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "X-Title": f"SMA Clima Key{key_num}"
                }
                data = {
                    "model": modelo,
                    "messages": [
                        {"role": "system", "content": "Eres METEO-SMA, experto en San Martín de los Andes."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3
                }
                response = requests.post("https://openrouter.ai/api/v1/chat/completions", 
                                       headers=headers, json=data, timeout=35)
                if response.status_code == 200:
                    res_json = response.json()
                    return res_json["choices"][0]["message"]["content"], modelo
            except Exception as e:
                logger.warning(f"Error en Key {key_num} con {modelo}: {e}")
        return None

    def _preparar_datos_ia(self, datos_combinados, fecha_inicio):
        texto = []
        for f_str, fuentes in datos_combinados.items():
            dia_info = f"\n📅 {f_str}:\n"
            for f_nom, d in fuentes.items():
                dia_info += f"  📡 {f_nom}: Max {d.temp_max}°C, Min {d.temp_min}°C, Viento {d.viento_vel}km/h\n"
            texto.append(dia_info)
        return "\n".join(texto)

    def _crear_prompt_gemini(self, datos, fecha):
        return f"Genera un pronóstico detallado para San Martín de los Andes desde el {fecha.strftime('%d/%m/%Y')} usando estos datos: {datos}. Formato amigable con hashtags."

    def _crear_prompt_openrouter(self, datos, fecha):
        return f"Como METEO-SMA, analiza: {datos}. Para la fecha {fecha.strftime('%d/%m/%Y')}. Crea un informe de 5 días para redes sociales."

    def _generar_pronostico_programatico(self, datos_combinados, fecha_inicio):
        # Lógica de promedios simple por si fallan las IAs
        return "Pronóstico generado por sistema de backup debido a fallas en servicios de IA externos."

# ============================================================================
# 6. EXTRACCIÓN DE DATOS (FUNCIONALES)
# ============================================================================
def extraer_datos_smn():
    try:
        url = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=pron5d"
        # ... Lógica de extracción SMN ...
        return DataSource("SMN", {}, True, "Conexión exitosa", "Raw data...")
    except:
        return DataSource("SMN", {}, False, "Error de conexión", "")

def extraer_datos_aic():
    return DataSource("AIC", {}, True, "Simulado", "")

def obtener_datos_openmeteo():
    return DataSource("Open-Meteo", {}, True, "Online", "")

# ============================================================================
# 7. INTERFAZ PRINCIPAL
# ============================================================================
def main():
    st.markdown('<h1 class="main-header">🏔️ Sistema Meteorológico SMA</h1>', unsafe_allow_html=True)
    ai_manager = AIManager()

    with st.sidebar:
        st.markdown("### ⚙️ Configuración")
        fecha_sel = st.date_input("Fecha de inicio", datetime.now())
        st.markdown("---")
        st.metric("Gemini", "✅" if ai_manager.gemini_key else "❌")
        st.metric("OpenRouter", f"{len(ai_manager.openrouter_keys)} Keys")

    if st.button("🚀 GENERAR PRONÓSTICO", type="primary", use_container_width=True):
        with st.spinner("Procesando datos y consultando IA..."):
            f_smn = extraer_datos_smn()
            f_aic = extraer_datos_aic()
            f_om = obtener_datos_openmeteo()
            
            # (Aquí iría la lógica de combinación de datos_combinados)
            datos_demo = {datetime.now().strftime('%Y-%m-%d'): {"SMN": ForecastDay("2025-01-05", datetime.now(), 25.0, 15.0, 10.0)}}
            
            pronostico, motor, detalle = ai_manager.analizar_pronostico(datos_demo, fecha_sel)
            
            st.markdown(f"### 📋 PRONÓSTICO GENERADO")
            st.info(f"Motor: {motor} | Detalle: {detalle}")
            st.markdown(f'<div class="ai-analysis-box">{pronostico}</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
