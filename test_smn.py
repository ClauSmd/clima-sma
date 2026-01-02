import requests
import zipfile
import io
import re

def probar_lectura_smn():
    url_zip = "https://ws.smn.gob.ar/export/pronostico-txt.zip"
    print(f"--- Iniciando prueba de descarga desde: {url_zip} ---")
    
    try:
        r = requests.get(url_zip, timeout=10)
        r.raise_for_status()
        print("✅ Descarga exitosa del ZIP.")
        
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            # Listamos archivos internos para ver qué hay
            archivos = z.namelist()
            print(f"📂 Archivos dentro del ZIP: {archivos}")
            
            nombre_txt = [f for f in archivos if f.endswith('.txt')][0]
            with z.open(nombre_txt) as f:
                contenido = f.read().decode('utf-8', errors='ignore')
                
                # Prueba de búsqueda flexible (Regex)
                patron_chapelco = re.compile(r"CHAPELCO[_\s]AERO", re.IGNORECASE)
                match_inicio = patron_chapelco.search(contenido)
                
                if match_inicio:
                    print("🎯 ¡Estación CHAPELCO AERO encontrada!")
                    # Extraemos un bloque de texto para ver la estructura
                    bloque = contenido[match_inicio.start():match_inicio.start()+1000]
                    
                    # Probamos el procesador de datos
                    dias_datos = {}
                    lineas = bloque.strip().split('\n')
                    for linea in lineas:
                        # Buscamos: Fecha, Temp, Viento
                        m = re.search(r'(\d{2})/([A-Z]{3})/(\d{4}).*?(\d+\.\d+).*?\|.*?(\d+)', linea)
                        if m:
                            fecha = f"{m.group(1)} {m.group(2)}"
                            temp = float(m.group(4))
                            viento = int(m.group(5))
                            print(f"   📍 Detectado: {fecha} | Temp: {temp}°C | Viento: {viento}km/h")
                else:
                    print("❌ No se encontró la palabra CHAPELCO_AERO en el texto.")
                    # Opcional: imprimir las primeras 10 estaciones para ver cómo se llaman
                    estaciones = re.findall(r'^[A-Z_\s]+$', contenido, re.MULTILINE)
                    print(f"Lista parcial de estaciones encontradas: {estaciones[:10]}")

    except Exception as e:
        print(f"🛑 Error en la prueba: {e}")

if __name__ == "__main__":
    probar_lectura_smn()
