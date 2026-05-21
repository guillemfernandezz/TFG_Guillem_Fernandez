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