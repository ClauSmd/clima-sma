import streamlit as st
# ... (mantener imports previos)

# Diccionario de iconos basado en AIC
ICONOS_CIELO = {
    "Despejado": "☀️",
    "Mayormente Despejado": "🌤️",
    "Parcialmente Nublado": "⛅",
    "Nublado": "☁️",
    "Cubierto": "🌥️",
    "Inestable": "🌦️",
    "Lluvias Débiles y Dispersas": "🌧️",
    "Lluvia": "🌧️",
    "Nieve": "❄️"
}

# --- LÓGICA DE PROCESAMIENTO ---
if st.button("🚀 GENERAR REPORTE ESTILO AIC"):
    # ... (mantener lógica de extracción y filtrado previa)

    if d_aic["status"] == "OK" and d_om["status"] == "OK":
        # Preparación de datos fusionados y redondeados
        dias_reporte = []
        for i in range(dias_compatibles):
            idx_aic = i * 2
            
            # Redondeo lógico sin decimales
            t_max = int(round((aic_f[idx_aic]['max'] + om_f[i]['max']) / 2))
            t_min = int(round((aic_f[idx_aic+1]['max'] + om_f[i]['min']) / 2))
            v_vel = int(round((aic_f[idx_aic]['viento'] + om_f[i]['viento']) / 2))
            v_raf = int(round(om_f[i]['rafaga']))
            
            condicion = aic_f[idx_aic]['cielo']
            icono = ICONOS_CIELO.get(condicion, "🌡️")
            
            dias_reporte.append({
                "fecha": aic_f[idx_aic]['fecha_obj'].strftime("%d/%m"),
                "dia_semana": dias_semana[aic_f[idx_aic]['fecha_obj'].weekday()],
                "cielo": f"{icono} {condicion}",
                "temp": f"{t_max}° / {t_min}°",
                "viento": f"{v_vel} km/h",
                "rafagas": f"{v_raf} km/h",
                "dir": aic_f[idx_aic]['dir']
            })

        # --- VISUALIZACIÓN ESTILO TABLA AIC ---
        st.subheader("🎯 Pronóstico Ponderado (Formato AIC)")
        
        # Creamos columnas dinámicas según la cantidad de días procesados
        cols = st.columns(len(dias_reporte))
        for idx, col in enumerate(cols):
            d = dias_reporte[idx]
            with col:
                st.markdown(f"**{d['dia_semana']} {d['fecha']}**")
                st.info(f"**Cielo**\n{d['cielo']}")
                st.metric("Temp (Máx/Mín)", d['temp'])
                st.write(f"**Viento:** {d['viento']}")
                st.write(f"**Ráfagas:** {d['rafagas']}")
                st.write(f"**Dirección:** {d['dir']}")

        # --- TEXTO FINAL PARA COPIAR (CON IA O SIN IA) ---
        reporte_texto = ""
        for d in dias_reporte:
            reporte_texto += f"{d['dia_semana']} {d['fecha']} – SMA: {d['cielo']}, {d['temp']}C. Viento {d['viento']} (Ráf. {d['rafagas']}). #ClimaSMA\n"
        
        st.markdown("---")
        if usa_ia:
            prompt = f"Resume este pronóstico en un párrafo profesional usando la síntesis: {d_aic['sintesis']}\nDatos: {reporte_texto}"
            reporte_ia, modelo = consultar_ia_robusta(prompt)
            if reporte_ia:
                st.success(f"Optimizado con {modelo}")
                st.write(reporte_ia)
        
        st.text_area("Copiar Reporte Texto:", value=reporte_texto + f"\nSÍNTESIS: {d_aic['sintesis']}", height=200)

        # ... (mantener los expanders de datos crudos al final)
