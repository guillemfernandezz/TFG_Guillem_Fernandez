"""
Descripción: Fichero que devuelve un GeoJSON para comprobar la cobertura espacial de los datos de Wikidata extraídos en el script 2 de Catalunya
"""

import requests
import json
import math
import sys

WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"

def log(missatge):
    print(f"[QA Radar] {missatge}")
    sys.stdout.flush()

def crear_poligon_circular(lat, lon, radi_km, num_punts=32):
    """
    Calcula matemàticament un polígon (cercle) al voltant d'unes coordenades.
    Fórmula de la trigonometria esfèrica de la Terra.
    """
    radi_terra_km = 6371.0
    coordenades_poligon = []
    
    for i in range(num_punts):
        angle = math.radians(float(i) / num_punts * 360.0)
        
        lat1 = math.radians(lat)
        lon1 = math.radians(lon)
        
        # Càlcul de la nova coordenada del vèrtex del cercle
        lat2 = math.asin(math.sin(lat1) * math.cos(radi_km / radi_terra_km) + 
                         math.cos(lat1) * math.sin(radi_km / radi_terra_km) * math.cos(angle))
        
        lon2 = lon1 + math.atan2(math.sin(angle) * math.sin(radi_km / radi_terra_km) * math.cos(lat1), 
                                 math.cos(radi_km / radi_terra_km) - math.sin(lat1) * math.sin(lat2))
        
        coordenades_poligon.append([math.degrees(lon2), math.degrees(lat2)])
    
    # Tanquem el polígon repetint el primer punt
    coordenades_poligon.append(coordenades_poligon[0])
    
    return [coordenades_poligon]

def generar_geojson_cobertura():
    log("Descarregant els centres dels 947 municipis de Catalunya...")
    
    query = """
    SELECT DISTINCT ?muniLabel ?coords WHERE {
      ?muni wdt:P31 wd:Q33146843;
            wdt:P131* wd:Q5705;
            wdt:P625 ?coords.
      SERVICE wikibase:label { bd:serviceParam wikibase:language "ca". }
    }
    """
    
    headers = {"User-Agent": "TFG-IDE-Cultural-QA (contacte@universitat.edu)", "Accept": "application/sparql-results+json"}
    
    try:
        res = requests.get(WIKIDATA_ENDPOINT, params={'query': query}, headers=headers, timeout=30)
        dades = res.json()['results']['bindings']
        
        features = []
        log("Calculant polígons de 16km per a cada municipi...")
        
        for item in dades:
            nom = item['muniLabel']['value']
            coord_raw = item['coords']['value']
            coord_clean = coord_raw.replace("Point(", "").replace(")", "").strip()
            lon_str, lat_str = coord_clean.split(" ")
            lon, lat = float(lon_str), float(lat_str)
            
            # Generem el polígon de 16km
            poligon = crear_poligon_circular(lat, lon, 16.0)
            
            feature = {
                "type": "Feature",
                "properties": {
                    "municipi": nom,
                    "radi_km": 16,
                    "color": "#ff0000",
                    "fillOpacity": 0.2
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": poligon
                }
            }
            features.append(feature)
            
        geojson_sencer = {
            "type": "FeatureCollection",
            "features": features
        }
        
        # Guardem el fitxer
        with open('cobertura_radar_16km.geojson', 'w', encoding='utf-8') as f:
            json.dump(geojson_sencer, f, ensure_ascii=False)
            
        log(f"✅ ÈXIT! Fitxer 'cobertura_radar_16km.geojson' creat amb {len(features)} anells de radar.")
        
    except Exception as e:
        log(f"❌ Error generant la cobertura: {e}")

if __name__ == "__main__":
    print("\n" + "═"*55)
    print(" 📡 AUDITORIA DE COBERTURA ESPACIAL (RADAR 16KM)")
    print("═"*55)
    generar_geojson_cobertura()
    print("═"*55 + "\n")