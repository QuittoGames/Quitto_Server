from pathlib import Path
import os
from data import data
from typing import Optional
from datetime import datetime
import logging
from dataclasses import dataclass
import json
from Repository.User.UserRepository import UserRepository
from Repository.Machines.MachineRepository import MachineRepository
from models.Machine import Machine
import requests

logger = logging.getLogger("server.services.files.filestools")

@dataclass
class FilesTools:
	"""Collection of filesystem helper functions used by FileService.

	All methods are `@staticmethod` so they can be called without instantiating.
	"""
	EXTENSION_MAP = {
        "code": {".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".cs", ".go", ".rs", ".rb", ".php", ".lua", ".sh", ".ps1", ".sql", ".r", ".kt", ".swift", ".dart", ".zig", ".hs", ".ex", ".scala", ".groovy", ".coffee", ".v", ".cr", ".rkt", ".clj", ".elm", ".hx", ".fs", ".ml", ".pl"},
        "web":  {".html", ".css", ".jsx", ".tsx", ".vue", ".svelte", ".scss", ".sass", ".less"},
        "doc":  {".md", ".txt", ".rst", ".adoc", ".org", ".tex", ".pdf", ".doc", ".docx", ".odt"},
        "data": {".json", ".yaml", ".yml", ".toml", ".ini", ".xml", ".csv", ".tsv", ".env"},
        "img":  {".png", ".jpg", ".jpeg", ".gif", ".svg", ".bmp", ".webp", ".ico", ".tiff"},
        "audio":{".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a"},
        "video":{".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv"},
        "archive":{".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar"},
        "config":{".gitignore", ".dockerignore", ".editorconfig", "Dockerfile", "Makefile", ".lock"},
    }

	@staticmethod
	def get_file_category(ext: str) -> str:
		if not ext:
			return "other"
		ext = ext.lower()
		for cat, exts in FilesTools.EXTENSION_MAP.items():
			if ext in exts:
				return cat
		return "other"

	@staticmethod
	def format_size(size_bytes: int) -> str:
		if size_bytes < 1024:
			return f"{size_bytes} B"
		elif size_bytes < 1024**2:
			return f"{round(size_bytes/1024, 1)} KB"
		elif size_bytes < 1024**3:
			return f"{round(size_bytes/(1024**2), 2)} MB"
		else:
			return f"{round(size_bytes/(1024**3), 2)} GB"

	@staticmethod
	def read_file_with_path(path, machine: Optional[Machine] = None) -> dict:
		"""
		Read a file by absolute path. If `machine` is provided and has a
		`url_connect`, attempt to request the remote machine's MCP endpoint
		`/mcp/tools/read_file_with_path` with JSON payload `{'path': path}`.

		Falls back to reading the local filesystem if remote fetch fails or
		`machine` is not provided.
		"""
		# normalize path
		try:
			p = Path(path) if not isinstance(path, Path) else path
		except Exception:
			return {"error": "invalid path"}

		# Try remote fetch if machine provided
		if machine and getattr(machine, 'url_connect', None):
			try:
				base = str(machine.url_connect).rstrip('/')
				url = f"{base}/mcp/tools/read_file_with_path"
				resp = requests.post(url, json={"path": str(p)}, timeout=8)
				try:
					j = resp.json()
				except Exception:
					j = None
				if resp.ok and j and "content" in j:
					return j.get("content")
				if resp.ok and j:
					return j
				return {"error": f"remote returned status {resp.status_code}", "text": resp.text}
			except Exception as E:
				logger.debug("Remote fetch failed for %s: %s", getattr(machine, 'url_connect', None), E)

		# Local read fallback
		try:
			if not p.exists() or not p.is_file():
				return {"error": "file not found", "path": str(p)}
			with open(p, 'r', encoding='utf-8', errors='replace') as f:
				text = f.read()
			return {"path": str(p), "text": text, "size": p.stat().st_size}
		except Exception as E:
			logger.error(f"[ERROR] Failed to read file {p}: {E}")
			return {"error": str(E)}
	
	@staticmethod
	def resolve_base_root(entry):
		if entry is None:
			return None
		if isinstance(entry, list):
			for it in entry:
				if isinstance(it, Path):
					if it.exists():
						return it
				elif isinstance(it, str):
					p = Path(it)
					if p.exists():
						return p
			return None
		if isinstance(entry, Path):
			return entry if entry.exists() else None
		if isinstance(entry, str):
			p = Path(entry)
			return p if p.exists() else None
		return None

	@staticmethod
	def _read_file_path(file_path: Path) -> dict:
		return FilesTools.read_file_with_path(file_path)

	@staticmethod
	def _get_file_path_for(base: str, rel_path: str):
		# base is a registered key
		if base in data.GLOBAL_PATHS:
			entries = data.GLOBAL_PATHS.get(base) or []
			if not isinstance(entries, list):
				entries = [entries]

			chosen_root = None
			for e in entries:
				r = FilesTools.resolve_base_root(e)
				if r:
					chosen_root = r
					break

			if not chosen_root:
				return None, "base not found"

			candidate = chosen_root / rel_path
			if not candidate.exists():
				return None, "file not found"
			return candidate, None

		# base looks like a path - validate it's registered in data.GLOBAL_PATHS
		try:
			candidate_root = Path(base)
		except Exception:
			return None, "invalid base/path"

		found = False
		resolved_base_key = None
		for k, entries in data.GLOBAL_PATHS.items():
			if not isinstance(entries, list):
				entries = [entries]
			for e in entries:
				try:
					if isinstance(e, Path) and e.resolve() == candidate_root.resolve():
						found = True
						resolved_base_key = k
						break
					if isinstance(e, str) and Path(e).resolve() == candidate_root.resolve():
						found = True
						resolved_base_key = k
						break
				except Exception:
					continue
			if found:
				break

		if not found:
			return None, "path not registered in data.GLOBAL_PATHS"

		if not candidate_root.exists() or not candidate_root.is_dir():
			return None, "path not found or not a directory"

		candidate = candidate_root / rel_path
		if not candidate.exists():
			return None, "file not found"
		return candidate, None

	@staticmethod
	def normalize_rel_path(rel: str) -> str:
		if rel is None:
			return ""
		r = rel.strip()
		while r.startswith("/"):
			r = r[1:]
		parts = [p for p in r.split(os.path.sep) if p != ""]
		return os.path.sep.join(parts)

	@staticmethod
	def search_file_in_base(base: str, filename: str, limit: int = 1):
		if base not in data.GLOBAL_PATHS:
			return None

		entries = data.GLOBAL_PATHS.get(base) or []
		if not isinstance(entries, list):
			entries = [entries]

		for entry in entries:
			root = FilesTools.resolve_base_root(entry)
			if not root:
				continue

			# exact relative match
			candidate = root / filename
			try:
				if candidate.exists() and candidate.is_file():
					return candidate
			except Exception:
				pass

			# fallback: search by name anywhere under root
			try:
				for p in root.rglob("*"):
					if not p.is_file():
						continue
					if p.name == filename:
						return p
			except Exception:
				continue

		return None

	@staticmethod
	def read_file_from_base(base: str, path: str) -> dict:
		"""
		Reads a file from a given base directory and relative path, returning its contents as a dictionary.

		This method normalizes the provided relative path, attempts to resolve the full file path,
		and reads the file if found. If the file is not found directly, it searches for the file
		within the base directory. If the file still cannot be found, it returns a dictionary with an error message.

		Args:
			base (str): The base directory to search within.
			path (str): The relative path to the file.

		Returns:
			dict: The contents of the file as a dictionary, or a dictionary containing an error message if not found.
		"""
		rel = FilesTools.normalize_rel_path(path)

		candidate, err = FilesTools._get_file_path_for(base, rel)
		if err:
			if os.path.sep not in rel and "/" not in rel:
				found = FilesTools.search_file_in_base(base, rel)
				if found:
					return FilesTools._read_file_path(found)
			return {"error": err}

		return FilesTools._read_file_path(candidate)

	@staticmethod
	def get_home_path(id:int) -> Path:
		path_config_json = Path("/home/quitto/.config/quitto_server/homes.json")
		try:
			if not path_config_json.exists():
				return None
			
			content_data:dict = {}

			with open(path_config_json, "r", encoding="utf-8") as f:
				content_data = json.load(f)

			for i in content_data:
				if i["id_owner"] == id:
					return Path(i["path"])

			return None	
		except Exception as E:
			logger.error(f"[ERROR] Erro in get your path, Erro: {E}")

	@staticmethod
	def isGLOBAL_PATH(path_local:str) -> bool:
		"""Verify whether `path_local` belongs to a registered global base.

		This function understands the legacy forms stored in `data.GLOBAL_PATHS`:
		- Path or str entries (local filesystem roots)
		- `int` entries (machine PKs)
		- `Machine` instances

		Return values:
		- False: not a registered global path
		- dict with `type` == 'local' and `base_key` when matched to a local path
		- dict with `type` == 'machine', `machine_id` and `machine` when matched to a machine entry
		
		This richer return lets services decide whether to handle the path locally
		or forward the request to a remote machine.
		"""
		try:
			p = Path(path_local).resolve()
		except Exception:
			return False

		# build quick id->machine map from in-memory cache
		id_map = {m.id: m for m in getattr(data, 'MACHINES', []) if getattr(m, 'id', None) is not None}

		for key, entries in data.GLOBAL_PATHS.items():
			if not isinstance(entries, list):
				entries = [entries]
			for e in entries:
				try:
					# Machine id reference (integer)
					if isinstance(e, int):
						m = id_map.get(e)
						if m:
							return {"type": "machine", "machine_id": m.id, "machine": m, "base_key": key}
					# Machine object directly
					if isinstance(e, Machine):
						if getattr(e, 'id', None) is not None:
							return {"type": "machine", "machine_id": e.id, "machine": e, "base_key": key}
					# Local path entries
					if isinstance(e, Path):
						if e.resolve() == p:
							return {"type": "local", "base_key": key, "path": str(e)}
					elif isinstance(e, str):
						if Path(e).resolve() == p:
							return {"type": "local", "base_key": key, "path": e}
				except Exception:
					continue

		return False
		
	@staticmethod
	def get_machine_from_global_paths(path_or_id) -> Optional[Machine]:
		"""
		Given a path string, machine id (int) or a Machine instance, return the
		`Machine` object associated with that GLOBAL_PATHS entry when possible.

		- If `path_or_id` is an int, try to resolve it to a Machine by id.
		- If it's already a Machine, return it.
		- If it's a path (str), search `data.GLOBAL_PATHS` for an entry that
		  references a Machine (int or Machine) for the same resolved path and
		  return that Machine instance.
		
		Returns None when no machine association exists.
		"""
		# If caller already passed a Machine
		if isinstance(path_or_id, Machine):
			return path_or_id

		# If caller passed an integer id
		if isinstance(path_or_id, int):
			# try in-memory cache first
			for m in getattr(data, 'MACHINES', []) or []:
				if m and getattr(m, 'id', None) == path_or_id:
					return m
			# fallback to repository
			try:
				repo = MachineRepository()
				return repo.get_machine_by_id(path_or_id)
			except Exception:
				return None

		# Treat as path string
		try:
			p = Path(path_or_id).resolve()
		except Exception:
			return None

		# build quick id->machine map from in-memory cache
		id_map = {m.id: m for m in getattr(data, 'MACHINES', []) if getattr(m, 'id', None) is not None}

		for key, entries in data.GLOBAL_PATHS.items():
			if not isinstance(entries, list):
				entries = [entries]
			for e in entries:
				try:
					# If entry is machine id
					if isinstance(e, int):
						m = id_map.get(e)
						if m:
							# Check whether this base path matches the provided path
							# If MACHINE_BASES stores paths separately, caller probably passed the path
							return m
					# If entry is a Machine instance
					if isinstance(e, Machine):
						return e
					# If entry is a local path string or Path, compare with provided path
					if isinstance(e, Path) and e.resolve() == p:
						# No machine associated with this base entry
						return None
					if isinstance(e, str) and Path(e).resolve() == p:
						return None
				except Exception:
					continue

		return None


	@staticmethod
	def resolve_machine(machine_id: Optional[int] = None, mac: Optional[str] = None) -> Optional[Machine]:
		"""Resolve a Machine instance by id or MAC, preferring in-memory `data.MACHINES`.

		Returns None if not found.
		"""
		# Prefer in-memory machines loaded by data.load_machines()
		if machine_id is not None:
			for m in data.MACHINES:
				if m and getattr(m, 'id', None) == machine_id:
					return m

		if mac:
			norm = str(mac).lower().replace(':', '').replace('-', '')
			for m in data.MACHINES:
				if not m:
					continue
				for attr in ('mac', 'mac_address', 'macaddr'):
					a = getattr(m, attr, None)
					if a and str(a).lower().replace(':', '').replace('-', '') == norm:
						return m

		# Fallback to repository
		try:
			repo = MachineRepository()
			if machine_id is not None:
				try:
					m = repo.get_machine_by_id(machine_id)
					if m:
						return m
				except Exception:
					pass

			if mac:
				try:
					for m in repo.get_all_machines() or []:
						for attr in ('mac', 'mac_address', 'macaddr'):
							a = getattr(m, attr, None)
							if a and str(a).lower().replace(':', '').replace('-', '') == norm:
								return m
				except Exception:
					pass
		except Exception:
			pass

		return None