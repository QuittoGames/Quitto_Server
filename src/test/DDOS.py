from fastapi.testclient import TestClient
import sys  
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from index import app

client = TestClient(app)

for i in range(120):  # passa do limite de 100/min
    r = client.get("/server")

print(r.status_code, r.json())

