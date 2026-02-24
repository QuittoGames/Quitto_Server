import sys
import os

# Adiciona o caminho para imports relativos
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from DB.DBConnection import DBConnection
from typing import Optional,List
from pathlib import Path
from models.Machine import Machine
from data import data
import logging
import json
import ast

# Logger specific to this service: server.services.mcp.memoryservice
logger = logging.getLogger("server.services.mcp.memoryservice")

class MemoryService:
    def __init__(self):
        try:
            self.db = DBConnection()
            self.conn = None
        except Exception as e:
            logger.error(f"[ERROR] Erro ao conectar ao banco de dados: {e}")
            # Ensure attributes exist even if DB initialization failed
            self.db = None
            self.conn = None

    def _ensure_db(self) -> bool:
        """Return True if DB is initialized, otherwise log and return False."""
        if not getattr(self, "db", None):
            logger.error("[ERROR] Operação abortada: conexão com o banco de dados não inicializada")
            return False
        return True
    
    def save_in_mem(self, payload: str, agent_id: Optional[int] = None) -> bool:
        try:
            if not self._ensure_db():
                return False
                
            # If payload is bytes, decode
            if isinstance(payload, bytes):
                try:
                    payload = payload.decode("utf-8")
                except Exception:
                    payload = str(payload)

            # If it's a Python object (dict/list), dump to JSON
            if not isinstance(payload, str):
                try:
                    payload = json.dumps(payload, ensure_ascii=False)
                except Exception:
                    payload = str(payload)

            # If it's a string, ensure it's valid JSON; try json.loads, then ast.literal_eval fallback
            if isinstance(payload, str):
                try:
                    json.loads(payload)
                    # already valid JSON
                except Exception:
                    try:
                        parsed = ast.literal_eval(payload)
                        payload = json.dumps(parsed, ensure_ascii=False)
                    except Exception:
                        # fallback: wrap string as JSON string (adds double quotes)
                        payload = json.dumps(payload, ensure_ascii=False)

            # Ensure agent_id is always provided to satisfy NOT NULL constraint in DB
            agent_id_to_use = agent_id if agent_id is not None else 1
            query = """
                INSERT INTO agent_data (agent_id, data)
                VALUES (%s, %s)
            """
            params = (agent_id_to_use, payload)

            logger.debug("Inserting agent_data params: %s", params)

            # execute as non-fetching query so commit occurs
            affected = self.db.execute_query(query, params, fetch=False)
            return bool(affected and affected > 0)
        except Exception as E:
            logger.error(f"[ERROR] Erro ao inserir em agent_data: {E}")
            return False

    def get_promt(self, agent_id: int) -> Optional[str]:
        try:
            if not self._ensure_db():
                return None
            query = """
                SELECT prompt FROM agent WHERE id = %s
            """
            rows = self.db.execute_query(query, (agent_id,))
            if not rows:
                return None

            # rows is a list of RealDictCursor rows
            first = rows[0]
            return first.get("prompt")
        except Exception as E:
            logger.error(f"[ERROR] Erro ao buscar prompt do agente: {E}")
            return None

    def get_base_templete(self) -> Path:
        try:
            templete = data.GLOBAL_PATHS.get("ai")[0] / "templete.md"
            if not templete.exists():
                templete = data.GLOBAL_PATHS.get("obsidian")[0] / "IA" / "templete.md"

            return templete
        except PermissionError as E:
            logger.error(f"[ERROR] Permission denied while accessing the template file: {E}")
        except Exception as E:
            logger.error(f"[ERROR] Erro ao acessar o arquivo de template: {E}")