from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2.extras import RealDictCursor
import json
from datetime import datetime

app = FastAPI(
    title="API Visor Patrimoni i Cultura",
    description="API REST per servir dades espacials del patrimoni i l'agenda cultural de Catalunya.",
    version="1.0.0"
)

# Configuración de CORS (Permite que el front-end web se conecte a esta API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, aquí pondrías el dominio real de tu web
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# ⚙️ CONFIGURACIÓN BASE DE DATOS
# ==========================================
DB_CONFIG = {
    "dbname": "events_db",
    "user": "postgres",
    "password": "Tucans97", 
    "host": "localhost",
    "port": "5432"
}

def get_db_connection():
    try:
        # Usamos RealDictCursor para que PostGIS nos devuelva los datos como diccionarios (JSON ready)
        conn = psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        print(f"Error conectando a la base de datos: {e}")
        raise HTTPException(status_code=500, detail="Error intern del servidor de base de dades")

# ==========================================
# 🚀 ENDPOINTS (Rutas de la API)
# ==========================================

@app.get("/")
def arrel():
    return {"missatge": "Benvingut a l'API del Visor de Patrimoni. Afegeix /docs a la URL per veure la documentació."}

@app.get("/api/patrimonio")
def obtenir_patrimoni(limit: int = 1000):
    """
    Retorna els monuments històrics en format GeoJSON.
    Accepta un paràmetre 'limit' per no saturar el mapa si hi ha massa dades.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Consulta SQL combinant els camps de text amb la funció ST_AsGeoJSON per a la geometria
        query = f"""
            SELECT 
                id_wikidata, 
                nom, 
                descripcio, 
                categoria, 
                estil, 
                proteccio, 
                url_oficial_gencat, 
                imatge_url, 
                google_maps_url, 
                wikipedia_url,
                ST_AsGeoJSON(geometry)::json AS geometry
            FROM ide_cultural.patrimoni_monumental
            LIMIT {limit};
        """
        cursor.execute(query)
        resultats = cursor.fetchall()
        
        # Construïm l'estructura oficial GeoJSON requerida per Leaflet
        features = []
        for row in resultats:
            feature = {
                "type": "Feature",
                "geometry": row["geometry"],
                "properties": {k: v for k, v in row.items() if k != 'geometry'}
            }
            features.append(feature)
            
        return {
            "type": "FeatureCollection",
            "metadata": {
                "titol": "Patrimoni Arquitectònic i Monumental de Catalunya",
                "font": "Wikidata (Web Semàntica) & Generalitat de Catalunya",
                "data_generacio": datetime.now().isoformat(),
                "crs": {
                    "type": "name",
                    "properties": { "name": "urn:ogc:def:crs:EPSG::4326" }
                },
                "total_elements_retornats": len(features),
                "llicencia": "CC0 1.0 Universal"
            },
            "features": features
        }
        
    except Exception as e:
        print(f"Error en la consulta /api/patrimonio: {e}")
        raise HTTPException(status_code=500, detail="Error recuperant el patrimoni")
    finally:
        cursor.close()
        conn.close()

@app.get("/api/agenda")
def obtenir_agenda(limit: int = 500):
    """
    Retorna els esdeveniments culturals actius en format GeoJSON.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        query = f"""
            SELECT 
                id,
                denominacio,
                data_inici,
                data_fi,
                espai,
                municipi,
                comarca,
                enllac,
                imatge,
                descripcio,
                tags_cerca,
                ST_AsGeoJSON(geometry)::json AS geometry
            FROM ide_cultural.agenda_dinamica
            LIMIT {limit};
        """
        cursor.execute(query)
        resultats = cursor.fetchall()
        
        features = []
        for row in resultats:
            feature = {
                "type": "Feature",
                "geometry": row["geometry"],
                "properties": {
                    k: (str(v) if k in ['data_inici', 'data_fi'] and v else v) # Convertim les dates a text (ISO format)
                    for k, v in row.items() if k != 'geometry'
                }
            }
            features.append(feature)
            
        return {
            "type": "FeatureCollection",
            "metadata": {
                "titol": "Agenda Cultural Dinàmica de Catalunya",
                "font": "Generalitat de Catalunya - Departament de Cultura",
                "data_generacio": datetime.now().isoformat(),
                "crs": {
                    "type": "name",
                    "properties": { "name": "urn:ogc:def:crs:EPSG::4326" }
                },
                "total_elements_retornats": len(features),
                "llicencia": "CC0 1.0 Universal"
            },
            "features": features
        }
        
    except Exception as e:
        print(f"Error en la consulta /api/agenda: {e}")
        raise HTTPException(status_code=500, detail="Error recuperant l'agenda")
    finally:
        cursor.close()
        conn.close()
        
    # Para arrancar el servidor, usar: uvicorn backend_api.main:app --reload en la carpeta raíz del proyecto.