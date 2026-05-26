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
def obtenir_patrimoni(
    limit: int = 30000,
    minx: float = -180.0, miny: float = -90.0,
    maxx: float = 180.0,  maxy: float = 90.0,
):
    """
    Retorna els monuments històrics en format GeoJSON.
    Accepta bbox (minx/miny/maxx/maxy) per filtrar per àrea visible i un 'limit' màxim.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        query = """
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
            WHERE ST_Intersects(geometry, ST_MakeEnvelope(%s, %s, %s, %s, 4326))
              AND LOWER(COALESCE(categoria, '')) NOT IN ('masia', 'mas', 'mas forestal', 'masies')
            LIMIT %s;
        """
        cursor.execute(query, (minx, miny, maxx, maxy, limit))
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
def obtenir_agenda(
    limit: int = 1000,
    minx: float = -180.0, miny: float = -90.0,
    maxx: float = 180.0,  maxy: float = 90.0,
):
    """
    Retorna els esdeveniments culturals actius en format GeoJSON.
    Accepta bbox (minx/miny/maxx/maxy) per filtrar per àrea visible.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        query = """
            SELECT
                id_uuid AS id,
                nom AS denominacio,
                data_inici,
                data_fi,
                espai,
                municipi,
                link_entrades AS enllac,
                imatge_url AS imatge,
                descripcio,
                categoria,
                horari,
                gratuita,
                adrecca,
                ST_AsGeoJSON(geometry)::json AS geometry
            FROM ide_cultural.agenda_cultural
            WHERE ST_Intersects(geometry, ST_MakeEnvelope(%s, %s, %s, %s, 4326))
            LIMIT %s;
        """
        cursor.execute(query, (minx, miny, maxx, maxy, limit))
        resultats = cursor.fetchall()
        
        features = []
        for row in resultats:
            feature = {
                "type": "Feature",
                "geometry": row["geometry"],
                "properties": {
                    # Convertimos las marcas de tiempo de PostgreSQL a texto (ISO format)
                    k: (str(v) if k in ['data_inici', 'data_fi'] and v else v) 
                    for k, v in row.items() if k != 'geometry'
                }
            }
            features.append(feature)
            
        return {
            "type": "FeatureCollection",
            "features": features
        }
        
    except Exception as e:
        print(f"Error en la consulta /api/agenda: {e}")
        raise HTTPException(status_code=500, detail="Error recuperant l'agenda")
    finally:
        cursor.close()
        conn.close()
        
@app.get("/api/metadata")
def obtenir_metadades():
    """
    Retorna metadades del conjunt de dades seguint l'estructura NEM (Núcleo Español de Metadatos)
    basat en ISO 19115 / INSPIRE.
    """
    return {
        "fileIdentifier": "cat-ide-cultural-v1",
        "language": "cat",
        "characterSet": "utf8",
        "hierarchyLevel": "dataset",
        "contact": {
            "organisationName": "L'Atles Cultural — IDE de Catalunya",
            "role": "pointOfContact"
        },
        "dateStamp": datetime.now().isoformat(),
        "identificationInfo": {
            "citation": {
                "title": "IDE Cultural de Catalunya — Patrimoni i Agenda",
                "date": "2025-01-01",
                "edition": "1.0"
            },
            "abstract": (
                "Infraestructura de Dades Espacials que integra el patrimoni arquitectònic i monumental "
                "de Catalunya (via Wikidata) i l'agenda cultural dinàmica (via Generalitat de Catalunya). "
                "Les dades es serveixen en format GeoJSON filtrat per bounding box."
            ),
            "language": "cat",
            "topicCategory": "society",
            "extent": {
                "geographicBoundingBox": {
                    "westBoundLongitude": 0.159,
                    "eastBoundLongitude": 3.334,
                    "southBoundLatitude": 40.520,
                    "northBoundLatitude": 42.860,
                    "crs": "EPSG:4326"
                }
            },
            "spatialResolution": "1:50000",
            "maintenanceInfo": {
                "maintenanceAndUpdateFrequency": "daily"
            }
        },
        "distributionInfo": {
            "distributionFormat": "GeoJSON",
            "onlineResource": {
                "patrimoni": "/api/patrimonio",
                "agenda": "/api/agenda",
                "docs": "/docs"
            }
        },
        "dataQualityInfo": {
            "lineage": (
                "Patrimoni: extret de Wikidata (SPARQL) i enriquit amb dades de la Generalitat de Catalunya. "
                "Agenda: obtinguda de l'API oberta d'Agenda Cultural de la Generalitat. "
                "Geometries emmagatzemades a PostGIS en EPSG:4326."
            )
        },
        "metadataStandardName": "NEM — Núcleo Español de Metadatos (ISO 19115)",
        "metadataStandardVersion": "ISO 19115:2003"
    }