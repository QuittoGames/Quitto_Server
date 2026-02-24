import sys
import os

# Adiciona o caminho para imports relativos
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from DB.DBConnection import DBConnection
from models.User import User
from models.UnixUser import UnixUser
from typing import Optional, List
import logging

# Logger specific to this repository: server.repository.user.userrepository
logger = logging.getLogger("server.repository.UnixUser")

class UnixUserRepository:
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


    def get_unix_user_with(self, uid: int) -> Optional[UnixUser]:
        try:
            if not self._ensure_db():
                return None

            rows = self.db.execute_query(
                """
                SELECT id, uid, username, gid
                FROM unix_users
                WHERE uid = %s
                """,
                (uid,)
            )

            if not rows:
                return None

            unix_user_id, uid, username, gid = rows[0]

            group_rows = self.db.execute_query(
                """
                SELECT ug.name
                FROM unix_groups ug
                JOIN unix_user_groups uug
                    ON uug.unix_group_id = ug.id
                WHERE uug.unix_user_id = %s
                """,
                (unix_user_id,)
            )

            groups = [row[0] for row in group_rows]

            return UnixUser(
                id=unix_user_id,
                uid=uid,
                username=username,
                gid=gid,
                groups=groups
            )

        except Exception as e:
            logger.error(f"[ERROR] Erro ao buscar UnixUser: {e}")
            return None