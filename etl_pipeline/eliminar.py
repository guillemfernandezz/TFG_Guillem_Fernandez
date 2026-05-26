import requests
import psycopg2
from psycopg2 import execute_batch
import time
import sys
from datetime import datetime
import concurrent.futures
import threading

# ⚙️ 1. CONFIGURACIÓ DE L'ENTORN