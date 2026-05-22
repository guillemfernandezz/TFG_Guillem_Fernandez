import requests
import psycopg2
from psycopg2.extras import execute_batch
import sys
import time
from datetime import datetime

# ==========================================
# ⚙️ 1. CONFIGURACIÓ DE L'ENTORN
# ==========================================
DB_CONFIG = {
    "dbname": "events_db",
    "user": "postgres",
    "password": "Tucans97", 
    "host": "localhost",
    "port": "5432"
}

WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"

def log(missatge):
    temps = datetime.now().strftime("%H:%M:%S")
    print(f"[{temps}] {missatge}")
    sys.stdout.flush()

# ==========================================
# 🏗️ 2. APROVISIONAMENT (DDL)
# ==========================================
def preparar_base_de_dades():
    """Crea la taula per al patrimoni monumental amb el model ric."""
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
            web_oficial VARCHAR(1024),
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

# ==========================================
# 📥 3. EXTRACT (SPARQL Optimitzat + Paginació)
# ==========================================
def extreure_dades_wikidata():
    log("Iniciant extracció optimitzada per blocs (inclou descripcions)...")
    
    mida_bloc = 2500  # 2500 monuments per bloc per evitar timeouts i sobrecàrrega
    blocs_totals = 12  # 12 blocs x 2500 = Capacitat per 30.000 registres
    tots_els_resultats = []
    
    headers = {
        "User-Agent": "TFG-IDE-Cultural (guillemfernandezz@gmail.com)",
        "Accept": "application/sparql-results+json"
    }
    
    for i in range(blocs_totals):
        offset = i * mida_bloc
        log(f"📥 Demanant bloc {i+1}/{blocs_totals} (Monuments del {offset} al {offset + mida_bloc})...")
        
        query = f"""
        SELECT DISTINCT 
            ?monument ?monumentLabel ?desc ?coords ?imatge ?catLabel 
            ?idIpac ?idArqueo ?proteccioLabel ?estilLabel
        WHERE {{
            ?monument wdt:P131* wd:Q5705.       
            
            {{ ?monument wdt:P1600 ?idIpac. }} UNION {{ ?monument wdt:P3861 ?idArqueo. }}
            
            ?monument wdt:P625 ?coords;
                      wdt:P18 ?imatge;
                      wdt:P31 ?categoria.
                      
            OPTIONAL {{ ?monument wdt:P1435 ?proteccio. }}
            OPTIONAL {{ ?monument wdt:P149 ?estil. }}
            
            SERVICE wikibase:label {{ 
                bd:serviceParam wikibase:language "ca,es,en". 
                ?monument rdfs:label ?monumentLabel.
                ?monument schema:description ?desc.
                ?categoria rdfs:label ?catLabel.
                ?proteccio rdfs:label ?proteccioLabel.
                ?estil rdfs:label ?estilLabel.
            }}
        }}
        ORDER BY ?monument
        LIMIT {mida_bloc}
        OFFSET {offset}
        """
        
        try:
            response = requests.get(WIKIDATA_ENDPOINT, params={'query': query}, headers=headers, timeout=120)
            response.raise_for_status()
            
            dades = response.json()
            bloc_resultats = dades['results']['bindings']
            
            if not bloc_resultats:
                log("ℹ️ No hi ha més registres disponibles a Wikidata. Finalitzant bucle.")
                break
                
            tots_els_resultats.extend(bloc_resultats)
            log(f"✅ Bloc {i+1} processat correctament ({len(bloc_resultats)} elements).")
            
            # Deixem respirar el servidor 2 segons
            time.sleep(2.0)  
            
        except Exception as e:
            log(f"⚠️ Error al bloc {i+1} (Offset {offset}): {e}.")
            log("Intentant continuar amb el següent bloc...")
            continue
            
    log(f"🏁 Extracció massiva completada: {len(tots_els_resultats)} monuments totals obtinguts.")
    return tots_els_resultats

# ==========================================
# 🔄 4. TRANSFORM
# ==========================================
def transformar_dades(dades_brutes):
    log("Transformant el graf de coneixement a format relacional...")
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
                "descripcio": item.get("desc", {}).get("value", "Sense descripció disponible"),
                "categoria": item.get("catLabel", {}).get("value", "Monument"),
                "estil": item.get("estilLabel", {}).get("value", "Desconegut"),
                "proteccio": item.get("proteccioLabel", {}).get("value", "Inventariat"),
                "id_ipac": ipac,
                "id_arqueo": arqueo,
                "url_oficial_gencat": url_gencat,
                "imatge_url": item.get("imatge", {}).get("value", ""),
                "web_oficial": None, # Forcem a None doncs ja no ho extraiem de SPARQL
                "wikipedia_url": None, # Forcem a None
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
        (id_wikidata, nom, descripcio, categoria, estil, proteccio, id_ipac, id_arqueo, url_oficial_gencat, imatge_url, web_oficial, wikipedia_url, lat, lon, geometry)
        VALUES 
        (%(id_wikidata)s, %(nom)s, %(descripcio)s, %(categoria)s, %(estil)s, %(proteccio)s, %(id_ipac)s, %(id_arqueo)s, %(url_oficial_gencat)s, %(imatge_url)s, %(web_oficial)s, %(wikipedia_url)s, %(lat)s, %(lon)s, 
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
        log(f"🏆 ÈXIT: Taula 'patrimoni_monumental' actualitzada amb {len(dades_netes)} punts!")
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
    print(" 🏛️ PIPELINE ETL: PATRIMONI ESTÀTIC (WIKIDATA V3)")
    print("═"*55)
    
    preparar_base_de_dades()
    dades_api = extreure_dades_wikidata()
    dades_processades = transformar_dades(dades_api)
    carregar_a_postgis(dades_processades)
    
    print("═"*55 + "\n")