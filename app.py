def sintetizar_con_ia(prompt):
    """
    Intenta generar el reporte con Gemini 3. 
    Si falla (por cuota 429 o por nombre 404), salta al 1.5.
    """
    # Identificadores limpios para evitar el error 404 en v1beta
    modelos_a_probar = [
        'gemini-3-flash-preview', 
        'gemini-1.5-flash'
    ]
    
    for nombre_modelo in modelos_a_probar:
        try:
            # Quitamos el prefijo 'models/' para que la API lo tome directo
            modelo_ai = genai.GenerativeModel(nombre_modelo)
            response = modelo_ai.generate_content(prompt)
            return response.text, nombre_modelo
        except Exception as e:
            # Si el modelo no se encuentra o la cuota se agotó, probamos el siguiente
            if "404" in str(e) or "429" in str(e):
                continue
            else:
                # Si es un error distinto (ej. falta de internet), lo reportamos
                return f"Error técnico: {e}", None
                
    return "Todos los modelos están saturados. Reintentá en 1 minuto.", None
