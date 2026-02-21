import sys
import os

# Adiciona o caminho para imports relativos
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from DB.DBConnection import DBConnection
from typing import Optional,List
from models.Machine import Machine
import logging

# Logger specific to this repository: server.repository.machines.machinerepository
logger = logging.getLogger("server.repository.machines.machinerepository")


class MachineRepository:
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

    def get_machine_by_id(self,id:int) -> Optional[Machine]:
        try:
            if not self._ensure_db():
                return None
            rows = self.db.execute_query("SELECT * FROM machines WHERE id = %s", (id,))
            if not rows:
                return None
            row = rows[0]
            machine_local = Machine(
                id=row.get("id"),
                address=row.get("address"),
                name=row.get("name"),
                interface=row.get("interface"),
                vendor=row.get("vendor"),
                is_randomized=bool(row.get("is_randomized"))
            )
            return machine_local
        except Exception as E:
            logger.error(f"[ERROR] Erro em pegar machines by id , Erro: {E}")

    def get_machine_by_name(self,name:str) -> Optional[Machine]:
        try:
            if not self._ensure_db():
                return None
            rows = self.db.execute_query("SELECT * FROM machines WHERE name = %s", (name,))
            if not rows:
                return None
            row = rows[0]
            machine_local = Machine(
                id=row.get("id"),
                address=row.get("address"),
                name=row.get("name"),
                interface=row.get("interface"),
                vendor=row.get("vendor"),
                is_randomized=bool(row.get("is_randomized"))
            )
            return machine_local
        except Exception as E:
            logger.error(f"[ERROR] Erro em pegar machine by id , Erro: {E}")

    def get_all_machines(self) -> List[list]:
        """Retrieve all machines from the database."""
        try:
            if not self._ensure_db():
                return []
            rows = self.db.execute_query("SELECT * FROM machines ORDER BY id")
            machines = []
            for row in rows:
                machines.append(
                    Machine(
                        id=row.get("id"),
                        address=row.get("address"),
                        name=row.get("name"),
                        interface=row.get("interface"),
                        vendor=row.get("vendor"),
                        is_randomized=bool(row.get("is_randomized"))
                    )
                )
            return machines
        except Exception as e:
            logger.error(f"[ERROR] Failed to retrieve all machines: {e}")
            return []
    
    def create_machine(self, machine: Machine) -> bool:
        try:
            if not self._ensure_db():
                return False
            if hasattr(machine, 'is_valid') and not machine.is_valid():
                logger.error("[ERROR] Endereço MAC inválido ao criar máquina.")
                return False

            # Use table name 'machines'
            self.db.execute_query(
                """
                INSERT INTO machines (address, name, interface, vendor, is_randomized)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    machine.address,
                    machine.name,
                    machine.interface,
                    machine.vendor,
                    machine.is_randomized,
                ),
                fetch=False
            )
            logger.info(f"[INFO] Machine '{getattr(machine, 'name', '')}' criado com sucesso")
            return True
        except Exception as e:
            logger.error(f"[ERROR] Erro ao criar máquina: {e}")
            return False
        
    