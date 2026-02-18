from dataclasses import dataclass
import re
from typing import Optional


@dataclass
class Machine:
    address: str                   # "AA:BB:CC:DD:EE:FF"
    id: Optional[int] = None #FK
    name: Optional[str] = None
    interface: Optional[str] = None   # eth0, wlan0
    vendor: Optional[str] = None      # Intel, Apple, Realtek
    is_randomized: bool = False    # MAC aleatório

    def is_valid(self) -> bool:
        return bool(
            re.fullmatch(r"([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", self.address)
        )
