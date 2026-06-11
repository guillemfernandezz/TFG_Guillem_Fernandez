import requests
import psycopg2
from psycopg2.extras import execute_batch
import sys
import time
from datetime import datetime
import concurrent.futures
import threading

# 1. Configuración del entorno
DB_CONFIG = {
    'dbname': 'events_db',
    'user' : 'postgres',
    'password': 'Tucans97',
    'host': 'localhost',
    'port': '5432'
}

WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"
HEADERS = {
    "User-Agent": "TFG-IDE-Cultural-Radar/1.0 (guillemfernandezz@gmail.com)",
    "Accept": "application/sparql-results+json"
}

def log(missatge):
    temps = datetime.now().strftime("%H:%M:%S")
    print(f"[{temps}] {missatge}")
    sys.stdout.flush()

# Preparamos base de datos (esquema y tabla)
def preparar_base_de_dades():
    log("Verificant l'estructura a PostGIS per al Patrimoni Estàtic...")
    sql_setup = """
        CREATE SCHEMA IF NOT EXISTS ide_cultural;

        CREATE TABLE IF NOT EXISTS ide_cultural.patrimoni_monumental (
            id_wikidata VARCHAR PRIMARY KEY,
            nom VARCHAR(512),
            descripcio TEXT,
            categoria VARCHAR(256),
            estil VARCHAR(256),
            proteccio VARCHAR(256),
            id_ipac VARCHAR(50),
            id_arqueo VARCHAR(50),
            url_oficial_gencat VARCHAR(1024),
            imatge_url VARCHAR(1024),
            google_maps_url VARCHAR(1024),
            wikipedia_url VARCHAR(1024),
            lat NUMERIC(10, 6),
            lon NUMERIC(10, 6),
            geometry geometry(Point, 4326)
        );
    """
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute(sql_setup)
        conn.commit()
        log("✅ Taula 'patrimoni_monumental' preparada.")
    except Exception as e:
        log(f"❌ Error preparant la DB: {e}")
        sys.exit(1)
    finally:
        if 'cursor' in locals() and cursor is not None: cursor.close()
        if 'conn' in locals() and conn is not None: conn.close()

# 3. Obtener los centros de los municipios para el radar y extraemos los monumentos cercanos con consultas SPARQL multihilo
def obtenir_centres_radar():
    log("Extreient la xarxa de coordenades per al radar (Sense noms per màxima velocitat)...")
    
    # Consulta super rapida para obtener únicamente la coordenada de cada municipi de Catalunya
    query = """
    SELECT DISTINCT ?coords WHERE {
        ?muni wdt:P31 wd:Q33146843.
        ?muni wdt:P131* wd:Q5705.
        ?muni wdt:P625 ?coords.
    }
    """
    try:
        res = requests.get(WIKIDATA_ENDPOINT, params={'query': query}, headers=HEADERS, timeout=60)
        res.raise_for_status()
        dades = res.json()['results']['bindings']
        
        centres = []
        for item in dades:
            coord_raw = item['coords']['value']
            coord_clean = coord_raw.replace("Point(", "").replace(")", "").strip()
            lon, lat = coord_clean.split(" ")
            centres.append({"lat": lat, "lon": lon})
            
        log(f"✅ Xarxa radar preparada: {len(centres)} nodes de llançament a Catalunya.")
        return centres
    except Exception as e:
        log(f"❌ Error obtenint els centres del radar: {e}")
        sys.exit(1)
# Extraemos los monumentos con los centros obtenidos
def processar_node(centre, index, total_centres, monuments_dict, dict_lock):
    """Funció que executarà cada fil (thread) de forma independent."""
    lat = centre['lat']
    lon = centre['lon']
    
    query = f"""
    SELECT DISTINCT 
        ?monument ?monumentLabel ?desc ?coords ?imatge ?catLabel 
        ?idIpac ?idArqueo ?proteccioLabel ?estilLabel ?wikipedia_link
    WHERE {{
        SERVICE wikibase:around {{
            ?monument wdt:P625 ?coords.
            bd:serviceParam wikibase:center "Point({lon} {lat})"^^geo:wktLiteral.
            bd:serviceParam wikibase:radius "16".
        }}
        {{
            {{ ?monument wdt:P1600 ?idIpac. }}        # IPAC (Inventari del Patrimoni Arquitectònic de Catalunya)
            UNION
            {{ ?monument wdt:P3861 ?idArqueo. }}       # Identificador arqueològic EGIPCI
            UNION
            {{ ?monument wdt:P3744 ?idBpca. }}         # BPCA (Bé del Patrimoni Cultural d'Aragó, cobertura fronterera)
            UNION
            {{ ?monument wdt:P6203 ?idIbpci. }}        # IBPCI (Inventari de Béns del Patrimoni Cultural Immaterial)
            UNION
            {{                                         # BCIN via P1435 = wd:Q23790
                ?monument wdt:P1435 wd:Q23790.
            }}
            UNION
            {{                                         # BCIL via P1435 = wd:Q15700834
                ?monument wdt:P1435 wd:Q15700834.
            }}
            UNION
            {{                                         # BIC (Bien de Interés Cultural estatal)
                ?monument wdt:P1435 wd:Q23776.
            }}
        }}

        ?monument wdt:P18 ?imatge;
                  wdt:P31 ?categoria.

        # Exclusió de categories residencials sense valor patrimonial expositiu
        FILTER NOT EXISTS {{
            ?monument wdt:P31 ?catExcluida.
            VALUES ?catExcluida {{
                wd:Q1649060    # masia
                wd:Q2652178    # mas (explotació agrícola)
                wd:Q56242238   # mas forestal
                wd:Q3558316    # masoveria
                wd:Q13393285   # habitatge rural
                wd:Q3947        # casa (residència genèrica)
                wd:Q19842071   # casa unifamiliar
            }}
        }}
                  
        OPTIONAL {{ ?monument wdt:P1435 ?proteccio. }}
        OPTIONAL {{ ?monument wdt:P149 ?estil. }}
        OPTIONAL {{
            ?wikipedia_link schema:about ?monument ;
                            schema:isPartOf <https://ca.wikipedia.org/> .
        }}
        
        SERVICE wikibase:label {{ 
            bd:serviceParam wikibase:language "ca,es,en". 
            ?monument rdfs:label ?monumentLabel.
            ?monument schema:description ?desc.
            ?categoria rdfs:label ?catLabel.
            ?proteccio rdfs:label ?proteccioLabel.
            ?estil rdfs:label ?estilLabel.
        }}
    }}
    """
    try:
        res = requests.get(WIKIDATA_ENDPOINT, params={'query': query}, headers=HEADERS, timeout=20)
        if res.status_code == 200:
            resultats = res.json()['results']['bindings']
            
            
            # Bloquegem el diccionari un microsegon per evitar que dos fils escriguin alhora
            with dict_lock:
                for item in resultats:
                    m_id = item.get("monument", {}).get("value", "").split("/")[-1]
                    monuments_dict[m_id] = item
                
                # Fem log només cada 50 nodes per no col·lapsar la terminal
                if (index + 1) % 50 == 0 or (index + 1) == total_centres:
                    log(f"   📡 [Fil Actiu] Processats {index + 1}/{total_centres} nodes. Joies: {len(monuments_dict)}")
        
        time.sleep(0.5) # Pausa obligatòria per no ser banejat per DDoS
    except Exception:
        pass # Si falla un, el radar adjacent ho cobrirà

def escombrada_radar(centres):
    log("Iniciant escombrada espacial MULTIHILO (màx 5 connexions simultànies)...")
    
    monuments_dict = {}
    total_centres = len(centres)
    dict_lock = threading.Lock() # Cadenat de seguretat per al diccionari compartit
    
    # Utilitzem ThreadPoolExecutor per llençar 5 peticions a la vegada
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futurs = []
        for i, centre in enumerate(centres):
            # Enviem la tasca a la piscina de treballadors
            futurs.append(executor.submit(processar_node, centre, i, total_centres, monuments_dict, dict_lock))
            
        # Esperem a que tots els treballadors acabin
        concurrent.futures.wait(futurs)

    dades_brutes = list(monuments_dict.values())
    log(f"🏁 Escombrada MULTIHILO completada. {len(dades_brutes)} monuments únics absoluts extrets.")
    return dades_brutes

# ==========================================
# 🔄 4. TRANSFORM
# ==========================================
def transformar_dades(dades_brutes):
    log("Transformant i netejant els registres...")
    dades_netes = []
    
    for item in dades_brutes:
        try:
            id_complet = item.get("monument", {}).get("value", "")
            id_net = id_complet.split("/")[-1] if id_complet else None
            
            coord_raw = item.get("coords", {}).get("value", "")
            if not coord_raw or "Point" not in coord_raw:
                continue
            
            coord_clean = coord_raw.replace("Point(", "").replace(")", "").strip()
            lon_str, lat_str = coord_clean.split(" ")
            lon = float(lon_str)
            lat = float(lat_str)
            
            ipac = item.get("idIpac", {}).get("value", None)
            arqueo = item.get("idArqueo", {}).get("value", None)
            url_gencat = None
            if ipac:
                url_gencat = f"https://invarquit.cultura.gencat.cat/card/{ipac}"
            elif arqueo:
                url_gencat = f"https://egipci.cultura.gencat.cat/ficha.jsf?id={arqueo}"
            
            monument = {
                "id_wikidata": id_net,
                "nom": item.get("monumentLabel", {}).get("value", "Monument sense nom"),
                "descripcio": (lambda d: d[0].upper() + d[1:] if d else "Sense descripció disponible")(item.get("desc", {}).get("value", "")),
                "categoria": item.get("catLabel", {}).get("value", "Monument"),
                "estil": item.get("estilLabel", {}).get("value", "Desconegut"),
                "proteccio": item.get("proteccioLabel", {}).get("value", "Inventariat"),
                "id_ipac": ipac,
                "id_arqueo": arqueo,
                "url_oficial_gencat": url_gencat,
                "imatge_url": item.get("imatge", {}).get("value", ""),
                
                # NOVES LÍNIES PER A L'UX DEL VISOR:
                "google_maps_url": f"https://www.google.com/maps/search/?api=1&query={lat},{lon}",
                "wikipedia_url": item.get("wikipedia_link", {}).get("value", None),
                
                "lat": lat,
                "lon": lon
            }
            
            if monument["id_wikidata"] and monument["lat"] and monument["lon"]:
                dades_netes.append(monument)
        except Exception:
            continue
            
    log(f"✅ Transformació completada: {len(dades_netes)} monuments estructurats.")
    return dades_netes

# ==========================================
# 💾 5. LOAD (UPSERT Massiu a PostGIS)
# ==========================================
def carregar_a_postgis(dades_netes):
    if not dades_netes:
        log("⚠️ No hi ha dades per carregar a PostGIS.")
        return

    log("Iniciant UPSERT massiu en blocs a PostGIS...")
    
    sql_upsert = """
        INSERT INTO ide_cultural.patrimoni_monumental 
        (id_wikidata, nom, descripcio, categoria, estil, proteccio, id_ipac, id_arqueo, url_oficial_gencat, imatge_url, google_maps_url, wikipedia_url, lat, lon, geometry)
        VALUES 
        (%(id_wikidata)s, %(nom)s, %(descripcio)s, %(categoria)s, %(estil)s, %(proteccio)s, %(id_ipac)s, %(id_arqueo)s, %(url_oficial_gencat)s, %(imatge_url)s, %(google_maps_url)s, %(wikipedia_url)s, %(lat)s, %(lon)s, 
        ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326))
        ON CONFLICT (id_wikidata) 
        DO UPDATE SET 
            nom = EXCLUDED.nom,
            descripcio = EXCLUDED.descripcio,
            categoria = EXCLUDED.categoria,
            estil = EXCLUDED.estil,
            proteccio = EXCLUDED.proteccio,
            id_ipac = EXCLUDED.id_ipac,
            id_arqueo = EXCLUDED.id_arqueo,
            url_oficial_gencat = EXCLUDED.url_oficial_gencat,
            imatge_url = EXCLUDED.imatge_url,
            google_maps_url = EXCLUDED.google_maps_url,
            wikipedia_url = EXCLUDED.wikipedia_url,
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
        log(f"🏆 ÈXIT FINAL: Base de dades PostGIS actualitzada amb {len(dades_netes)} punts!")
    except psycopg2.Error as e:
        log(f"❌ Error guardant a PostgreSQL: {e}")
        if conn: conn.rollback()
    finally:
        if 'cursor' in locals() and cursor is not None: cursor.close()
        if 'conn' in locals() and conn is not None: conn.close()

# ==========================================
# 🚀 ORQUESTADOR
# ==========================================
if __name__ == "__main__":
    print("\n" + "═"*55)
    print(" 🏛️ PIPELINE ETL: PATRIMONI ESTÀTIC")
    print("═"*55)
    
    preparar_base_de_dades()
    centres = obtenir_centres_radar()
    dades_api = escombrada_radar(centres)
    dades_processades = transformar_dades(dades_api)
    carregar_a_postgis(dades_processades)
    
    print("═"*55 + "\n")