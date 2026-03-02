from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import os
import logging
from models.Machine import Machine

logger = logging.getLogger("server.models.globalpaths")


@dataclass
class GlobalPathEntry:
    path: Optional[Path] = None
    machine: Optional[Machine] = None
    machine_id: Optional[int] = None
    raw: Optional[Any] = None

    def kind(self) -> str:
        if self.machine is not None:
            return "machine"
        if self.machine_id is not None:
            return "machine_id"
        if self.path is not None:
            return "path"
        return "unknown"

    def to_dict(self) -> Dict[str, Any]:
        k = self.kind()
        if k == "machine":
            m = self.machine
            return {
                "type": "machine",
                "id": getattr(m, "id", None),
                "name": getattr(m, "name", None),
                "url_connect": getattr(m, "url_connect", None),
                "address": getattr(m, "address", None),
            }
        if k == "machine_id":
            return {"type": "machine_id", "id": self.machine_id}
        if k == "path":
            p = self.path
            return {"type": "path", "path": str(p), "exists": p.exists() if p else False, "readable": os.access(p, os.R_OK) if p and p.exists() else False}
        return {"type": "unknown", "repr": repr(self.raw)}


@dataclass
class GlobalPaths:
    entries: Dict[str, List[GlobalPathEntry]] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, mapping: Dict[str, Any]) -> "GlobalPaths":
        gp = cls()
        for key, items in (mapping or {}).items():
            if not isinstance(items, list):
                items = [items]
            lst: List[GlobalPathEntry] = []
            for e in items:
                try:
                    if isinstance(e, Machine):
                        lst.append(GlobalPathEntry(machine=e))
                    elif isinstance(e, int):
                        lst.append(GlobalPathEntry(machine_id=e))
                    elif isinstance(e, Path):
                        lst.append(GlobalPathEntry(path=e))
                    else:
                        # try string path
                        s = str(e)
                        p = Path(s)
                        if p.exists():
                            lst.append(GlobalPathEntry(path=p))
                        else:
                            lst.append(GlobalPathEntry(raw=e))
                except Exception:
                    lst.append(GlobalPathEntry(raw=e))
            gp.entries[key] = lst
        return gp

    def to_primitive(self) -> Dict[str, List[Dict[str, Any]]]:
        return {k: [entry.to_dict() for entry in lst] for k, lst in self.entries.items()}

    def to_simple_map(self) -> Dict[str, List[str]]:
        simple: Dict[str, List[str]] = {}
        for k, lst in self.entries.items():
            items: List[str] = []
            for entry in lst:
                if entry.machine is not None:
                    items.append(f"machine:{getattr(entry.machine,'name',None)}@{getattr(entry.machine,'url_connect',None)}")
                elif entry.machine_id is not None:
                    items.append(f"machine_id:{entry.machine_id}")
                elif entry.path is not None:
                    items.append(str(entry.path))
                else:
                    items.append(str(entry.raw))
            simple[k] = items
        return simple
