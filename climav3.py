import streamlit as st
import requests
import pdfplumber
import io
import json
import google.generativeai as genai
from datetime import datetime, timedelta
import time

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Weather Aggregator SMA", layout="wide")

ICONOS_CIELO = {
    "Despejado": "☀️", "Mayormente Despejado": "🌤️", "Parcialmente Nublado": "⛅",
    "Nublado": "☁️", "Cubierto": "🌥️", "Inestable": "🌦️", 
    "Lluvias Débiles y Dispersas": "🌧️", "Lluvia": "🌧️", "Nieve": "❄️"
}

st.sidebar.title("Configuración")
fecha_inicio = st.sidebar.date_input("📅 Fecha de inicio", datetime.now().date())
usa_ia = st.sidebar.toggle("🤖 Activar Inteligencia Artificial", value=True)

# --- 2. FUNCIONES DE EXTRACCIÓN (AIC y Open-Meteo) ---
# [Se mantienen las funciones get_aic_data y get_open_meteo_data del historial]

# --- 3. LÓGICA DE UNIFICACIÓN Y FUSIÓN ---
if st.button("🚀 GENERAR PRONÓSTICO 5 DÍAS"):
    with st.spinner("Fusionando fuentes..."):
        d_aic = get_aic_data() # Extrae del PDF
        d_om = get_open_meteo_data() # Extrae de API

    if d_aic["status"] == "OK" and d_om["status"] == "OK":
        
        # --- PASO 1: UNIFICAR AIC POR FECHA (Fusión Día/Noche) ---
        aic_unificado = {}
        for d in d_aic["datos"]:
            f = d["fecha_obj"]
            if f not in aic_unificado:
                aic_unificado[f] = d # Tomamos el primer registro (Día) como base
            else:
                # Si es la misma fecha, solo actualizamos si el nuevo dato tiene temp más alta
                if d["max"] > aic_unificado[f]["max"]:
                    aic_unificado[f]["max"] = d["max"]

        # --- PASO 2: EMPAREJAR Y PROCESAR EXACTAMENTE 5 DÍAS ---
        pronostico_final = []
        fechas_procesadas = 0
        
        for i in range(10): # Buscamos en el margen de 10 días
            fecha_actual = fecha_inicio + timedelta(days=i)
            
            if fecha_actual in aic_unificado and fechas_procesadas < 5:
                # Datos de ambas fuentes para la misma fecha
                data_aic = aic_unificado[fecha_actual]
                # Buscamos la misma fecha en OpenMeteo
                data_om = next((x for x in d_om["datos"] if x["fecha_obj"] == fecha_actual), None)
                
                if data_om:
                    # Redondeo lógico (enteros)
                    t_max = int(round((data_aic['max'] + data_om['max']) / 2))
                    t_min = int(round(data_om['min'])) # OpenMeteo es más preciso en mínimas
                    v_vel = int(round((data_aic['viento'] + data_om['viento']) / 2))
                    v_raf = int(round(data_om['rafaga']))
                    
                    icono = ICONOS_CIELO.get(data_aic['cielo'], "🌡️")
                    
                    pronostico_final.append({
                        "fecha": fecha_actual,
                        "texto": f"{fecha_actual.strftime('%d/%m')}: {icono} {data_aic['cielo']}, {t_max}°/{t_min}°. Viento {v_vel}km/h (Ráf. {v_raf}km/h).",
                        "detalles": f"**{fecha_actual.strftime('%A %d')}** – SMA: {data_aic['cielo']}, máx {t_max}°, mín {t_min}°. Viento {v_vel} km/h con ráfagas de {v_raf} km/h. #ClimaSMA"
                    })
                    fechas_procesadas += 1

        # --- 4. VISUALIZACIÓN ---
        st.subheader("🎯 Pronóstico Final Ponderado (5 Días)")
        
        reporte_completo = ""
        cols = st.columns(5)
        for idx, p in enumerate(pronostico_final):
            with cols[idx]:
                st.metric(p["fecha"].strftime("%d/%m"), p["texto"].split(",")[1].split("/")[0].strip())
                st.write(p["texto"].split(":")[1].split(",")[0])
            reporte_completo += p["detalles"] + "\n"

        st.markdown("---")
        if usa_ia:
            prompt = f"Redacta profesionalmente estos 5 días: {reporte_completo}. Síntesis: {d_aic['sintesis']}"
            res, mod = consultar_ia_cascada(prompt) #
            if res:
                st.success(f"Optimizado con {mod}")
                st.info(res)
            else:
                st.warning("Fallo IA. Reporte Manual:")
                st.info(reporte_completo + f"\nSÍNTESIS: {d_aic['sintesis']}")
        else:
            st.info(reporte_completo + f"\nSÍNTESIS: {d_aic['sintesis']}")

        # --- 5. DATOS CRUDOS SIMPLIFICADOS (DESPLEGABLES) ---
        st.markdown("---")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            with st.expander("📊 Datos Open-Meteo (Simplificado)"):
                for o in d_om["datos"][:5]:
                    st.write(f"📅 {o['fecha_obj']}: {o['max']}°C / {o['min']}°C | Ráfagas: {o['rafaga']}km/h")
        with col_c2:
            with st.expander("📄 Datos AIC (Unificados)"):
                for f, a in aic_unificado.items():
                    st.write(f"📅 {f}: {a['cielo']} | Máxima: {a['max']}°C")

    else:
        st.error("Error al obtener datos.")
