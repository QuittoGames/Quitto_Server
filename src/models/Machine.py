from dataclasses import dataclass
import re
from typing import Optional
import socket

@dataclass
class Machine:
    address: str                   # "AA:BB:CC:DD:EE:FF"
    id: Optional[int] = None        #FK
    name: Optional[str] = None
    interface: Optional[str] = None   # eth0, wlan0
    vendor: Optional[str] = None      # Intel, Apple, Realtek
    is_randomized: bool = False    # MAC aleatório
    url_connect: Optional[str] 

    def is_valid(self) -> bool:
        return bool(
            re.fullmatch(r"([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", self.address)
        )

    def wake_on_lan(self) -> bool:
        try:
            mac = self.address.replace(":", "").replace("-", "")
            if len(mac) != 12:
                raise ValueError("MAC inválido")

            magic_packet = bytes.fromhex("FF" * 6 + mac * 16)

            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(magic_packet, ("255.255.255.255", 9))
            sock.close()
            return True
        except ValueError as ve:
            print(f"[ERRO] Valor inválido: {ve}")
            return False
        except Exception as e:
            print(f"[ERRO] Erro ao enviar pacote Wake-on-LAN: {e}")
            return False