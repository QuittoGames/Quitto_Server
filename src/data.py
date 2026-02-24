from dataclasses import dataclass, field
from typing import List, Optional, ClassVar, Dict, Any, Union
from pathlib import Path

from models.Machine import Machine
from Repository.Machines.MachineRepository import MachineRepository
from Services.AppsServices.AppService import AppService

# Core shared data container
@dataclass
class data:
    modules_local: List[str] = field(default_factory=list)
    Debug: bool = False

    MACHINES: ClassVar[List[Machine]] = []
    # Resolved view of BASES where machine IDs are replaced by Machine objects
    RESOLVED_BASES: ClassVar[Dict[str, List[Union[Path, Machine, None]]]] = {}

    APPS = ClassVar[List] 

    # BASES is delegated to Services/MachineService.MACHINE_BASES when present.
    # Keep an empty placeholder for compatibility; `resolve_bases` will prefer
    # the MACHINE_BASES defined in the MachineService module if available.
    BASES: ClassVar[Dict[str, Any]] = {}
    @classmethod
    def load_machines(cls) -> None:
        """Load machines into memory.

        This method delegates the actual load/resolution to
        `Services.MachineService.MachineService.load_machines` when available.
        Keeping this wrapper preserves the previous `data.load_machines()` API.
        """
        try:
            # Import inside function to avoid circular imports at module load time
            from Services.MachineService.MachineService import load_machines as ms_load
            ms_load()
            return
        except Exception:
            # Fallback to local loading if MachineService not present or import fails
            if not cls.MACHINES:
                repo = MachineRepository()
                cls.MACHINES = repo.get_all_machines() or []
            try:
                cls.resolve_bases()
            except Exception:
                cls.RESOLVED_BASES = {}

    @classmethod
    def getMachineByName(cls, name: str) -> Optional[Machine]:
        for m in cls.MACHINES:
            if m and getattr(m, 'name', None) == name:
                return m
        return None
    
    @classmethod
    def load_apps(cls) -> None:
        app_service = AppService()
        cls.APPS = app_service.load_apps()
        

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
        # Ensure machines are loaded (delegates to MachineService.load_machines)
        cls.load_machines()

        # Prefer MACHINE_BASES defined in MachineService if available
        try:
            from Services.MachineService.MachineService import MACHINE_BASES as SOURCE_BASES
        except Exception:
            SOURCE_BASES = cls.BASES or {}

        id_map: Dict[int, Machine] = {m.id: m for m in cls.MACHINES if getattr(m, 'id', None) is not None}
        resolved: Dict[str, List[Union[Path, Machine, None]]] = {}

        for base_name, entries in SOURCE_BASES.items():
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
