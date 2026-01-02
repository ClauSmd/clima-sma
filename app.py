import streamlit as st
import google.generativeai as genai

st.title("🛠️ Diagnóstico de Conexión Gemini")

try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    
    st.write("### Buscando modelos disponibles...")
    
    # Intentamos listar los modelos disponibles para tu llave
    modelos_disponibles = []
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            modelos_disponibles.append(m.name)
    
    if modelos_disponibles:
        st.success("¡Conexión exitosa!")
        st.write("Tu llave permite usar estos modelos:")
        st.info(modelos_disponibles)
        st.write("👉 **Copia el nombre del primero que aparezca en la lista y dímelo.**")
    else:
        st.warning("La llave conecta, pero no encontró modelos con permiso de generación.")

except Exception as e:
    st.error(f"Error crítico de conexión: {e}")
    st.write("Esto confirma que el problema es la comunicación entre la API Key y el servidor.")
