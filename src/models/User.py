from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from models.UnixUser import UnixUser
import bcrypt

@dataclass
class User:
    id: int #PK
    _name: str
    _password_hash: str = field(repr=False)
    
    admin: bool = False
    unix_user: Optional[UnixUser] = None
    
    machines: List[str] = field(default_factory=list)
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None

    def get_id(self) -> int:
        return self.id

    def get_name(self) -> str:
        return self._name

    def is_admin(self) -> bool:
        return self.admin

    def get_unix_user(self) -> Optional[UnixUser]:
        return self.unix_user

    def get_machines(self) -> List[str]:
        return self.machines

    def get_created_at(self) -> datetime:
        return self.created_at

    def get_last_login(self) -> Optional[datetime]:
        return self.last_login
    
    def set_name(self, new_name: str):
        if not new_name:
            raise ValueError("Nome não pode ser vazio")
        self._name = new_name

    def set_password_hash(self, new_hash: str):
        self._password_hash = new_hash

    def get_password_hash(self) -> str:
        return self._password_hash

    def set_admin(self, value: bool):
        self.admin = value

    def set_unix_user(self, unix_user: UnixUser):
        self.unix_user = unix_user

    def add_machine(self, machine: str):
        if machine not in self.machines:
            self.machines.append(machine)

    def remove_machine(self, machine: str):
        if machine in self.machines:
            self.machines.remove(machine)

    def update_last_login(self):
        self.last_login = datetime.utcnow()

    def verify_password(self, password_plain: str) -> bool:
        return bcrypt.checkpw(
            password_plain.encode("utf-8"),
            self._password_hash.encode("utf-8")
        )

    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")
