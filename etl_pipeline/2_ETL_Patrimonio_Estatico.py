import requests
import psycopg2
from psycopg2.extras import execute_batch
from datetime import datetime
import sys


# 1. Configuración del entorno
DB_CONFIG = {
    'dbname': 'events_db',
    'user' : 'postgres',
    'password': 'Tucans97',
    'host': 'localhost',
    'port': '5432'
}

# Endpoint de Wikidata para consultas SPARQL
WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"

def log(missatge):
    temps = datetime.now().strftime("%H:%M:%S")
    print(f"[{temps}] {missatge}")
    sys.stdout.flush()
    
# 2. Preparar la BBDD
def preparar_base_de_dades():
    """
    Creamos el esquema y la tabla en PostGIS si no existiera
    """
    log("Preparando la base de datos...")
    sql_setup = """
        CREATE SCHEMA IF NOT EXISTS ide_cultural;

        CREATE TABLE IF NOT EXISTS ide_cultural.patrimoni_monumental (
            id_wikidata VARCHAR PRIMARY KEY,
            nom VARCHAR(512),
            imatge_url VARCHAR(1024),
            lat NUMERIC(10, 6),
            lon NUMERIC(10, 6),
            geometry geometry(Point, 4326)
        );
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute(sql_setup)
        conn.commit()
        log("Capa patrimonio monumental preparada.")
    except Exception as e:
        log(f"Error preparando la base de datos: {e}")
    finally:
        if 'cursor': cursor.close()
        if 'conn': conn.close()
        
# 3. Extract (Consulta SPARQL a Wikidata)
def extreure_dades_wikidata():
    log("Iniciando la extracción de datos de Wikidata...")
    
    query = """
    SELECT DISTINCT ?monument ?monumentLabel ?lat ?lon ?imatge
    WHERE {
        # 1. Ubicat a Catalunya (o qualsevol de les seves subdivisions)
        ?monument wdt:P131* wd:Q5705;       

        # 2. Amb algun estatus de protecció patrimonial (BCIN, BCIL, etc)
                wdt:P1435 ?proteccio;     
                
        # 3. I amb coordenades exactes
                p:P625 ?coordenada.       

        # Extraiem Latitud i Longitud pures
        ?coordenada psv:P625 ?node_coord.
        ?node_coord wikibase:geoLatitude ?lat.
        ?node_coord wikibase:geoLongitude ?lon.

        # 4. (Opcional) Si té foto, la volem
        OPTIONAL { ?monument wdt:P18 ?imatge. }

        # Servei de traducció de Wikidata
        SERVICE wikibase:label { bd:serviceParam wikibase:language "ca,es,en". }
    }
    LIMIT 4000
    """
    
    # Si no nos identificamos Wikidata nos bloqueará por exceso de consultas
    headers = {
        "User-Agent": "TFG-IDE-Cultural (guillemfernandezz@gmail.com)",
        "Accept": "application/sparql-results+json"
    }
    
    try:
        response = requests.get(WIKIDATA_ENDPOINT, params={'query': query}, headers=headers, timeout=60)
        response.raise_for_status()
        dades = response.json()
        resultats = dades['results']['bindings']
        log(f"Extracción completada. {len(resultats)} registros obtenidos.")
        return resultats
    except Exception as e:
        log(f"Error extrayendo datos de Wikidata: {e}")
        sys.exit(1)
        
# 4. Transform (Adaptamos el JSON de Wikidata)
def transformar_dades(dades_brutes):
    log("Transformando los datos...")
    dades_netes = []
    
    for item in dades_brutes:
        try:
            id_completo = item.get("monument", {}).get("value", "")
            id_net = id_completo.split("/")[-1]
            
            event = {
                "id_wikidata": id_net,
                "nom": item.get("monumentLabel", {}).get("value", "Monument sense nom"),
                "imatge_url": item.get("imatge", {}).get("value", ""),
                "lat": float(item.get("lat", {}).get("value")),
                "lon": float(item.get("lon", {}).get("value"))
            }
            
            if event["id_wikidata"] and event["lat"] and event["lon"]:
                dades_netes.append(event)
        except Exception:
            continue
        
    log(f"Transformación completada. {len(dades_netes)} registros listos para cargar.")
    return dades_netes

# 5. Load (Insertamos en PostGIS)
def carregar_a_postgis(dades_netes):
    log("Iniciant UPSERT massiu en blocs a PostGIS...")
    
    sql_upsert = """
        INSERT INTO ide_cultural.patrimoni_monumental 
        (id_wikidata, nom, imatge_url, lat, lon, geometry)
        VALUES 
        (%(id_wikidata)s, %(nom)s, %(imatge_url)s, %(lat)s, %(lon)s, ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326))
        ON CONFLICT (id_wikidata) 
        DO UPDATE SET 
            nom = EXCLUDED.nom,
            imatge_url = EXCLUDED.imatge_url,
            lat = EXCLUDED.lat,
            lon = EXCLUDED.lon,
            geometry = EXCLUDED.geometry;
    """
    
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        execute_batch(cursor, sql_upsert, dades_netes)
        conn.commit()
        log(f"🏆 ÈXIT: Taula 'patrimoni_monumental' actualitzada amb {len(dades_netes)} elements!")
    except psycopg2.Error as e:
        log(f"❌ Error guardant a PostgreSQL: {e}")
        if conn: conn.rollback()
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

if __name__ == "__main__":
    print("\n" + "═"*55)
    print(" 🏛️ PIPELINE ETL: PATRIMONI ESTÀTIC (WIKIDATA)")
    print("═"*55)
    
    preparar_base_de_dades()
    dades_api = extreure_dades_wikidata()
    dades_processades = transformar_dades(dades_api)
    carregar_a_postgis(dades_processades)
    
    print("═"*55 + "\n")
