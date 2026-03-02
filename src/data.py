from dataclasses import dataclass, field
from typing import List, Optional, ClassVar, Dict, Any, Union
from pathlib import Path

from models.Machine import Machine
from Repository.Machines.MachineRepository import MachineRepository
from Services.AppsServices.AppService import AppService
import requests
import logging

logger = logging.getLogger("server.data")

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
    # Backwards-compatible container used across services to register global path bases
    GLOBAL_PATHS: ClassVar[Dict[str, Any]] = {}
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

        # Prefer MACHINE_BASES defined in MachineService if available.
        # The MACHINE_BASES may be defined as a module-level symbol or as a
        # class attribute on `MachineService`. Try both locations.
        try:
            import Services.MachineService.MachineService as ms_mod
            if hasattr(ms_mod, 'MACHINE_BASES'):
                SOURCE_BASES = getattr(ms_mod, 'MACHINE_BASES')
            elif hasattr(ms_mod, 'MachineService') and hasattr(ms_mod.MachineService, 'MACHINE_BASES'):
                SOURCE_BASES = ms_mod.MachineService.MACHINE_BASES
            else:
                SOURCE_BASES = cls.BASES or {}
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
        # Keep backward-compatible GLOBAL_PATHS reference (maps to original MACHINE_BASES)
        try:
            # SOURCE_BASES may contain Path/Machine entries; store the original mapping
            cls.GLOBAL_PATHS = SOURCE_BASES or {}
        except Exception:
            cls.GLOBAL_PATHS = {}
        return resolved

    @classmethod
    def get_resolved_bases(cls) -> Dict[str, List[Union[Path, Machine, None]]]:
        if not cls.RESOLVED_BASES:
            return cls.resolve_bases()
        return cls.RESOLVED_BASES

    @classmethod
    def load_global_paths(cls, timeout: int = 5) -> Dict[str, Any]:
        """Populate `GLOBAL_PATHS` by merging local MACHINE_BASES/BASES with
        bases reported by known machines (via their `/api/global_paths` endpoint).

        Rules:
        - Ensure machines are loaded first.
        - Start from the local source (MachineService.MACHINE_BASES or `cls.BASES`).
        - For each machine with `url_connect`, request `/api/global_paths` and
          for any base key reported by the machine, add the `Machine` instance
          to that base's entries (so remote bases are represented by the
          corresponding `Machine` object in `GLOBAL_PATHS`).
        - Return the merged mapping and set `cls.GLOBAL_PATHS`.
        """
        try:
            cls.load_machines()
        except Exception:
            logger.debug("load_machines failed while loading global paths", exc_info=True)

        # Start from existing SOURCE_BASES if available (like resolve_bases does)
        try:
            import Services.MachineService.MachineService as ms_mod
            if hasattr(ms_mod, 'MACHINE_BASES'):
                source = dict(getattr(ms_mod, 'MACHINE_BASES') or {})
            elif hasattr(ms_mod, 'MachineService') and hasattr(ms_mod.MachineService, 'MACHINE_BASES'):
                source = dict(ms_mod.MachineService.MACHINE_BASES or {})
            else:
                source = dict(cls.BASES or {})
        except Exception:
            source = dict(cls.BASES or {})

        merged = {}
        # Normalize source into lists
        for k, v in source.items():
            merged[k] = v if isinstance(v, list) else [v]

        # Query each known machine for its reported global_paths and merge
        for m in cls.MACHINES:
            try:
                url_connect = getattr(m, 'url_connect', None)
                if not url_connect:
                    continue
                resp = requests.get(str(url_connect).rstrip('/') + '/api/global_paths', timeout=timeout)
                if not resp.ok:
                    continue
                j = resp.json()
                if not isinstance(j, dict):
                    continue
                for key in j.keys():
                    # add machine object as an entry for this base
                    if key not in merged:
                        merged[key] = []
                    # avoid duplicates
                    if m not in merged[key]:
                        merged[key].append(m)
            except requests.RequestException as E:
                logger.debug("Failed to fetch global_paths from %s: %s", getattr(m, 'url_connect', None), E)
                continue
            except Exception as E:
                logger.exception("Unexpected error merging global_paths from machine %s", getattr(m, 'url_connect', None))

        # store and return
        try:
            cls.GLOBAL_PATHS = merged or {}
        except Exception:
            cls.GLOBAL_PATHS = {}

        return cls.GLOBAL_PATHS

    @classmethod
    def get_global_paths_for_api(cls, timeout: int = 5) -> List[Dict[str, Any]]:
        """Return a JSON-friendly list of global path entries suitable for API

        Each entry is a dict with keys:
        - `base`: the base/key name (e.g. 'MUSIC')
        - `path`: the literal path string (when available) or the base name
        - `machine`: dict with `id`, `name`, `url_connect` when the entry
          references a remote `Machine`. For local `Path` entries `machine`
          will be a small stub with `id=1` and `name='local'`.

        This method calls `load_global_paths()` (which already queries
        known machines) and then normalizes the mixed-type entries into
        plain dicts so API handlers can easily serialize the result.
        """
        merged = cls.load_global_paths(timeout=timeout) or {}
        out: List[Dict[str, Any]] = []

        for base_name, entries in merged.items():
            # ensure list
            if not isinstance(entries, list):
                entries = [entries]

            for entry in entries:
                item: Dict[str, Any] = {"base": base_name, "path": None, "machine": None}

                try:
                    if isinstance(entry, Machine):
                        item["machine"] = {"id": entry.id, "name": entry.name, "url_connect": entry.url_connect}
                        item["path"] = base_name
                    elif isinstance(entry, Path):
                        item["machine"] = {"id": 1, "name": "local", "url_connect": None}
                        item["path"] = str(entry)
                    elif isinstance(entry, int):
                        # lookup machine by id
                        m = next((mm for mm in cls.MACHINES if getattr(mm, 'id', None) == entry), None)
                        if m:
                            item["machine"] = {"id": m.id, "name": m.name, "url_connect": m.url_connect}
                        item["path"] = base_name
                    else:
                        # fallback: stringify unknown entries
                        item["path"] = str(entry)
                        item["machine"] = None
                except Exception:
                    item["path"] = str(entry)
                    item["machine"] = None

                out.append(item)

        return out
