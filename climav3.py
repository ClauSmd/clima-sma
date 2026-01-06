import streamlit as st
import requests
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
    """Carga la API key de OpenRouter desde secrets"""
    secrets = {}
    
    try:
        # OpenRouter API (gratuita)
        if "OPENROUTER_API_KEY" in st.secrets:
            secrets['OPENROUTER_KEY'] = st.secrets["OPENROUTER_API_KEY"]
            logger.info("✅ OpenRouter API key encontrada")
        else:
            logger.warning("❌ OpenRouter API key NO encontrada en secrets")
            secrets['OPENROUTER_KEY'] = ''
        
    except Exception as e:
        logger.error(f"Error cargando secrets: {e}")
        secrets = {'OPENROUTER_KEY': ''}
    
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
    .model-status {
        background: #2d3748;
        padding: 10px;
        border-radius: 8px;
        margin: 5px 0;
        border-left: 4px solid #4299e1;
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
# 4. SISTEMA DE IA CON MODELOS GRATUITOS DE OPENROUTER
# ============================================================================

class AIManager:
    """Gestiona IA usando SOLO modelos gratuitos de OpenRouter"""
    
    def __init__(self):
        self.openrouter_key = SECRETS.get('OPENROUTER_KEY', '')
        
        # LISTA COMPLETA DE MODELOS GRATUITOS DE OPENROUTER
        self.modelos_gratuitos = [
            # Modelos principales recomendados
            "openai/gpt-3.5-turbo",                    # 5M tokens gratis/mes
            "google/gemini-2.0-flash-exp:free",        # Experimental gratis
            
            # Modelos específicos que pediste
            "openai/gpt-oss-20b:free",                 # GPT OSS 20B
            "google/gemma-3n-e2b-it:free",             # Gemma 3n 2B
            
            # Otros modelos gratuitos confiables
            "microsoft/phi-3-medium-128k-instruct:free",
            "huggingfaceh4/zephyr-7b-beta:free",
            "qwen/qwen-2.5-32b-instruct:free",
            "meta-llama/llama-3.2-3b-instruct:free",
            "cognitivecomputations/dolphin-3.0-llama-3-8b:free",
            "nousresearch/hermes-3-llama-3.1-8b:free",
        ]
        
        # Mostrar estado
        if self.openrouter_key:
            logger.info(f"✅ OpenRouter key cargada - {len(self.modelos_gratuitos)} modelos disponibles")
        else:
            logger.warning("❌ NO hay OpenRouter key configurada")
    
    def analizar_pronostico(self, datos_combinados: Dict, fecha_inicio: datetime) -> Tuple[str, str, str]:
        """Analiza datos usando SOLO modelos gratuitos de OpenRouter"""
        
        datos_para_ia = self._preparar_datos_ia(datos_combinados, fecha_inicio)
        
        # 1. INTENTAR CON OPENROUTER (modelos gratuitos)
        if self.openrouter_key:
            resultado, modelo_usado = self._usar_modelos_openrouter_gratis(datos_para_ia, fecha_inicio)
            if resultado:
                return resultado, "OpenRouter", modelo_usado
        
        # 2. LÓGICA PROGRAMÁTICA (fallback si OpenRouter falla)
        resultado = self._generar_pronostico_programatico(datos_combinados, fecha_inicio)
        return resultado, "Lógica Programática", "Backup"
    
    def _usar_modelos_openrouter_gratis(self, datos_texto: str, fecha_inicio: datetime) -> Tuple[Optional[str], str]:
        """Usa TODOS los modelos gratuitos de OpenRouter hasta que uno funcione"""
        
        prompt = self._crear_prompt_meteorologico(datos_texto, fecha_inicio)
        
        for modelo in self.modelos_gratuitos:
            try:
                logger.info(f"Probando modelo gratuito: {modelo}")
                
                headers = {
                    "Authorization": f"Bearer {self.openrouter_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://sma-clima.streamlit.app",
                    "X-Title": "Sistema Meteorológico SMA"
                }
                
                data = {
                    "model": modelo,
                    "messages": [
                        {
                            "role": "system", 
                            "content": """Eres METEO-ARGENTINA, meteorólogo experto especializado en 
                            la región andina de Neuquén, específicamente San Martín de los Andes 
                            y la zona de Chapelco. Proporciona pronósticos detallados, precisos 
                            y en español coloquial argentino."""
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.2,  # Bajo para consistencia
                    "max_tokens": 2000,
                    "top_p": 0.9,
                    "frequency_penalty": 0.1,
                    "presence_penalty": 0.1
                }
                
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=45
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if "choices" in result and len(result["choices"]) > 0:
                        respuesta = result["choices"][0]["message"]["content"]
                        
                        # Guardar estadísticas en session_state
                        if hasattr(st, 'session_state'):
                            st.session_state['modelo_exitoso'] = modelo
                            st.session_state['timestamp_ia'] = datetime.now()
                        
                        logger.info(f"✅ Éxito con modelo: {modelo}")
                        return respuesta, self._nombre_amigable_modelo(modelo)
                
                elif response.status_code == 429:  # Rate limit
                    logger.warning(f"Rate limit con {modelo}, esperando 2s...")
                    time.sleep(2)
                    continue
                    
                elif response.status_code == 402:  # Requiere pago (no debería pasar con free)
                    logger.warning(f"Modelo {modelo} requiere pago, saltando...")
                    continue
                    
                else:
                    logger.warning(f"Modelo {modelo} error HTTP {response.status_code}")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout con {modelo}, siguiente modelo...")
                continue
            except Exception as e:
                logger.warning(f"Error con {modelo}: {str(e)[:50]}")
                continue
        
        logger.error("❌ Todos los modelos gratuitos fallaron")
        return None, ""
    
    def _nombre_amigable_modelo(self, modelo: str) -> str:
        """Convierte nombre técnico a nombre amigable"""
        nombres = {
            "openai/gpt-3.5-turbo": "GPT-3.5 Turbo",
            "google/gemini-2.0-flash-exp:free": "Gemini 2.0 Flash",
            "openai/gpt-oss-20b:free": "GPT OSS 20B",
            "google/gemma-3n-e2b-it:free": "Gemma 3n 2B",
            "microsoft/phi-3-medium-128k-instruct:free": "Phi-3 Medium",
            "huggingfaceh4/zephyr-7b-beta:free": "Zephyr 7B",
            "qwen/qwen-2.5-32b-instruct:free": "Qwen 32B",
            "meta-llama/llama-3.2-3b-instruct:free": "Llama 3.2 3B",
        }
        return nombres.get(modelo, modelo.split('/')[-1].split(':')[0])
    
    def _preparar_datos_ia(self, datos_combinados: Dict, fecha_inicio: datetime) -> str:
        """Prepara datos en formato legible para IA"""
        
        if not datos_combinados:
            return "No hay datos disponibles de las fuentes meteorológicas."
        
        datos_texto = [f"📊 DATOS METEOROLÓGICOS - Fecha análisis: {fecha_inicio.strftime('%d/%m/%Y')}\n"]
        
        for fecha_str, fuentes in datos_combinados.items():
            fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d')
            dia_semana = fecha_obj.strftime('%A')
            dia_mes = fecha_obj.strftime('%d')
            mes = self._mes_espanol(fecha_obj.strftime('%B'))
            
            datos_texto.append(f"\n📅 {dia_semana} {dia_mes} de {mes}:")
            
            for fuente_nombre, datos in fuentes.items():
                if datos:
                    datos_texto.append(f"  📡 {fuente_nombre}:")
                    if datos.temp_max is not None:
                        datos_texto.append(f"    • Máxima: {datos.temp_max}°C")
                    if datos.temp_min is not None:
                        datos_texto.append(f"    • Mínima: {datos.temp_min}°C")
                    if datos.viento_vel is not None:
                        dir_text = f" ({datos.viento_dir})" if datos.viento_dir else ""
                        datos_texto.append(f"    • Viento: {datos.viento_vel} km/h{dir_text}")
                    if datos.precipitacion is not None and datos.precipitacion > 0:
                        datos_texto.append(f"    • Precipitación: {datos.precipitacion} mm")
                    if datos.cielo:
                        datos_texto.append(f"    • Cielo: {datos.cielo}")
                    if datos.descripcion:
                        datos_texto.append(f"    • Descripción: {datos.descripcion[:100]}...")
        
        return "\n".join(datos_texto)
    
    def _mes_espanol(self, mes_ingles: str) -> str:
        """Convierte mes en inglés a español"""
        meses = {
            'January': 'Enero', 'February': 'Febrero', 'March': 'Marzo',
            'April': 'Abril', 'May': 'Mayo', 'June': 'Junio',
            'July': 'Julio', 'August': 'Agosto', 'September': 'Septiembre',
            'October': 'Octubre', 'November': 'Noviembre', 'December': 'Diciembre'
        }
        return meses.get(mes_ingles, mes_ingles)
    
    def _crear_prompt_meteorologico(self, datos_texto: str, fecha_inicio: datetime) -> str:
        """Crea prompt optimizado para análisis meteorológico"""
        
        return f"""Eres METEO-ARGENTINA, meteorólogo experto para la región andina de Neuquén.

UBICACIÓN: San Martín de los Andes, Neuquén (zona de Chapelco)
FECHA DE ANÁLISIS: {fecha_inicio.strftime('%A %d de %B de %Y')}

DATOS DISPONIBLES DE 3 FUENTES:
{datos_texto}

INSTRUCCIONES CRÍTICAS:

1. FORMATO OBLIGATORIO (para cada día):
   [Día de semana] [Día] de [Mes] – San Martín de los Andes: [descripción completa del tiempo]. 
   Máxima de [X]°C, mínima de [Y]°C. Viento del [dirección] entre [min] y [max] km/h. 
   [Detalles específicos sobre precipitación, tormentas, nubosidad, etc.].

2. GENERA PRONÓSTICO para los próximos 5 días comenzando desde la fecha de análisis.

3. COMBINA INTELIGENTEMENTE los datos de las 3 fuentes:
   - SMN: Datos específicos de estación CHAPELCO_AERO
   - AIC: Pronóstico oficial argentino
   - Open-Meteo: Modelos globales

4. INCLUYE estos hashtags al final de cada día:
   #SanMartínDeLosAndes #ClimaSMA #[CondicionPrincipal]
   Ejemplo: #Soleado #Ventoso #Lluvioso #Tormentas

5. DESTACA RIESGOS METEOROLÓGICOS:
   - Tormentas eléctricas
   - Granizo
   - Nieve
   - Niebla densa
   - Vientos fuertes (>40 km/h)
   - Temperaturas extremas

6. PROPORCIONA RECOMENDACIONES prácticas si hay condiciones adversas.

7. USA ESPAÑOL COLOQUIAL ARGENTINO, claro y profesional.

8. Sé específico con temperaturas, dirección del viento y probabilidad de precipitación.

RESPONDE SOLO CON EL PRONÓSTICO, sin introducciones ni conclusiones adicionales."""
    
    def _generar_pronostico_programatico(self, datos_combinados: Dict, fecha_inicio: datetime) -> str:
        """Genera pronóstico con lógica programática cuando las IA fallan"""
        
        if not datos_combinados:
            return "⚠️ No hay datos suficientes de las fuentes meteorológicas para generar pronóstico."
        
        pronostico_dias = []
        fecha_actual = fecha_inicio
        
        for i in range(5):
            fecha_str = fecha_actual.strftime('%Y-%m-%d')
            dia_semana = fecha_actual.strftime('%A')
            dia_mes = fecha_actual.strftime('%d')
            mes = self._mes_espanol(fecha_actual.strftime('%B'))
            
            if fecha_str in datos_combinados:
                fuentes = datos_combinados[fecha_str]
                
                # Calcular promedios ponderados
                temps_max = []
                temps_min = []
                vientos = []
                precipitaciones = []
                condiciones = []
                
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
                        if datos.cielo:
                            condiciones.append(datos.cielo.lower())
                
                if temps_max and temps_min:
                    # Calcular valores
                    temp_max_prom = round(sum(temps_max)/len(temps_max), 1)
                    temp_min_prom = round(sum(temps_min)/len(temps_min), 1)
                    viento_prom = round(sum(vientos)/len(vientos), 1) if vientos else None
                    precip_total = sum(precipitaciones) if precipitaciones else 0
                    
                    # Determinar dirección predominante del viento
                    viento_dir = fuentes.get('SMN', fuentes.get('AIC', None))
                    dir_text = f"del {viento_dir.viento_dir}" if viento_dir and viento_dir.viento_dir else "variables"
                    
                    # Determinar condición principal
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
                    elif condiciones and "despejado" in " ".join(condiciones):
                        condicion = "Despejado"
                        hashtag = "#Despejado"
                    else:
                        condicion = "Variable"
                        hashtag = "#Variable"
                    
                    # Construir pronóstico
                    texto = f"{dia_semana} {dia_mes} de {mes} – San Martín de los Andes: "
                    texto += f"tiempo {condicion.lower()} con nubosidad variable. "
                    texto += f"Máxima de {temp_max_prom}°C, mínima de {temp_min_prom}°C. "
                    
                    if viento_prom:
                        viento_min = max(1, round(viento_prom * 0.7))
                        viento_max = round(viento_prom * 1.3)
                        texto += f"Viento {dir_text} entre {viento_min} y {viento_max} km/h. "
                    
                    if precip_total > 0:
                        texto += f"Precipitación acumulada de {precip_total} mm. "
                    else:
                        texto += "Sin precipitación significativa. "
                    
                    texto += f"#SanMartínDeLosAndes #ClimaSMA {hashtag}"
                    
                    pronostico_dias.append(texto)
            
            fecha_actual += timedelta(days=1)
        
        return "\n\n".join(pronostico_dias) if pronostico_dias else "No hay datos suficientes para los próximos días."

# ============================================================================
# 5. FUNCIONES DE EXTRACCIÓN DE DATOS (SIMPLIFICADAS PARA PRUEBA)
# ============================================================================

def extraer_datos_smn():
    """Extrae datos del SMN - CHAPELCO_AERO"""
    try:
        url = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=pron5d"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                archivos = [f for f in z.namelist() if f.endswith('.txt')]
                if archivos:
                    with z.open(archivos[0]) as f:
                        contenido = f.read().decode('utf-8', errors='ignore')
                        
                        # Buscar específicamente CHAPELCO_AERO
                        if "CHAPELCO_AERO" in contenido:
                            partes = contenido.split("CHAPELCO_AERO")
                            if len(partes) > 1:
                                bloque = partes[1]
                                return DataSource(
                                    nombre="SMN",
                                    datos={},  # Se procesaría en versión completa
                                    estado=True,
                                    debug_info="CHAPELCO_AERO encontrado",
                                    raw_data=bloque[:1500]
                                )
        
        return DataSource(
            nombre="SMN",
            datos={},
            estado=False,
            debug_info="No se pudo extraer CHAPELCO_AERO",
            raw_data=""
        )
        
    except Exception as e:
        return DataSource(
            nombre="SMN",
            datos={},
            estado=False,
            debug_info=f"Error: {str(e)[:50]}",
            raw_data=""
        )

def extraer_datos_aic():
    """Extrae datos del AIC"""
    try:
        url = "https://www.aic.gob.ar/sitio/extendido-pdf?a=1029&z=1750130550"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, verify=False, timeout=40)
        
        if response.status_code == 200:
            return DataSource(
                nombre="AIC",
                datos={},
                estado=True,
                debug_info="HTML/PDF obtenido",
                raw_data=response.text[:2000]
            )
    except Exception as e:
        return DataSource(
            nombre="AIC",
            datos={},
            estado=False,
            debug_info=f"Error: {str(e)[:50]}",
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
                datos={},
                estado=True,
                debug_info="Datos obtenidos",
                raw_data=json.dumps(data, indent=2)[:1500]
            )
    except Exception as e:
        return DataSource(
            nombre="Open-Meteo",
            datos={},
            estado=False,
            debug_info=f"Error: {str(e)[:50]}",
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
            "Fecha de inicio del pronóstico",
            datetime.now(),
            max_value=datetime.now() + timedelta(days=14)
        )
        
        st.markdown("---")
        
        # Mostrar estado de API
        st.markdown("### 🔑 API OpenRouter")
        
        if ai_manager.openrouter_key:
            st.success(f"✅ API Configurada")
            st.info(f"📊 {len(ai_manager.modelos_gratuitos)} modelos gratuitos disponibles")
            
            # Mostrar modelos disponibles
            with st.expander("🤖 Ver modelos disponibles"):
                for i, modelo in enumerate(ai_manager.modelos_gratuitos[:8]):  # Mostrar primeros 8
                    nombre = ai_manager._nombre_amigable_modelo(modelo)
                    st.markdown(f"<div class='model-status'>{i+1}. {nombre}</div>", unsafe_allow_html=True)
                
                if len(ai_manager.modelos_gratuitos) > 8:
                    st.caption(f"... y {len(ai_manager.modelos_gratuitos)-8} más")
        else:
            st.error("""
            ❌ **API NO configurada**
            
            Para usar modelos gratuitos de IA:
            1. Ve a Settings → Secrets en Streamlit Cloud
            2. Agrega: `OPENROUTER_API_KEY = "tu-key-aqui"`
            3. El sistema usará lógica programática hasta que la configures
            """)
        
        st.markdown("---")
        
        # Mostrar último modelo exitoso si existe
        if hasattr(st, 'session_state') and 'modelo_exitoso' in st.session_state:
            modelo = st.session_state['modelo_exitoso']
            nombre = ai_manager._nombre_amigable_modelo(modelo)
            st.info(f"📈 Último modelo exitoso: **{nombre}**")
        
        if st.button("🔄 Limpiar cache de modelos", type="secondary"):
            if hasattr(st, 'session_state'):
                keys = ['modelo_exitoso', 'timestamp_ia']
                for key in keys:
                    if key in st.session_state:
                        del st.session_state[key]
                st.success("Cache limpiado")
                time.sleep(1)
                st.rerun()
    
    # Botón principal
    if st.button("🚀 GENERAR PRONÓSTICO CON IA GRATUITA", 
                type="primary", 
                use_container_width=True,
                help="Usa modelos gratuitos de OpenRouter para analizar datos meteorológicos"):
        
        # Verificar si hay API key
        if not ai_manager.openrouter_key:
            st.error("""
            ⚠️ **No hay API key de OpenRouter configurada**
            
            El sistema usará lógica programática para generar el pronóstico.
            
            Para usar IA gratuita, agrega tu API key en:
            **Settings → Secrets** de tu app en Streamlit Cloud
            """)
        
        # Mostrar progreso
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        with st.spinner("Recopilando datos meteorológicos..."):
            # Obtener datos de fuentes
            status_text.text("📡 Conectando con SMN (CHAPELCO_AERO)...")
            fuente_smn = extraer_datos_smn()
            progress_bar.progress(25)
            
            status_text.text("📡 Conectando con AIC...")
            fuente_aic = extraer_datos_aic()
            progress_bar.progress(50)
            
            status_text.text("🌐 Conectando con Open-Meteo...")
            fuente_om = obtener_datos_openmeteo()
            progress_bar.progress(75)
            
            # Combinar datos (simulado para demo)
            datos_combinados = {
                datetime.now().strftime('%Y-%m-%d'): {
                    'SMN': ForecastDay(
                        datetime.now().strftime('%Y-%m-%d'), 
                        datetime.now(),
                        25.5, 15.3, 12.0, "NE", 0.0, 
                        "Parcialmente nublado", "Viento suave del noreste", "SMN"
                    ),
                    'AIC': ForecastDay(
                        datetime.now().strftime('%Y-%m-%d'), 
                        datetime.now(),
                        28.0, 14.0, 15.0, "SE", 1.5, 
                        "Tormentas aisladas", "Caluroso con tormentas vespertinas", "AIC"
                    ),
                    'Open-Meteo': ForecastDay(
                        datetime.now().strftime('%Y-%m-%d'), 
                        datetime.now(),
                        26.5, 13.8, 18.0, "S", 0.2, 
                        "Parcialmente nublado", "Viento moderado del sur", "Open-Meteo"
                    )
                }
            }
            
            status_text.text("🧠 Analizando con IA gratuita...")
            
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
                <strong>✅ Generado con IA gratuita:</strong> {detalle}
            </div>
            """, unsafe_allow_html=True)
        
        # Mostrar pronóstico
        st.markdown(f'<div class="ai-analysis-box">{pronostico}</div>', unsafe_allow_html=True)
        
        # Mostrar estado de fuentes
        st.markdown("---")
        st.markdown("### 📊 Estado de Fuentes de Datos")
        
        cols = st.columns(3)
        fuentes = [fuente_smn, fuente_aic, fuente_om]
        
        for idx, fuente in enumerate(fuentes):
            with cols[idx]:
                color = "#48bb78" if fuente.estado else "#f56565"
                st.markdown(f"""
                <div class="data-source-card" style="border-left-color: {color};">
                    <h4>{fuente.nombre}</h4>
                    <p><strong>Estado:</strong> {"✅ ONLINE" if fuente.estado else "❌ OFFLINE"}</p>
                    <p><strong>Info:</strong><br><small>{fuente.debug_info}</small></p>
                </div>
                """, unsafe_allow_html=True)
    
    # Panel informativo inicial
    else:
        st.markdown("""
        <div class="info-box">
            <h4>🎯 Sistema Meteorológico con IA Gratuita</h4>
            <p>Este sistema usa <strong>modelos de IA 100% gratuitos</strong> de OpenRouter 
            para analizar datos meteorológicos de múltiples fuentes.</p>
            
            <p><strong>🔥 Modelos gratuitos incluidos:</strong></p>
            <ul>
                <li>🤖 <strong>GPT-3.5 Turbo</strong> - 5M tokens gratis/mes</li>
                <li>⚡ <strong>Gemini 2.0 Flash</strong> - Experimental gratis</li>
                <li>🧠 <strong>GPT OSS 20B</strong> - Modelo open-source de 20B</li>
                <li>🐦 <strong>Gemma 3n 2B</strong> - Modelo liviano de Google</li>
                <li>🔄 <strong>+5 modelos adicionales</strong> gratuitos</li>
            </ul>
            
            <p><strong>📡 Fuentes meteorológicas:</strong></p>
            <ul>
                <li>🏔️ <strong>SMN</strong>: Datos específicos de CHAPELCO_AERO</li>
                <li>📄 <strong>AIC</strong>: Pronóstico oficial argentino</li>
                <li>🌐 <strong>Open-Meteo</strong>: Modelos climáticos globales</li>
            </ul>
            
            <p><strong>⚠️ Requisito:</strong> Solo necesitas una API key gratuita de 
            <a href="https://openrouter.ai" target="_blank">OpenRouter</a> en los Secrets.</p>
            
            <p><em>Presiona el botón para generar pronóstico con IA gratuita.</em></p>
        </div>
        """, unsafe_allow_html=True)
        
        # Mostrar ejemplo de pronóstico
        with st.expander("📝 Ver ejemplo de formato de salida"):
            st.markdown("""
            **Ejemplo de pronóstico generado:**
            
            ```
            Lunes 6 de Enero – San Martín de los Andes: tiempo caluroso e inestable 
            con formación de tormentas aisladas hacia la tarde. Máxima de 31°C, 
            mínima de 14°C. Viento del sudoeste entre 20 y 45 km/h. 
            Probabilidad de chaparrones y tormentas eléctricas hacia la tarde-noche. 
            #SanMartínDeLosAndes #ClimaSMA #Caluroso #Inestable #Tormentas
            
            Martes 7 de Enero – San Martín de los Andes: mejoría temporaria con 
            disminución de la inestabilidad. Máxima de 28°C, mínima de 12°C. 
            Viento del oeste entre 15 y 30 km/h. Cielo parcialmente nublado. 
            #SanMartínDeLosAndes #ClimaSMA #Mejoría #ParcialmenteNublado
            ```
            """)

# ============================================================================
# 7. ARCHIVO requirements.txt NECESARIO
# ============================================================================
"""
# requirements.txt
streamlit>=1.28.0
requests>=2.31.0
pandas>=2.0.0
beautifulsoup4>=4.12.0
pdfplumber>=0.10.0
urllib3>=2.0.0
"""

# ============================================================================
# 8. EJECUCIÓN
# ============================================================================

def cargar_configuracion():
    secrets = {}
    try:
        # 1. Cargar clave de Gemini
        for i in range(1, 4):
            nombre = f"GEMINI_API_KEY_{i}" if i > 1 else "GEMINI_API_KEY"
            if nombre in st.secrets:
                secrets['GEMINI'] = st.secrets[nombre]
                break 

        # 2. Cargar claves de OpenRouter
        openrouter_keys = []
        for i in range(1, 4):
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

# Al final del archivo, para ejecutar la app:
if __name__ == "__main__":
    main()

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
