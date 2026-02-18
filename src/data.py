from dataclasses import dataclass, field
from typing import List, Optional, ClassVar, Dict, Any, Union
from pathlib import Path

from models.Machine import Machine
from Repository.Machines.MachineRepository import MachineRepository


# Core shared data container
@dataclass
class data:
    modules_local: List[str] = field(default_factory=list)
    Debug: bool = False

    MACHINES: ClassVar[List[Machine]] = []
    # Resolved view of BASES where machine IDs are replaced by Machine objects
    RESOLVED_BASES: ClassVar[Dict[str, List[Union[Path, Machine, None]]]] = {}

    # BASES may contain Path entries and/or machine references by DB id (int)
    # Example: "ai": [ Path(...), 1 ]  -> where 1 is machines.id in DB
    BASES = {
        "ai": [
            Path("/home/quitto/.ai"),
            # legacy inline Machine kept for backward compatibility; prefer using DB id ints
        ],
        "projects": [Path("/run/media/quitto/DATA/Projects")],
        "obsidian": [Path("/run/media/quitto/DATA/Obisidian_DB/Obisidian")],
    }

    @classmethod
    def load_machines(cls) -> None:
        """Load machines from repository into the in-memory list."""
        if not cls.MACHINES:
            repo = MachineRepository()
            # repo.get_all_machines() should return a list of Machine instances
            cls.MACHINES = repo.get_all_machines() or []
            # After loading machines, refresh resolved BASES
            try:
                cls.resolve_bases()
            except Exception:
                # Non-fatal: keep RESOLVED_BASES empty if resolution fails
                cls.RESOLVED_BASES = {}

    @classmethod
    def getMachineByName(cls, name: str) -> Optional[Machine]:
        for m in cls.MACHINES:
            if m and getattr(m, 'name', None) == name:
                return m
        return None

    @classmethod
    def resolve_bases(cls) -> Dict[str, List[Union[Path, Machine, None]]]:
        """Resolve entries in `BASES` converting integer IDs to Machine objects.

        Rules:
        - If an entry is an int, treat it as a machine DB id and replace with the
          corresponding `Machine` instance (or `None` if not found).
        - If an entry is already a `Machine`, keep it.
        - If an entry is a `Path`, keep it.
        - Any other types are coerced to `str` in the resolved view.
        """
        # Ensure machines are loaded
        cls.load_machines()

        id_map: Dict[int, Machine] = {m.id: m for m in cls.MACHINES if getattr(m, 'id', None) is not None}
        resolved: Dict[str, List[Union[Path, Machine, None]]] = {}

        for base_name, entries in cls.BASES.items():
            resolved[base_name] = []
            for entry in entries:
                if isinstance(entry, int):
                    resolved[base_name].append(id_map.get(entry))
                elif isinstance(entry, Path):
                    resolved[base_name].append(entry)
                elif isinstance(entry, Machine):
                    resolved[base_name].append(entry)
                else:
                    # unknown types: keep as-is (caller may stringify)
                    resolved[base_name].append(entry)

        cls.RESOLVED_BASES = resolved
        return resolved

    @classmethod
    def get_resolved_bases(cls) -> Dict[str, List[Union[Path, Machine, None]]]:
        if not cls.RESOLVED_BASES:
            return cls.resolve_bases()
        return cls.RESOLVED_BASES
