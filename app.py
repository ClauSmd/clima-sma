import streamlit as st
import pandas as pd
import datetime
from fusion_engine import FusionEngine
from ai_reporter import MeteorologistBot
import os
import textwrap

# Page Config
st.set_page_config(page_title="Pronóstico SMA - Fusión", page_icon="🌦️", layout="wide")

# Custom CSS for AIC Style
st.markdown("""
<style>
    .main {
        background-color: #f0f2f6;
    }
    .forecast-card {
        background-color: white;
        border: 1px solid #ddd;
        border-radius: 5px;
        padding: 10px;
        text-align: center;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
        height: 100%;
    }
    .date-header {
        font-weight: bold;
        font-size: 1.1em;
        background-color: #005a87;
        color: white;
        padding: 5px;
        border-radius: 3px 3px 0 0;
        margin-bottom: 10px;
        text-transform: capitalize;
    }
    .param-row {
        margin: 5px 0;
        font-size: 0.9em;
        border-bottom: 1px solid #eee;
        padding-bottom: 3px;
    }
    .param-label {
        font-weight: bold;
        color: #555;
        font-size: 0.8em;
        display: block;
    }
    .temp-high { color: #d32f2f; font-weight: bold; }
    .temp-low { color: #1976d2; font-weight: bold; }
    .ai-report-box {
        background-color: #e3f2fd;
        border-left: 5px solid #2196f3;
        padding: 15px;
        margin-top: 20px;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.title("🌦️ Weather Aggregator SMA")
st.markdown("**Fusión de Fuentes:** SMN (Nacional) + AIC (Cuenca) + Open-Meteo (Ráfagas)")

# Sidebar for API Key
with st.sidebar:
    st.header("Configuración")
    api_key_input = st.text_input("Gemini API Key", type="password", value=os.environ.get("GOOGLE_API_KEY", ""))
    if api_key_input:
        os.environ["GOOGLE_API_KEY"] = api_key_input

# Main Logic
try:
    with st.spinner("Fusionando datos de SMN, AIC y Open-Meteo..."):
        engine = FusionEngine()
        forecast_data = engine.get_5_day_forecast()

    # Layout: Premium Card Grid
    st.markdown("""
    <style>
        .weather-card {
            background-color: var(--secondary-background-color);
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            border: 1px solid var(--secondary-background-color);
            overflow: hidden;
            transition: transform 0.2s;
            margin-bottom: 20px;
        }
        .weather-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 12px rgba(0,0,0,0.15);
        }
        .card-header {
            background-color: #007bff; /* SMN Blue stays as brand color */
            color: white;
            padding: 10px;
            text-align: center;
            font-weight: 600;
            font-size: 1.1em;
            letter-spacing: 0.5px;
        }
        .card-body {
            padding: 15px;
            text-align: center;
            color: var(--text-color);
        }
        .weather-icon {
            font-size: 3.5em; /* Large Icon */
            margin: 10px 0;
            text-shadow: 0px 0px 10px rgba(128,128,128,0.2);
        }
        .sky-text {
            font-size: 0.9em;
            color: var(--text-color);
            opacity: 0.8;
            margin-bottom: 15px;
            text-transform: capitalize;
            height: 40px; /* Fixed height for alignment */
            display: flex;
            align-items: center;
            justify-content: center;
            line-height: 1.2;
        }
        .temp-container {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 15px;
            margin-bottom: 15px;
            background: rgba(128,128,128,0.1); /* Transparent grey compatible with both modes */
            padding: 8px;
            border-radius: 8px;
        }
        .temp-box {
            display: flex;
            flex-direction: column;
        }
        .temp-val-max { font-size: 1.8em; font-weight: 700; color: #ff6b6b; line-height: 1; } /* Lighter red for visibility on dark */
        .temp-val-min { font-size: 1.4em; font-weight: 600; color: #4dabf7; line-height: 1; } /* Lighter blue for visibility on dark */
        .temp-label { font-size: 0.7em; color: var(--text-color); opacity: 0.7; text-transform: uppercase; margin-top: 4px; }
        
        .stat-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            font-size: 0.85em;
            margin-top: 10px;
            border-top: 1px solid rgba(128,128,128,0.2);
            padding-top: 10px;
        }
        .stat-box {
            background-color: rgba(128,128,128,0.05);
            padding: 5px;
            border-radius: 6px;
        }
        .stat-value { font-weight: 600; color: var(--text-color); }
        .stat-label { font-size: 0.8em; color: var(--text-color); opacity: 0.7; }
        .source-tag {
            margin-top: 10px;
            font-size: 0.7em;
            color: var(--text-color);
            opacity: 0.5;
            text-align: right;
            font-style: italic;
        }
    </style>
    """, unsafe_allow_html=True)

    cols = st.columns(5)
    for i, col in enumerate(cols):
        day = forecast_data[i]
        
        # Icon Logic
        desc = day['sky_desc'].lower()
        icon = "coudy" # fallback
        emoji = "☁️"
        
        if "despejado" in desc or "soleado" in desc: emoji = "☀️"
        elif "parcialmente" in desc: emoji = "⛅"
        elif "lluvia" in desc or "llovizna" in desc: emoji = "🌧️"
        elif "nieve" in desc: emoji = "❄️"
        elif "tormenta" in desc: emoji = "⛈️"
        elif "niebla" in desc: emoji = "🌫️"
        elif "nublado" in desc or "cubierto" in desc: emoji = "☁️"
        
        
        src_clean = "Fusión"
        if "AIC" in day['source']: src_clean = "AIC + Fusión"
        
        html_card = f"""
<div class="weather-card">
<div class="card-header">{day['date_str']}</div>
<div class="card-body">
<div class="sky-text">{day['sky_desc']}</div>
<div class="weather-icon">{emoji}</div>
<div class="temp-container">
<div class="temp-box">
<span class="temp-val-max">{day['max_temp']}°</span>
<span class="temp-label">Máx</span>
</div>
<div style="width:1px; height:30px; background:#ddd;"></div>
<div class="temp-box">
<span class="temp-val-min">{day['min_temp']}°</span>
<span class="temp-label">Mín</span>
</div>
</div>
<div class="stat-grid">
<div class="stat-box">
<div class="stat-label">Viento</div>
<div class="stat-value">{day['wind_speed']} km/h</div>
<div style="font-size:0.7em; color:#888">{day['wind_dir']}</div>
</div>
<div class="stat-box">
<div class="stat-label">Ráfagas</div>
<div class="stat-value">{day['gusts']} km/h</div>
</div>
</div>
<div class="source-tag">Fuente: {src_clean}</div>
</div>
</div>
"""
        
        with col:
            st.markdown(html_card, unsafe_allow_html=True)


    st.markdown("---")
    st.subheader("🤖 Meteorólogo Virtual (IA)")
    
    # Selection for AI Report
    selected_day_idx = st.selectbox("Elegir día para generar reporte:", range(5), format_func=lambda x: forecast_data[x]['date_str'])
    
    if st.button("Generar Reporte (IA / Automático)"):
        # We allow running without key now (falls back to template)
        if os.environ.get("GOOGLE_API_KEY"):
             os.environ["GOOGLE_API_KEY"] = os.environ["GOOGLE_API_KEY"].strip()
        
        bot = MeteorologistBot()
        day_data = forecast_data[selected_day_idx]
        with st.spinner(f"Generando reporte para el {day_data['date_str']}..."):
            report = bot.generate_report(day_data)
            
            st.markdown(f"""
            <div class="ai-report-box">
                <h4>🎙️ Reporte del Día</h4>
                <p style="font-family: monospace; font-size: 1.1em;">{report}</p>
            </div>
            """, unsafe_allow_html=True)
            
    st.markdown("---")
    with st.expander("🔎 Desglose de Datos por Fuente (Auditoría)", expanded=True):
        st.info("Aquí se muestran los datos crudos extraídos antes de la ponderación.")
        for day in forecast_data:
            st.markdown(f"**{day['date_str']}**")
            d = day['debug']
            
            # Updated to show all 5 sources
            c1, c2, c3, c4, c5 = st.columns(5)
            with c1:
                st.caption("🟠 Open-Meteo (50%)")
                if d['om']: st.json(d['om'])
                else: st.warning("-")
            with c2:
                st.caption("🔵 AIC (PDF)")
                if d['aic']: st.json(d['aic'])
                else: st.warning("-")
            with c3:
                st.caption("⚪ SMN")
                st.text(d['smn'])
            with c4:
                st.caption("🌤️ Met.no / AW")
                if d['aw']: st.json(d['aw']) # Showing Met.no data here as per fusion logic
                else: st.warning("-")
            with c5:
                st.caption("🪁 Windguru")
                st.text(d['wg'])
            st.markdown("---")

except Exception as e:
    st.error(f"Ocurrió un error crítico: {e}")
    st.exception(e)

