import requests
import json
import psycopg2
from psycopg2.extras import execute_batch
import sys
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
# 🏗️ 2. APROVISIONAMENT (DDL ENRIQUIT)
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
        log("✅ Taula 'patrimoni_monumental' preparada amb camps rics del pilot.")
    except Exception as e:
        log(f"❌ Error preparant la DB: {e}")
        sys.exit(1)
    finally:
        if 'cursor' in locals() and cursor is not None: cursor.close()
        if 'conn' in locals() and conn is not None: conn.close()

# ==========================================
# 📥 3. EXTRACT (Consulta SPARQL Ultra-Optimitzada)
# ==========================================
def extreure_dades_wikidata():
    log("Enviant consulta SPARQL optimitzada a Wikidata...")
    
    # Consulta optimitzada: Filtra per Catalunya a nivell de motor de grafs,
    # el que evita Timeouts i permet extreure milers de registres d'un sol cop.
    query = """
    SELECT DISTINCT 
        ?monument ?monumentLabel ?desc ?coords ?imatge ?catLabel 
        ?idIpac ?idArqueo ?proteccioLabel ?estilLabel ?web ?wikipedia_link
    WHERE {
        # Restringim immediatament l'espai de cerca a Catalunya per evitar que Wikidata es pengi
        ?monument wdt:P131* wd:Q5705.       
        
        # Filtre obligatori: Ha de tenir identificador patrimonial oficial català
        { ?monument wdt:P1600 ?idIpac. } UNION { ?monument wdt:P3861 ?idArqueo. }
        
        # Coordenades i imatge obligatòries
        ?monument p:P625 ?coordenada;
                  wdt:P18 ?imatge. 
        
        ?coordenada psv:P625 ?node_coord.
        ?node_coord wikibase:geoLatitude ?lat.
        ?node_coord wikibase:geoLongitude ?lon.
        
        # Metadades opcionals del pilot
        ?monument wdt:P31 ?categoria.
        OPTIONAL { ?monument wdt:P1435 ?proteccio. }
        OPTIONAL { ?monument wdt:P149 ?estil. }
        OPTIONAL { ?monument wdt:P856 ?web. }
        OPTIONAL {
            ?wikipedia_link schema:about ?monument ;
                            schema:isPartOf <https://ca.wikipedia.org/> .
        }
        
        # Traductor automàtic
        SERVICE wikibase:label { 
            bd:serviceParam wikibase:language "ca,es,en". 
            ?monument rdfs:label ?monumentLabel.
            ?monument schema:description ?desc.
            ?categoria rdfs:label ?catLabel.
            ?proteccio rdfs:label ?proteccioLabel.
            ?estil rdfs:label ?estilLabel.
        }
    }
    LIMIT 25000
    """
    
    headers = {
        "User-Agent": "TFG-IDE-Cultural (guillemfernandezz@gmail.com)",
        "Accept": "application/sparql-results+json"
    }
    
    try:
        response = requests.get(WIKIDATA_ENDPOINT, params={'query': query}, headers=headers, timeout=90)
        response.raise_for_status()
        
        # FIX DE SEGURETAT: Saltem els caràcters de control ocults que trencaven el JSON
        dades = json.loads(response.text, strict=False)
        resultats = dades['results']['bindings']
        log(f"✅ Extracció completada: {len(resultats)} monuments lliurats per Wikidata.")
        return resultats
    except Exception as e:
        log(f"❌ Error extreient dades de Wikidata: {e}")
        sys.exit(1)

# ==========================================
# 🔄 4. TRANSFORM + MODO DEBUGGING
# ==========================================
def transformar_dades(dades_brutes):
    if not dades_brutes:
        return []
        
    # 🔍 --- MODO DEBUGGING: RADIOGRAFIA DEL PRIMER REGISTRE ---
    print("\n" + "🔍" * 20)
    print("RADIOGRAFIA DEL PRIMER REGISTRE ENVIAT PER WIKIDATA:")
    print(json.dumps(dades_brutes[0], indent=2, ensure_ascii=False))
    print("🔍" * 20 + "\n")
    
    log("🚨 Atenció: Mode Debugging actiu. Aturant l'execució de seguretat per analitzar les claus.")
    log("Si veus l'estructura del JSON a dalt, el fix de caràcters i la connexió han funcionat!")
    sys.exit(0) # Forcem l'aturada de seguretat sol·licitada
    
# ==========================================
# 🚀 ORQUESTADOR
# ==========================================
if __name__ == "__main__":
    print("\n" + "═"*55)
    print(" 🏛️ PIPELINE ETL: PATRIMONI ESTÀTIC (WIKIDATA V2)")
    print("═"*55)
    
    preparar_base_de_dades()
    dades_api = extreure_dades_wikidata()
    transformar_dades(dades_api) # S'aturarà aquí per fer el debugging