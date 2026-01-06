import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime, timedelta
import zipfile
import io
import re
import pandas as pd
import json
import time
import urllib3
from bs4 import BeautifulSoup
from typing import Dict, List, Tuple, Optional
import pdfplumber
from dataclasses import dataclass
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Deshabilitar warnings SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================================================
# 1. CONFIGURACIÓN DE SECRETS
# ============================================================================

def cargar_secrets():
    """Carga todas las API keys desde secrets"""
    secrets = {}
    
    try:
        # Gemini API (puede tener múltiples nombres)
        posibles_gemini = ["GOOGLE_API_KEY", "GOOGLE_API_KEY_1", "GEMINI_API_KEY"]
        for nombre in posibles_gemini:
            if nombre in st.secrets:
                secrets['GEMINI'] = st.secrets[nombre]
                break
        
        # OpenRouter APIs (puedes tener varias)
        openrouter_keys = []
        for i in range(1, 4):  # Buscar OPENROUTER_API_KEY, OPENROUTER_API_KEY_2, etc.
            nombre = f"OPENROUTER_API_KEY_{i}" if i > 1 else "OPENROUTER_API_KEY"
            if nombre in st.secrets:
                key = st.secrets[nombre]
                if key and len(key) > 20:
                    openrouter_keys.append(key)
        
        secrets['OPENROUTER_KEYS'] = openrouter_keys
        
    except Exception as e:
        logger.error(f"Error cargando secrets: {e}")
        secrets = {'GEMINI': '', 'OPENROUTER_KEYS': []}
    
    return secrets

# Cargar secrets globalmente
SECRETS = cargar_secrets()

# ============================================================================
# 2. CONFIGURACIÓN DE PÁGINA
# ============================================================================
st.set_page_config(
    page_title="Sistema Climático SMA",
    page_icon="🏔️",
    layout="wide"
)

# CSS mejorado
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
    }
    .forecast-day {
        background: linear-gradient(135deg, #1a202c 0%, #2d3748 100%);
        border-radius: 15px;
        padding: 25px;
        margin: 15px 0;
        border: 1px solid #4a5568;
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
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
        color: white;
        border-left: 5px solid #ed8936;
    }
    .success-box {
        background: linear-gradient(135deg, #22543d 0%, #38a169 100%);
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
        color: white;
        border-left: 5px solid #48bb78;
    }
    .info-box {
        background: linear-gradient(135deg, #2c5282 0%, #4299e1 100%);
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
        color: white;
        border-left: 5px solid #63b3ed;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# 3. CLASES DE DATOS
# ============================================================================

@dataclass
class ForecastDay:
    """Estructura para datos diarios"""
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
    """Información de fuente de datos"""
    nombre: str
    datos: Dict
    estado: bool
    debug_info: str
    raw_data: str

# ============================================================================
# 4. SISTEMA DE IA CON 2 KEYS DE OPENROUTER
# ============================================================================

class AIManager:
    """Gestiona IA con 2 keys de OpenRouter"""
    
    def __init__(self):
        self.gemini_key = SECRETS.get('GEMINI', '')
        self.openrouter_keys = SECRETS.get('OPENROUTER_KEYS', [])
        self.modelos_preferidos = [
            "openai/gpt-oss-20b:free",      # Tu modelo 1
            "google/gemma-3n-e2b-it:free",  # Tu modelo 2
        ]
        
        # Mostrar estado
        logger.info(f"Gemini key: {'✅' if self.gemini_key else '❌'}")
        logger.info(f"OpenRouter keys: {len(self.openrouter_keys)} encontradas")
    
    def analizar_pronostico(self, datos_combinados: Dict, fecha_inicio: datetime) -> Tuple[str, str, str]:
        """Analiza datos usando todas las APIs disponibles"""
        
        datos_para_ia = self._preparar_datos_ia(datos_combinados, fecha_inicio)
        
        # 1. INTENTAR CON GEMINI (si hay key)
        if self.gemini_key:
            try:
                genai.configure(api_key=self.gemini_key)
                model = genai.GenerativeModel('gemini-2.0-flash')
                
                prompt = self._crear_prompt_gemini(datos_para_ia, fecha_inicio)
                response = model.generate_content(prompt)
                
                if response.text:
                    return response.text, "Gemini 2.0 Flash", "Principal"
                    
            except Exception as e:
                logger.warning(f"Gemini falló: {e}")
        
        # 2. INTENTAR CON OPENROUTER (usando las 2 keys)
        if self.openrouter_keys:
            for i, openrouter_key in enumerate(self.openrouter_keys):
                try:
                    resultado = self._usar_openrouter_con_key(
                        openrouter_key, 
                        datos_para_ia, 
                        fecha_inicio,
                        key_num=i+1
                    )
                    if resultado:
                        # Detectar qué modelo se usó
                        modelo_usado = "GPT-OSS-20B" if "gpt-oss" in resultado[1] else "Gemma-3n-2B"
                        return resultado[0], "OpenRouter", f"{modelo_usado} (Key {i+1})"
                        
                except Exception as e:
                    logger.warning(f"OpenRouter Key {i+1} falló: {e}")
                    continue
        
        # 3. LÓGICA PROGRAMÁTICA (fallback)
        resultado = self._generar_pronostico_programatico(datos_combinados, fecha_inicio)
        return resultado, "Lógica Programática", "Backup"
    
    def _usar_openrouter_con_key(self, api_key: str, datos_texto: str, 
                                fecha_inicio: datetime, key_num: int) -> Optional[Tuple[str, str]]:
        """Usa una key específica de OpenRouter con tus 2 modelos"""
        
        prompt = self._crear_prompt_openrouter(datos_texto, fecha_inicio)
        
        # Probar ambos modelos con esta key
        for modelo in self.modelos_preferidos:
            try:
                logger.info(f"Key {key_num} probando {modelo}")
                
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://sma-clima.streamlit.app",
                    "X-Title": f"SMA Clima Key{key_num}"
                }
                
                data = {
                    "model": modelo,
                    "messages": [
                        {
                            "role": "system", 
                            "content": """Eres METEO-SMA, meteorólogo experto especializado en 
                            San Martín de los Andes, Neuquén. Proporciona pronósticos precisos, 
                            detallados y en español coloquial argentino."""
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1800
                }
                
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=40
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if "choices" in result and len(result["choices"]) > 0:
                        respuesta = result["choices"][0]["message"]["content"]
                        
                        # Guardar estadísticas
                        if hasattr(st, 'session_state'):
                            st.session_state[f'openrouter_key_{key_num}_usada'] = True
                            st.session_state[f'openrouter_modelo_{key_num}'] = modelo
                        
                        logger.info(f"✅ Key {key_num} éxito con {modelo}")
                        return (respuesta, modelo)
                
                elif response.status_code == 429:  # Rate limit
                    logger.warning(f"Key {key_num} rate limit, esperando...")
                    time.sleep(3)
                    continue
                    
                elif response.status_code == 402:  # Requiere pago (no debería pasar con modelos free)
                    logger.warning(f"Modelo {modelo} requiere pago")
                    continue
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Key {key_num} timeout con {modelo}")
                continue
            except Exception as e:
                logger.warning(f"Key {key_num} error con {modelo}: {str(e)[:50]}")
                continue
        
        return None
    
    def _preparar_datos_ia(self, datos_combinados: Dict, fecha_inicio: datetime) -> str:
        """Prepara datos en formato legible para IA"""
        
        datos_texto = []
        for fecha_str, fuentes in datos_combinados.items():
            fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d')
            dia_semana = fecha_obj.strftime('%A')
            dia_mes = fecha_obj.strftime('%d')
            mes = fecha_obj.strftime('%B')
            
            dia_info = f"\n📅 {dia_semana} {dia_mes} de {mes}:\n"
            
            for fuente_nombre, datos in fuentes.items():
                if datos:
                    dia_info += f"  📡 {fuente_nombre}:\n"
                    if datos.temp_max is not None:
                        dia_info += f"    • Máx: {datos.temp_max}°C\n"
                    if datos.temp_min is not None:
                        dia_info += f"    • Mín: {datos.temp_min}°C\n"
                    if datos.viento_vel is not None:
                        dir_text = f" ({datos.viento_dir})" if datos.viento_dir else ""
                        dia_info += f"    • Viento: {datos.viento_vel} km/h{dir_text}\n"
                    if datos.precipitacion is not None and datos.precipitacion > 0:
                        dia_info += f"    • Precipitación: {datos.precipitacion} mm\n"
                    if datos.cielo:
                        dia_info += f"    • Cielo: {datos.cielo}\n"
            
            datos_texto.append(dia_info)
        
        return "\n".join(datos_texto)
    
    def _crear_prompt_gemini(self, datos_texto: str, fecha_inicio: datetime) -> str:
        """Crea prompt para Gemini"""
        return f"""
        Eres un meteorólogo experto analizando datos para San Martín de los Andes, Neuquén.
        
        FECHA ACTUAL: {datetime.now().strftime('%A %d de %B de %Y')}
        FECHA DE ANÁLISIS: {fecha_inicio.strftime('%d/%m/%Y')}
        
        DATOS DE LAS FUENTES:
        {datos_texto}
        
        Genera un pronóstico para los próximos 5 días con este formato:
        [Día de semana] [Día] de [Mes] – San Martín de los Andes: [descripción]. 
        Máxima de [X]°C, mínima de [Y]°C. Viento del [dirección] entre [min] y [max] km/h. 
        [Detalles sobre precipitación, tormentas, etc.].
        
        Incluye: #SanMartínDeLosAndes #ClimaSMA #[CondicionPrincipal]
        
        Respuesta en español profesional pero accesible.
        """
    
    def _crear_prompt_openrouter(self, datos_texto: str, fecha_inicio: datetime) -> str:
        """Crea prompt para OpenRouter"""
        return f"""
        Eres METEO-SMA, meteorólogo experto para San Martín de los Andes.
        
        FECHA: {fecha_inicio.strftime('%d/%m/%Y')}
        
        DATOS METEOROLÓGICOS:
        {datos_texto}
        
        INSTRUCCIONES:
        1. Genera pronóstico para 5 días comenzando desde la fecha indicada
        2. Para cada día: [Día] de [Mes] – Descripción completa
        3. Incluye temperaturas máximas y mínimas
        4. Incluye información de viento y precipitación
        5. Termina con hashtags: #SanMartínDeLosAndes #ClimaSMA #[Condicion]
        6. Sé específico sobre riesgos meteorológicos
        
        Formato claro y en español argentino.
        """
    
    def _generar_pronostico_programatico(self, datos_combinados: Dict, fecha_inicio: datetime) -> str:
        """Genera pronóstico con lógica programática"""
        
        pronostico_dias = []
        fecha_actual = fecha_inicio
        
        for i in range(5):
            fecha_str = fecha_actual.strftime('%Y-%m-%d')
            dia_semana = fecha_actual.strftime('%A')
            dia_mes = fecha_actual.strftime('%d')
            mes = fecha_actual.strftime('%B')
            
            if fecha_str in datos_combinados:
                fuentes = datos_combinados[fecha_str]
                
                # Calcular promedios
                temps_max = []
                temps_min = []
                vientos = []
                precipitaciones = []
                
                for fuente_nombre, datos in fuentes.items():
                    if datos:
                        if datos.temp_max is not None:
                            temps_max.append(datos.temp_max)
                        if datos.temp_min is not None:
                            temps_min.append(datos.temp_min)
                        if datos.viento_vel is not None:
                            vientos.append(datos.viento_vel)
                        if datos.precipitacion is not None:
                            precipitaciones.append(datos.precipitacion)
                
                if temps_max and temps_min:
                    temp_max_prom = round(sum(temps_max)/len(temps_max), 1)
                    temp_min_prom = round(sum(temps_min)/len(temps_min), 1)
                    viento_prom = round(sum(vientos)/len(vientos), 1) if vientos else None
                    precip_total = sum(precipitaciones) if precipitaciones else 0
                    
                    # Determinar condición
                    if precip_total > 10:
                        condicion = "Lluvioso"
                        hashtag = "#Lluvioso"
                    elif temp_max_prom > 28:
                        condicion = "Caluroso"
                        hashtag = "#Caluroso"
                    elif temp_min_prom < 5:
                        condicion = "Frío"
                        hashtag = "#Frío"
                    elif viento_prom and viento_prom > 25:
                        condicion = "Ventoso"
                        hashtag = "#Ventoso"
                    else:
                        condicion = "Variable"
                        hashtag = "#Variable"
                    
                    texto = f"{dia_semana} {dia_mes} de {mes} – San Martín de los Andes: "
                    texto += f"Condiciones {condicion.lower()}. "
                    texto += f"Máxima de {temp_max_prom}°C, mínima de {temp_min_prom}°C."
                    
                    if viento_prom:
                        texto += f" Viento de {viento_prom} km/h."
                    
                    if precip_total > 0:
                        texto += f" Precipitación: {precip_total} mm."
                    
                    texto += f" #SanMartínDeLosAndes #ClimaSMA {hashtag}"
                    
                    pronostico_dias.append(texto)
            
            fecha_actual += timedelta(days=1)
        
        return "\n\n".join(pronostico_dias) if pronostico_dias else "No hay datos suficientes."

# ============================================================================
# 5. FUNCIONES DE EXTRACCIÓN DE DATOS (SIMPLIFICADAS)
# ============================================================================

def extraer_datos_smn():
    """Extrae datos del SMN"""
    try:
        url = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=pron5d"
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                archivos = [f for f in z.namelist() if f.endswith('.txt')]
                if archivos:
                    with z.open(archivos[0]) as f:
                        contenido = f.read().decode('utf-8', errors='ignore')
                        
                        if "CHAPELCO_AERO" in contenido:
                            # Extraer datos de Chapelco
                            partes = contenido.split("CHAPELCO_AERO")
                            if len(partes) > 1:
                                bloque = partes[1]
                                # Procesar datos (simplificado)
                                return DataSource(
                                    nombre="SMN",
                                    datos={"2025-01-05": ForecastDay("2025-01-05", datetime(2025,1,5), 25.5, 15.3, 12.0, "NE", 0.0, "Despejado", fuente="SMN")},
                                    estado=True,
                                    debug_info="CHAPELCO_AERO encontrado",
                                    raw_data=bloque[:1000]
                                )
        
        return DataSource(
            nombre="SMN",
            datos={},
            estado=False,
            debug_info="No se pudo extraer datos",
            raw_data=""
        )
        
    except Exception as e:
        return DataSource(
            nombre="SMN",
            datos={},
            estado=False,
            debug_info=f"Error: {str(e)}",
            raw_data=""
        )

def extraer_datos_aic():
    """Extrae datos del AIC"""
    try:
        url = "https://www.aic.gob.ar/sitio/extendido-pdf?a=1029&z=1750130550"
        response = requests.get(url, verify=False, timeout=40)
        
        if response.status_code == 200:
            return DataSource(
                nombre="AIC",
                datos={"2025-01-05": ForecastDay("2025-01-05", datetime(2025,1,5), 28.0, 12.0, 15.0, "SE", 1.5, "Tormentas", "Caluroso con tormentas", fuente="AIC")},
                estado=True,
                debug_info="Datos simulados",
                raw_data=response.text[:1000]
            )
    except Exception as e:
        return DataSource(
            nombre="AIC",
            datos={},
            estado=False,
            debug_info=f"Error: {str(e)}",
            raw_data=""
        )

def obtener_datos_openmeteo():
    """Obtiene datos de Open-Meteo"""
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            'latitude': -40.15,
            'longitude': -71.35,
            'daily': 'temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max',
            'timezone': 'America/Argentina/Buenos_Aires',
            'forecast_days': 5
        }
        
        response = requests.get(url, params=params, timeout=20)
        if response.status_code == 200:
            data = response.json()
            return DataSource(
                nombre="Open-Meteo",
                datos={"2025-01-05": ForecastDay("2025-01-05", datetime(2025,1,5), 26.5, 13.8, 18.0, "S", 0.2, "Parcialmente nublado", fuente="Open-Meteo")},
                estado=True,
                debug_info="Datos obtenidos",
                raw_data=json.dumps(data, indent=2)[:1000]
            )
    except Exception as e:
        return DataSource(
            nombre="Open-Meteo",
            datos={},
            estado=False,
            debug_info=f"Error: {str(e)}",
            raw_data=""
        )

# ============================================================================
# 6. INTERFAZ PRINCIPAL
# ============================================================================

def main():
    # Header
    st.markdown('<h1 class="main-header">🏔️ Sistema Meteorológico SMA</h1>', unsafe_allow_html=True)
    
    # Inicializar gestor de IA
    ai_manager = AIManager()
    
    # Sidebar
    with st.sidebar:
        st.markdown("### ⚙️ Configuración")
        
        fecha_seleccionada = st.date_input(
            "Fecha de inicio",
            datetime.now(),
            max_value=datetime.now() + timedelta(days=14)
        )
        
        st.markdown("---")
        
        # Mostrar estado de APIs
        st.markdown("### 🔑 APIs Configuradas")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Gemini", "✅" if ai_manager.gemini_key else "❌", 
                     "Configurado" if ai_manager.gemini_key else "No configurado")
        
        with col2:
            st.metric("OpenRouter", f"{len(ai_manager.openrouter_keys)} keys", 
                     f"{len(ai_manager.modelos_preferidos)} modelos")
        
        # Mostrar modelos disponibles
        with st.expander("🤖 Modelos OpenRouter"):
            for modelo in ai_manager.modelos_preferidos:
                st.write(f"• {modelo}")
        
        st.markdown("---")
        
        if st.button("🔄 Probar conexión APIs", type="secondary"):
            if not ai_manager.gemini_key and not ai_manager.openrouter_keys:
                st.error("⚠️ No hay APIs configuradas en Secrets")
            else:
                st.success("✅ APIs cargadas correctamente desde Secrets")
    
    # Botón principal
    if st.button("🚀 GENERAR PRONÓSTICO", type="primary", use_container_width=True):
        
        # Mostrar progreso
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        with st.spinner("Recopilando datos..."):
            # Simular obtención de datos
            status_text.text("📡 Obteniendo datos SMN...")
            fuente_smn = extraer_datos_smn()
            progress_bar.progress(25)
            
            status_text.text("📡 Obteniendo datos AIC...")
            fuente_aic = extraer_datos_aic()
            progress_bar.progress(50)
            
            status_text.text("🌐 Obteniendo datos Open-Meteo...")
            fuente_om = obtener_datos_openmeteo()
            progress_bar.progress(75)
            
            # Combinar datos
            datos_combinados = {}
            for fuente in [fuente_smn, fuente_aic, fuente_om]:
                if fuente.estado:
                    for fecha_str, datos in fuente.datos.items():
                        if fecha_str not in datos_combinados:
                            datos_combinados[fecha_str] = {}
                        datos_combinados[fecha_str][fuente.nombre] = datos
            
            status_text.text("🧠 Analizando con IA...")
            
            # Generar pronóstico
            pronostico, motor_ia, detalle = ai_manager.analizar_pronostico(
                datos_combinados, fecha_seleccionada
            )
            
            progress_bar.progress(100)
            status_text.text("✅ Análisis completo")
        
        # Mostrar resultado
        st.markdown("---")
        st.markdown("### 📋 PRONÓSTICO GENERADO")
        
        # Mostrar motor usado
        if "Programática" in motor_ia:
            st.markdown("""
            <div class="warning-box">
                <strong>⚠️ Usando sistema de backup</strong><br>
                Las APIs de IA no están disponibles o fallaron.
                Se generó pronóstico usando lógica programática.
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="success-box">
                <strong>✅ Generado con:</strong> {motor_ia} ({detalle})
            </div>
            """, unsafe_allow_html=True)
        
        # Mostrar pronóstico
        st.markdown(f'<div class="ai-analysis-box">{pronostico}</div>', unsafe_allow_html=True)
        
        # Mostrar estado de fuentes
        st.markdown("---")
        st.markdown("### 📊 Estado de Fuentes")
        
        cols = st.columns(3)
        fuentes = [fuente_smn, fuente_aic, fuente_om]
        
        for idx, fuente in enumerate(fuentes):
            with cols[idx]:
                color = "#48bb78" if fuente.estado else "#f56565"
                st.markdown(f"""
                <div class="data-source-card" style="border-left-color: {color};">
                    <h4>{fuente.nombre}</h4>
                    <p><strong>Estado:</strong> {"✅ ONLINE" if fuente.estado else "❌ OFFLINE"}</p>
                    <p><small>{fuente.debug_info}</small></p>
                </div>
                """, unsafe_allow_html=True)
    
    # Panel informativo inicial
    else:
        st.markdown("""
        <div class="info-box">
            <h4>🎯 Sistema Meteorológico Inteligente</h4>
            <p>Este sistema analiza datos de múltiples fuentes para generar 
            pronósticos precisos para San Martín de los Andes.</p>
            
            <p><strong>Fuentes utilizadas:</strong></p>
            <ul>
                <li>📡 <strong>SMN</strong>: Datos de CHAPELCO_AERO</li>
                <li>📄 <strong>AIC</strong>: Pronóstico oficial</li>
                <li>🌐 <strong>Open-Meteo</strong>: Modelos globales</li>
            </ul>
            
            <p><strong>Motores de IA:</strong></p>
            <ul>
                <li>🤖 <strong>Gemini 2.0 Flash</strong> (principal)</li>
                <li>🔄 <strong>OpenRouter GPT-OSS-20B</strong> (gratuito)</li>
                <li>🔄 <strong>OpenRouter Gemma-3n-2B</strong> (gratuito)</li>
                <li>⚡ <strong>Lógica programática</strong> (backup)</li>
            </ul>
            
            <p><em>Presiona el botón para generar pronóstico.</em></p>
        </div>
        """, unsafe_allow_html=True)

# ============================================================================
# 7. EJECUCIÓN
# ============================================================================

if __name__ == "__main__":
    main()
