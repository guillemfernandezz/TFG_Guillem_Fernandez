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

# API Agenda Cultural Generalitat
DATASET_ID = 'rhpv-yr4f'
API_URL = f"https://analisi.transparenciacatalunya.cat/resource/{DATASET_ID}.json"

def log(missatge):
    temps = datetime.now().strftime("%H:%M:%S")
    print(f"[{temps}] {missatge}")
    sys.stdout.flush()
    
# 2. Preparar la base de datos
    
def preparar_base_de_dades():
    """
    Creamos el esquema i la tabla en PostGIS si no existiera
    """
    log("Verificando/Creando la estructura en PostGIS ...")
    sql_setup = """
        CREATE SCHEMA IF NOT EXISTS ide_cultural;
        CREATE EXTENSION IF NOT EXISTS postgis; 

        CREATE TABLE IF NOT EXISTS ide_cultural.agenda_cultural (
            id_uuid VARCHAR PRIMARY KEY,
            nom VARCHAR(512),
            descripcio TEXT,
            data_inici TIMESTAMP,
            data_fi TIMESTAMP,
            horari TEXT,
            gratuita VARCHAR(50),
            espai VARCHAR(512),
            adrecca VARCHAR(512),
            municipi VARCHAR(256),
            categoria VARCHAR(256),
            imatge_url VARCHAR(1024),
            link_entrades VARCHAR(1024),
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
        log("Estructura de tablas preparada correctamente.")
    except Exception as e:
        log(f"Error al preparar la base de datos: {e}")
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()
        
# 3. Extracción de datos
def extreure_dades_api():
    log("Iniciando la extracción de la API de Agenda Cultural ...")
    avui = datetime.now().strftime("%Y-%m-%dT00:00:00.000")
    
    params = {
        "$where": f"data_fi >= '{avui}' AND latitud IS NOT NULL AND longitud IS NOT NULL",
        "$limit": 50000 
    }
    
    try:
        response = requests.get(API_URL, params=params, timeout=30)
        response.raise_for_status()
        dades = response.json()
        log(f"Extracción completada. {len(dades)} registros obtenidos.")
        return dades
    except requests.exceptions.RequestException as e:
        log(f"Error al extraer datos de la API: {e}")
        sys.exit(1)

# 4. Transformación de datos
def transformar_dades(dades_brutes):
    log("Transformando los datos ...")
    dades_netes = []
    
    # Modo debug para mostrar la estructura del primer registro
    print("\n[DEBUG] Radiografía del primer evento")
    if len(dades_brutes) > 0:
        keys = list(dades_brutes[0].keys())
        for key in keys:
            print(f"   - {key}")
    print(("="*50) + "\n")
    
    for item in dades_brutes:
        try:
            event = {
                "id_uuid": item.get("codi"),
                "nom": item.get("denominaci", "Esdeveniment sense nom"),
                "descripcio": item.get("descripcio", "Sense descripció"),
                "data_inici": item.get("data_inici"),
                "data_fi": item.get("data_fi"),
                "horari": item.get("horari", "Consultar horari oficial"),
                "gratuita": item.get("gratuita", "No especificat"),
                "espai": item.get("espai", "Espai públic"),
                "adrecca": item.get("adre_a", ""),
                "municipi": item.get("municipi", ""),
                "categoria": item.get("tags_categor_es", "Altres"),
                "imatge_url": item.get("imgapp", ""),
                "link_entrades": item.get("linkbotoentrades", ""),
                "lat": float(item.get("latitud")),
                "lon": float(item.get("longitud"))
            }
            
            # Segundo filtro por si de caso que no se cuele na'
            if event["id_uuid"] and event["lat"] and event["lon"]:
                dades_netes.append(event)
        except Exception:
            continue
    
    log(f"Transformación completada. {len(dades_netes)} registros válidos.")
    return dades_netes

# 5. Carga de datos
def purgar_events_caducats():
    """Elimina de PostGIS els esdeveniments amb data_fi anterior a avui."""
    log("Purgant esdeveniments caducats de PostGIS...")
    sql_purga = """
        DELETE FROM ide_cultural.agenda_cultural
        WHERE data_fi < NOW();
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute(sql_purga)
        eliminats = cursor.rowcount
        conn.commit()
        log(f"Purga completada: {eliminats} esdeveniments caducats eliminats.")
    except psycopg2.Error as e:
        log(f"Error durant la purga: {e}")
        if conn: conn.rollback()
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

def carregar_a_postgis(dades_netes):
    log("Inciando UPSERT en PostGIS ...")
    
    sql_upsert = """
        INSERT INTO ide_cultural.agenda_cultural 
        (id_uuid, nom, descripcio, data_inici, data_fi, horari, gratuita, espai, adrecca, municipi, categoria, imatge_url, link_entrades, lat, lon, geometry)
        VALUES 
        (%(id_uuid)s, %(nom)s, %(descripcio)s, %(data_inici)s, %(data_fi)s, %(horari)s, %(gratuita)s, %(espai)s, %(adrecca)s, %(municipi)s, %(categoria)s, %(imatge_url)s, %(link_entrades)s, %(lat)s, %(lon)s, 
        ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326))
        ON CONFLICT (id_uuid) 
        DO UPDATE SET 
            nom = EXCLUDED.nom,
            descripcio = EXCLUDED.descripcio,
            data_inici = EXCLUDED.data_inici,
            data_fi = EXCLUDED.data_fi,
            horari = EXCLUDED.horari,
            gratuita = EXCLUDED.gratuita,
            espai = EXCLUDED.espai,
            adrecca = EXCLUDED.adrecca,
            municipi = EXCLUDED.municipi,
            categoria = EXCLUDED.categoria,
            imatge_url = EXCLUDED.imatge_url,
            link_entrades = EXCLUDED.link_entrades,
            lat = EXCLUDED.lat,
            lon = EXCLUDED.lon,
            geometry = EXCLUDED.geometry;
    """
        
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        execute_batch(cursor, sql_upsert, dades_netes)
        conn.commit()
        log(f"UPSERT completado. {len(dades_netes)} registros procesados.")
        
    except psycopg2.Error as e:
        log(f"Error al cargar datos en PostGIS: {e}")
        if conn : conn.rollback()
    finally:
        if 'cursor' in locals():cursor.close()
        if 'conn' in locals(): conn.close()
        log("Conexión a PostGIS cerrada.")
        
if __name__ == "__main__":
    print("\n" + "="*50)
    print("INICIANDO EL PROCESO ETL DE AGENDA CULTURAL")
    print("="*50 )
    
    preparar_base_de_dades()
    purgar_events_caducats()
    dades_api = extreure_dades_api()
    dades_processades = transformar_dades(dades_api)
    carregar_a_postgis(dades_processades)
    
    print("\n" + "="*50)
    print("PROCESO ETL COMPLETADO CON ÉXITO")
    print("="*50 + "\n")