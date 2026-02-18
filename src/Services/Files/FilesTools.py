from pathlib import Path
import os
from data import data
from datetime import datetime
import logging
from dataclasses import dataclass

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
	def read_file_with_path(path) -> dict:
		try:
			p = Path(path) if not isinstance(path, Path) else path
		except Exception:
			return {"error": "invalid path"}

		try:
			if not p.exists():
				return {"error": "file not found"}
			if not p.is_file():
				return {"error": "path is not a file"}

			content = p.read_text(encoding="utf-8", errors="replace")
			return {
				"path": str(p),
				"size_bytes": p.stat().st_size,
				"content": content
			}
		except PermissionError:
			return {"error": "permission denied"}
		except Exception as e:
			return {"error": str(e)}

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
		if base in data.BASES:
			entries = data.BASES.get(base) or []
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

		# base looks like a path - validate it's registered in data.BASES
		try:
			candidate_root = Path(base)
		except Exception:
			return None, "invalid base/path"

		found = False
		resolved_base_key = None
		for k, entries in data.BASES.items():
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
			return None, "path not registered in data.BASES"

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
		if base not in data.BASES:
			return None

		entries = data.BASES.get(base) or []
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

    