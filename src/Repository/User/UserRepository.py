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
logger = logging.getLogger("server.repository.User")


class UserRepository:
    """Repositório para operações CRUD com usuários no banco de dados"""
    
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

    def is_connected(self) -> bool:
        """Return True when DBConnection was initialized successfully."""
        return bool(getattr(self, "db", None))
    
    def get_all_users(self) -> Optional[List[User]]:
        """Retorna todos os usuários do banco"""
        try:
            if not self._ensure_db():
                return None
            rows = self.db.execute_query("SELECT id, name, password_hash, admin FROM users ORDER BY id")
            users = []
            for row in rows:
                users.append(User(
                    id=row.get('id'),
                    _name=row.get('name'),
                    _password_hash=row.get('password_hash'),
                    admin=row.get('admin', False)
                ))
            return users
        except Exception as e:
            logger.error(f"[ERROR] Erro ao buscar usuários: {e}")
            return None
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Busca um usuário pelo ID"""
        try:
            if not self._ensure_db():
                return None
            rows = self.db.execute_query("SELECT id, name, password_hash, admin FROM users WHERE id = %s", (user_id,))
            if not rows:
                return None
            row = rows[0]
            return User(
                id=row.get('id'),
                _name=row.get('name'),
                _password_hash=row.get('password_hash'),
                admin=row.get('admin', False)
            )
        except Exception as e:
            logger.error(f"[ERROR] Erro ao buscar usuário por ID: {e}")
            return None
    
    def get_user_by_name(self, name: str) -> Optional[User]:
        """Busca um usuário pelo nome"""
        try:
            if not self._ensure_db():
                return None
            rows = self.db.execute_query("SELECT id, name, password_hash, admin FROM users WHERE name = %s", (name,))
            if not rows:
                return None
            row = rows[0]
            return User(
                id=row.get('id'),
                _name=row.get('name'),
                _password_hash=row.get('password_hash'),
                admin=row.get('admin', False)
            )
        except Exception as e:
            logger.error(f"[ERROR] Erro ao buscar usuário por nome: {e}")
            return None
    
    def create_user(self, user: User) -> bool:
        """Cria um novo usuário no banco"""
        try:
            if not self._ensure_db():
                return False
            # use execute_query with fetch=False for write operations
            self.db.execute_query(
                "INSERT INTO users (name, password_hash, admin) VALUES (%s, %s, %s)",
                (user.get_name(), user.get_password_hash(), user.is_admin()),
                fetch=False
            )
            logger.info(f"[INFO] Usuário '{user.get_name()}' criado com sucesso")
            return True
        except Exception as e:
            logger.error(f"[ERROR] Erro ao criar usuário: {e}")
            return False
    
    def update_user(self, user: User) -> bool:
        """Atualiza um usuário existente"""
        try:
            if not self._ensure_db():
                return False
            self.db.execute_query(
                "UPDATE users SET name = %s, password_hash = %s, admin = %s WHERE id = %s",
                (user.get_name(), user.get_password_hash(), user.is_admin(), user.get_id()),
                fetch=False
            )
            logger.info(f"[INFO] Usuário ID {user.get_id()} atualizado com sucesso")
            return True
        except Exception as e:
            logger.error(f"[ERROR] Erro ao atualizar usuário: {e}")
            return False
    
    def delete_user(self, user_id: int) -> bool:
        """Deleta um usuário pelo ID"""
        try:
            if not self._ensure_db():
                return False
            self.db.execute_query("DELETE FROM users WHERE id = %s", (user_id,), fetch=False)
            logger.info(f"[INFO] Usuário ID {user_id} deletado com sucesso")
            return True
        except Exception as e:
            logger.error(f"[ERROR] Erro ao deletar usuário: {e}")
            return False
    