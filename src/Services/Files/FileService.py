from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Request
from fastapi.responses import FileResponse
from pathlib import Path
from models.Machine import Machine
from data import data
from .FilesTools import FilesTools
import os
import shutil
import psutil
import mimetypes
from datetime import datetime
from typing import Optional
from Repository.Machines.MachineRepository import MachineRepository
from fastapi.responses import RedirectResponse
import logging

# Logger specific to this service: server.services.files.fileservice
logger = logging.getLogger("server.services.files.fileservice")

import requests

routerFile = APIRouter(prefix="/files", tags=["Files"])

# ═══════════════════════════════════════════════════════════════
# FileService - Serviço de Arquivos
# ═══════════════════════════════════════════════════════════════

# ── Helpers ──────────────────────────────────────────────────

EXTENSION_MAP = getattr(FilesTools, "EXTENSION_MAP", None)

def get_file_category(ext: str) -> str:
    return FilesTools.get_file_category(ext)

def format_size(size_bytes: int) -> str:
    return FilesTools.format_size(size_bytes)

def read_file_with_path(path) -> dict:
    return FilesTools.read_file_with_path(path)

def resolve_base_root(entry):
    return FilesTools.resolve_base_root(entry)

def _read_file_path(file_path: Path,machine_id) -> dict:
    try:
        # Resolve machine by id via in-memory cache first (data.MACHINES),
        # then fall back to repository lookup.
        machine = None
        if machine_id is not None:
            # Check loaded machines first
            for m in data.MACHINES:
                if m and getattr(m, 'id', None) == machine_id:
                    machine = m
                    break
            if machine is None:
                repo = MachineRepository()
                try:
                    machine = repo.get_machine_by_id(machine_id)
                except Exception:
                    machine = None
        return FilesTools._read_file_path(file_path, machine)
    except Exception as E:
        logger.error("[ERROR] Error in get machine, Errro: %s",E)

def _get_file_path_for(base: str, rel_path: str):
    return FilesTools._get_file_path_for(base, rel_path)

def normalize_rel_path(rel: str) -> str:
    return FilesTools.normalize_rel_path(rel)

def search_file_in_base(base: str, filename: str, limit: int = 1):
    return FilesTools.search_file_in_base(base, filename, limit)

def read_file_from_base(base: str, path: str) -> dict:
    return FilesTools.read_file_from_base(base, path)

class FileService:
    """Service para operações com arquivos nas bases"""
    
    @routerFile.get("/list/{base}")
    def list_files(base: str):
        """Lista arquivos .md de uma base"""
        entry = data.GLOBAL_PATHS.get(base)
        root = resolve_base_root(entry)
        if not root:
            # Try forwarding to machines if the base isn't local
            forwarded = FilesTools.forward_to_machines(f"/files/list/{base}")
            if forwarded is not None:
                return forwarded
            return {"error": "base not found", "available": list(data.GLOBAL_PATHS.keys())}

        files = [str(p.relative_to(root)) for p in root.rglob("*.md")]
        return {"base": base, "count": len(files), "files": files}
    

    @routerFile.get("/read/{base}")
    def read_file(base: str, path: str):
        """Lê conteúdo de um arquivo"""
        candidate, err = _get_file_path_for(base, path)
        if err:
            # If local resolution failed, try forwarding to machines
            forwarded = FilesTools.forward_to_machines(f"/files/read/{base}", params={"path": path})
            if forwarded is not None:
                return forwarded
            return {"error": err}
        return _read_file_path(candidate)

    @routerFile.get("/find")
    def find_in_base(base: str = Query(..., description="Base name from data.GLOBAL_PATHS or an absolute path"), filename: str = Query(..., description="Filename or relative path to find"), limit: int = Query(50, description="Max matches to return"), machine_id: Optional[int] = None, mac: Optional[str] = None):
        """Busca um arquivo dentro de uma base (chave em data.GLOBAL_PATHS) ou em um caminho absoluto.

        - Se `base` for uma chave existente em `data.GLOBAL_PATHS`, procura em todas as entradas resolvidas dessa base.
        - Se `base` for um caminho, valida que ele esteja presente em `data.GLOBAL_PATHS` (mesma entrada) antes de pesquisar.
        """
        matches = []

        # Helper to add match info
        def add_match(p: Path, used_base: str):
            try:
                stat = p.stat()
                matches.append({
                    "path": str(p),
                    "base": used_base,
                    "size_bytes": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
            except Exception:
                return

        # Remote forwarding if machine specified
        if machine_id or mac:
            try:
                machine = FilesTools.resolve_machine(machine_id=machine_id, mac=mac)
                if machine and getattr(machine, 'url_connect', None):
                    params = { 'base': base, 'filename': filename, 'limit': limit }
                    try:
                        r = requests.get(machine.url_connect.rstrip('/') + '/files/find', params=params, timeout=8)
                        if r.ok:
                            return r.json()
                        return {"error": f"remote HTTP {r.status_code}", "details": r.text[:512]}
                    except requests.RequestException as e:
                        logger.error("Error forwarding find to remote machine: %s", e)
                        return {"error": "remote request failed", "details": str(e)}
            except Exception as E:
                logger.error('Error resolving machine for find_in_base: %s', E)

        # Case 1: base is a registered key in data.GLOBAL_PATHS
        if base in data.GLOBAL_PATHS:
            entries = data.GLOBAL_PATHS.get(base) or []
            # normalize to list
            if not isinstance(entries, list):
                entries = [entries]

            for entry in entries:
                root = resolve_base_root(entry)
                if not root:
                    continue

                # If filename looks like a relative path, check directly
                if os.path.sep in filename or "/" in filename:
                    candidate = root / filename
                    if candidate.exists() and candidate.is_file():
                        add_match(candidate, base)
                else:
                    # search by name
                    for p in root.rglob("*"):
                        if not p.is_file():
                            continue
                        if p.name == filename:
                            add_match(p, base)
                            if len(matches) >= limit:
                                return {"query": {"base": base, "filename": filename}, "count": len(matches), "matches": matches}

            return {"query": {"base": base, "filename": filename}, "count": len(matches), "matches": matches}

        # Case 2: base looks like a path — validate it's listed in data.GLOBAL_PATHS
        try:
            candidate_path = Path(base)
        except Exception:
            return {"error": "invalid base/path"}

        # Verify candidate_path is present in any data.GLOBAL_PATHS entry (exact match)
        found_in_bases = False
        for k, entries in data.GLOBAL_PATHS.items():
            if not isinstance(entries, list):
                entries = [entries]
            for e in entries:
                try:
                    if isinstance(e, Path) and e.resolve() == candidate_path.resolve():
                        found_in_bases = True
                        resolved_base_key = k
                        break
                    if isinstance(e, str) and Path(e).resolve() == candidate_path.resolve():
                        found_in_bases = True
                        resolved_base_key = k
                        break
                except Exception:
                    continue
            if found_in_bases:
                break

        if not found_in_bases:
            return {"error": "path not registered in data.GLOBAL_PATHS"}

        # search inside candidate_path
        root = candidate_path
        if not root.exists() or not root.is_dir():
            return {"error": "path not found or not a directory"}

        if os.path.sep in filename or "/" in filename:
            cand = root / filename
            if cand.exists() and cand.is_file():
                add_match(cand, resolved_base_key)
        else:
            for p in root.rglob("*"):
                if not p.is_file():
                    continue
                if p.name == filename:
                    add_match(p, resolved_base_key)
                    if len(matches) >= limit:
                        break

        return {"query": {"base": base, "filename": filename, "resolved_base": resolved_base_key}, "count": len(matches), "matches": matches}
    
    @routerFile.post("/get_home_user")
    def get_home_user(request: Request, id: Optional[int] = None):
        """Retorna o caminho home do usuário.

        - Se `id` for fornecido no corpo/query, usa-o.
        - Caso contrário, tenta obter `user_id` da sessão (`request.session`).
        """
        try:
            user_id = id or request.session.get("user_id")
            if not user_id:
                raise HTTPException(status_code=401, detail="User id not provided or not authenticated")

            path = FilesTools.get_home_path(user_id)
            if not path:
                raise HTTPException(status_code=400, detail="Invalid user path")

            return {"path": str(path)}
        except HTTPException:
            raise
        except Exception as E:
            logger.error(f"[ERROR] Erro in get Path of user, Erro: {E}")
            raise HTTPException(status_code=500, detail="Internal server error")


    @routerFile.get("/search/{base}")
    def search_files(
        base: str,
        query: str = "",
        ext: Optional[str] = Query(None, description="Filtrar por extensão (.py, .md, etc)"),
        category: Optional[str] = Query(None, description="Filtrar por categoria (code, doc, img, etc)"),
        min_size: Optional[int] = Query(None, description="Tamanho mínimo em bytes"),
        max_size: Optional[int] = Query(None, description="Tamanho máximo em bytes"),
        sort: str = Query("name", description="Ordenar por: name, size, date"),
        limit: int = Query(50, description="Limite de resultados"),
        content: Optional[str] = Query(None, description="Buscar dentro do conteúdo dos arquivos"),
        machine_id: Optional[int] = None, mac: Optional[str] = None
    ):
        """Busca avançada de arquivos na base"""
        # Remote forwarding if machine specified
        if machine_id or mac:
            try:
                machine = FilesTools.resolve_machine(machine_id=machine_id, mac=mac)
                if machine and getattr(machine, 'url_connect', None):
                    params = {
                        'query': query,
                        'ext': ext,
                        'category': category,
                        'min_size': min_size,
                        'max_size': max_size,
                        'sort': sort,
                        'limit': limit
                    }
                    if content:
                        params['content'] = content
                    try:
                        r = requests.get(machine.url_connect.rstrip('/') + f'/files/search/{base}', params=params, timeout=8)
                        if r.ok:
                            return r.json()
                        return {"error": f"remote HTTP {r.status_code}", "details": r.text[:512]}
                    except requests.RequestException as e:
                        logger.error("Error forwarding search to remote machine: %s", e)
                        return {"error": "remote request failed", "details": str(e)}
            except Exception as E:
                logger.error('Error resolving machine for search_files: %s', E)

        entry = data.GLOBAL_PATHS.get(base)
        
        root = resolve_base_root(entry)
        if not root or not root.exists():
            return {"error": "base not found"}
        
        if not query and not ext and not category and not content:
            return {"error": "query, ext, category ou content é obrigatório"}
        
        results = []
        
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            
            # Filtro por nome
            if query and query.lower() not in p.name.lower():
                continue
            
            # Filtro por extensão
            if ext and p.suffix.lower() != ext.lower():
                continue
            
            # Filtro por categoria
            file_cat = get_file_category(p.suffix)
            if category and file_cat != category.lower():
                continue
            
            try:
                stat = p.stat()
            except (PermissionError, OSError):
                continue
            
            # Filtro por tamanho
            if min_size and stat.st_size < min_size:
                continue
            if max_size and stat.st_size > max_size:
                continue
            
            # Busca por conteúdo (apenas em arquivos texto < 1MB)
            if content:
                if stat.st_size > 1024 * 1024:
                    continue
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                    if content.lower() not in text.lower():
                        continue
                except:
                    continue
            
            results.append({
                "name": p.name,
                "path": str(p.relative_to(root)),
                "ext": p.suffix,
                "category": file_cat,
                "size_bytes": stat.st_size,
                "size_human": format_size(stat.st_size),
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "modified_ts": stat.st_mtime
            })
            
            if len(results) >= limit * 2:
                break
        
        # Ordenação
        if sort == "size":
            results.sort(key=lambda x: x["size_bytes"], reverse=True)
        elif sort == "date":
            results.sort(key=lambda x: x["modified_ts"], reverse=True)
        else:
            results.sort(key=lambda x: x["name"].lower())
        
        results = results[:limit]
        
        return {
            "base": base,
            "query": query,
            "filters": {"ext": ext, "category": category, "min_size": min_size, "max_size": max_size},
            "sort": sort,
            "count": len(results),
            "matches": results
        }
    
    @routerFile.get("/tree/{base}")
    def read_file_with_path(path) -> dict:
        """Read a file given a filesystem path (str or Path) and return a standardized dict.

        Returns dict with keys: `path`, `size_bytes`, `content` or `error` on failure.
        """
        # Delegate to FilesTools implementation
        return FilesTools.read_file_with_path(path)


    # `resolve_base_root` and `_read_file_path` are provided by FilesTools and
    # module-level wrappers; remove duplicate implementations to keep a single
    # authoritative implementation in `FilesTools`.
    

    @routerFile.post("/add")
    async def add_file(path: str, file: UploadFile = File(...)):
        """Upload de arquivo para um caminho absoluto"""
        if file is None:
            raise HTTPException(status_code=404, detail="File object is required")
        
        try:
            dest = Path(path)
            if not os.path.exists(dest):
                dest.parent.mkdir(parents=True, exist_ok=True)

            content = await file.read()

            with dest.open("wb") as buffer:
                buffer.write(content)

            return {
                "filename": file.filename,
                "content_type": file.content_type,
                "path": str(dest),
                "size": len(content),
                "size_human": format_size(len(content))
            }
        except PermissionError:
            raise HTTPException(status_code=403, detail="Permissão negada para escrever no caminho especificado")
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"Erro ao salvar arquivo: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erro inesperado: {str(e)}")

    @routerFile.post("/upload/{base}")
    async def upload_to_base(base: str, file: UploadFile = File(...), path: str = Query("", description="Subpasta destino dentro da base")):
        """Upload de arquivo para uma base específica"""
        entry = data.GLOBAL_PATHS.get(base)
        root = resolve_base_root(entry)
        if not root or not root.exists():
            raise HTTPException(status_code=404, detail="base not found")
        
        dest = root / path / file.filename if path else root / file.filename
        
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            content = await file.read()
            
            with dest.open("wb") as buffer:
                buffer.write(content)
            
            return {
                "status": "ok",
                "filename": file.filename,
                "content_type": file.content_type,
                "path": str(dest.relative_to(root)),
                "full_path": str(dest),
                "size": len(content),
                "size_human": format_size(len(content))
            }
        except PermissionError:
            raise HTTPException(status_code=403, detail="Permissão negada")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")
    
    @routerFile.get("/filesystem")
    def filesystem_info(request: Request):
        """Informações completas do filesystem"""
        if not request.session.get("authenticated"):
            raise PermissionError
        try:
            partitions = []
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    partitions.append({
                        "device": partition.device,
                        "mountpoint": partition.mountpoint,
                        "fstype": partition.fstype,
                        "total_gb": round(usage.total / (1024**3), 2),
                        "used_gb": round(usage.used / (1024**3), 2),
                        "free_gb": round(usage.free / (1024**3), 2),
                        "percent_used": usage.percent,
                        "total_human": format_size(usage.total),
                        "used_human": format_size(usage.used),
                        "free_human": format_size(usage.free)
                    })
                except PermissionError:
                    raise HTTPException(status_code=401,detail="[ERROR] Unauthorized")


            disk_io = psutil.disk_io_counters()
            mem = psutil.virtual_memory()
            
            return {
                "partitions": partitions,
                "total_partitions": len(partitions),
                "memory": {
                    "total_gb": round(mem.total / (1024**3), 2),
                    "used_gb": round(mem.used / (1024**3), 2),
                    "free_gb": round(mem.available / (1024**3), 2),
                    "percent_used": mem.percent
                },
                "disk_io": {
                    "read_count": disk_io.read_count if disk_io else 0,
                    "write_count": disk_io.write_count if disk_io else 0,
                    "read_mb": round((disk_io.read_bytes / (1024**2)) if disk_io else 0, 2),
                    "write_mb": round((disk_io.write_bytes / (1024**2)) if disk_io else 0, 2)
                }
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erro ao obter informações do filesystem: {str(e)}")
    
    @routerFile.get("/browse/{base}")
    def browse_directory(base: str, path: str = "", machine_id: Optional[int] = None, mac: Optional[str] = None):
        """Navega por diretórios de uma base com detalhes completos.

        Se `machine_id` ou `mac` for fornecido, tenta encaminhar a requisição
        para a `Machine` remota usando `machine.url_connect`. Caso contrário,
        executa a navegação localmente.
        """
        logger.debug("browse_directory called: base=%s path=%s machine_id=%s mac=%s", base, path, machine_id, mac)
        # Remote forwarding if machine specified
        if machine_id or mac:
            try:
                machine = FilesTools.resolve_machine(machine_id=machine_id, mac=mac)
                if machine and getattr(machine, 'url_connect', None):
                    url = machine.url_connect.rstrip('/') + f"/files/browse/{base}?path={requests.utils.requote_uri(path)}"
                    try:
                        r = requests.get(url, timeout=8)
                        if r.ok:
                            return r.json()
                        return {"error": f"remote HTTP {r.status_code}", "details": r.text[:512]}
                    except requests.RequestException as e:
                        logger.error("Error forwarding browse to remote machine: %s", e)
                        return {"error": "remote request failed", "details": str(e)}
            except Exception as E:
                logger.error('Error resolving machine for browse_directory: %s', E)

        # Local browsing fallback
        entry = data.GLOBAL_PATHS.get(base)
        root = resolve_base_root(entry)
        if not root or not root.exists():
            return {"error": "base not found"}

        target = root / path if path else root

        if not target.exists():
            return {"error": "path not found"}

        if not target.is_dir():
            return {"error": "path is not a directory"}

        items = []
        dir_count = 0
        file_count = 0
        total_size = 0

        try:
            for item in sorted(target.iterdir()):
                try:
                    stat = item.stat()
                    is_dir = item.is_dir()
                    ext = item.suffix if not is_dir else ""
                    size = stat.st_size if not is_dir else 0

                    if is_dir:
                        dir_count += 1
                    else:
                        file_count += 1
                        total_size += size

                    items.append({
                        "name": item.name,
                        "type": "dir" if is_dir else "file",
                        "ext": ext,
                        "category": get_file_category(ext) if not is_dir else "dir",
                        "size_bytes": size,
                        "size_human": format_size(size) if not is_dir else "",
                        "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                        "path": str(item.relative_to(root)),
                        "permissions": oct(stat.st_mode)[-3:]
                    })
                except (PermissionError, OSError):
                    continue
        except PermissionError:
            return {"error": "permission denied"}

        return {
            "base": base,
            "current_path": path or "/",
            "full_path": str(target),
            "parent_path": str(Path(path).parent) if path else None,
            "items": items,
            "summary": {
                "dirs": dir_count,
                "files": file_count,
                "total_items": len(items),
                "total_size_human": format_size(total_size)
            }
        }
    
    @routerFile.get("/download/{base}")
    def download_file(path: str, machine:Machine):
        try:
            url: str = f"{machine.url_connect}/download/?path={path}"
            response = requests.get(url, stream=True)
            response.raise_for_status()
            return FileResponse(
                content=response.content,
                filename=Path(path).name,
                media_type=response.headers.get("content-type", "application/octet-stream")
            )   
        except requests.exceptions.Timeout:
            raise HTTPException(status_code=504, detail="Timeout ao acessar o servidor de arquivos")

        except requests.exceptions.ConnectionError:
            raise HTTPException(status_code=502, detail="Servidor de arquivos indisponível")

        except requests.exceptions.HTTPError:
            raise HTTPException(
                status_code=response.status_code,
                detail="Erro ao baixar arquivo do servidor remoto"
            )

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @routerFile.delete("/delete/{base}")
    def delete_item(base: str, path: str):
        """Deleta arquivo ou diretório"""
        entry = data.GLOBAL_PATHS.get(base)
        root = resolve_base_root(entry)
        if not root:
            raise HTTPException(status_code=404, detail="base not found")
        
        target = root / path
        if not target.exists():
            raise HTTPException(status_code=404, detail="path not found")
        
        try:
            if target.is_dir():
                shutil.rmtree(target)
                return {"message": "directory deleted", "path": str(path)}
            else:
                target.unlink()
                return {"message": "file deleted", "path": str(path)}
        except PermissionError:
            raise HTTPException(status_code=403, detail="permission denied")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"error deleting: {str(e)}")
    
    @routerFile.post("/create-folder/{base}")
    def create_folder(base: str, path: str = "", name: str = ""):
        """Cria nova pasta"""
        entry = data.GLOBAL_PATHS.get(base)
        root = resolve_base_root(entry)
        if not root:
            raise HTTPException(status_code=404, detail="base not found")
        
        if not name:
            raise HTTPException(status_code=400, detail="name is required")
        
        target = root / path / name if path else root / name
        
        try:
            target.mkdir(parents=True, exist_ok=False)
            return {
                "message": "folder created",
                "path": str(target.relative_to(root)),
                "name": name
            }
        except FileExistsError:
            raise HTTPException(status_code=409, detail="folder already exists")
        except PermissionError:
            raise HTTPException(status_code=403, detail="permission denied")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"error creating folder: {str(e)}")

    @routerFile.post("/rename/{base}")
    def rename_item(base: str, path: str, new_name: str):
        """Renomeia arquivo ou pasta"""
        entry = data.GLOBAL_PATHS.get(base)
        root = resolve_base_root(entry)
        if not root:
            raise HTTPException(status_code=404, detail="base not found")
        
        target = root / path
        if not target.exists():
            raise HTTPException(status_code=404, detail="path not found")
        
        new_path = target.parent / new_name
        
        try:
            target.rename(new_path)
            return {
                "message": "renamed",
                "old_path": str(path),
                "new_path": str(new_path.relative_to(root)),
                "new_name": new_name
            }
        except FileExistsError:
            raise HTTPException(status_code=409, detail="target already exists")
        except PermissionError:
            raise HTTPException(status_code=403, detail="permission denied")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"error renaming: {str(e)}")

    # ═══════════════════════════════════════════════════════════════
    # Navegação Direta por Path (sem base)
    # ═══════════════════════════════════════════════════════════════

    @routerFile.get("/browse-path")
    def browse_path_direct(path: str = Query("/", description="Caminho absoluto no OS"), machine_id: Optional[int] = None, mac: Optional[str] = None):
        """Navega por qualquer diretório do OS dado um caminho absoluto.

        Se `machine_id` ou `mac` for fornecido, encaminha a requisição para
        o `machine.url_connect` remoto (`/files/browse-path`). Caso contrário,
        lista localmente.
        """
        # Determine whether the path belongs to a registered global base.
        match = FilesTools.isGLOBAL_PATH(path_local=path)

        logger.debug("browse_path_direct called: path=%s machine_id=%s mac=%s match=%s", path, machine_id, mac, match)

        # Resolve the preferred target machine: caller-specified wins (machine_id/mac),
        # otherwise fall back to the machine referenced by GLOBAL_PATHS for this path.
        target_machine = None
        if machine_id is not None or mac is not None:
            target_machine = FilesTools.resolve_machine(machine_id=machine_id, mac=mac)

        if not target_machine and isinstance(match, dict) and match.get('type') == 'machine':
            target_machine = match.get('machine')
            if not target_machine and match.get('machine_id'):
                try:
                    repo = MachineRepository()
                    target_machine = repo.get_machine_by_id(match.get('machine_id'))
                except Exception:
                    target_machine = None

        # If a remote machine is known and exposes `url_connect`, forward the request.
        if target_machine and getattr(target_machine, 'url_connect', None):
            try:
                base = str(target_machine.url_connect).rstrip('/')
                url = f"{base}/files/browse-path?path={requests.utils.requote_uri(path)}"
                r = requests.get(url, timeout=8)
                if r.ok:
                    return r.json()
                raise HTTPException(status_code=502, detail=f"remote HTTP {r.status_code}")
            except requests.RequestException as e:
                logger.error("Error forwarding browse_path_direct to remote: %s", e)
                raise HTTPException(status_code=502, detail="remote request failed")

        # Local behaviour
        target = Path(path)

        if not target.exists():
            raise HTTPException(status_code=404, detail="path not found")
        if not target.is_dir():
            raise HTTPException(status_code=400, detail="path is not a directory")

        items = []
        dir_count = 0
        file_count = 0
        total_size = 0

        try:
            for item in sorted(target.iterdir()):
                try:
                    stat = item.stat()
                    is_dir = item.is_dir()
                    ext = item.suffix if not is_dir else ""
                    size = stat.st_size if not is_dir else 0

                    if is_dir:
                        dir_count += 1
                    else:
                        file_count += 1
                        total_size += size

                    items.append({
                        "name": item.name,
                        "type": "dir" if is_dir else "file",
                        "ext": ext,
                        "category": get_file_category(ext) if not is_dir else "dir",
                        "size_bytes": size,
                        "size_human": format_size(size) if not is_dir else "",
                        "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                        "path": str(item),
                        "permissions": oct(stat.st_mode)[-3:]
                    })
                except (PermissionError, OSError):
                    continue
        except PermissionError:
            raise HTTPException(status_code=403, detail="permission denied")

        return {
            "mode": "direct",
            "current_path": str(target),
            "parent_path": str(target.parent) if str(target) != "/" else None,
            "items": items,
            "summary": {
                "dirs": dir_count,
                "files": file_count,
                "total_items": len(items),
                "total_size_human": format_size(total_size)
            }
        }

    @routerFile.get("/read-path")
    def read_file_direct(path: str):
        """Lê conteúdo de um arquivo por caminho absoluto"""
        file = Path(path)
        result = _read_file_path(file)
        if "error" in result:
            # map to HTTPException for direct path endpoints
            err = result.get("error")
            if err == "file not found":
                raise HTTPException(status_code=404, detail=err)
            if err == "path is not a file":
                raise HTTPException(status_code=400, detail=err)
            if err == "permission denied":
                raise HTTPException(status_code=403, detail=err)
            raise HTTPException(status_code=500, detail=err)

        # add name and human size for direct path API
        try:
            return {
                "path": result["path"],
                "name": file.name,
                "size_bytes": result["size_bytes"],
                "size_human": format_size(result["size_bytes"]),
                "content": file.read_text(encoding="utf-8", errors="replace")
            }
        except PermissionError:
            raise HTTPException(status_code=403, detail="permission denied")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @routerFile.get("/download-path")
    def download_file_direct(path: str):
        """Download de arquivo por caminho absoluto"""
        file = Path(path)
        if not file.exists():
            raise HTTPException(status_code=404, detail="file not found")
        if not file.is_file():
            raise HTTPException(status_code=400, detail="path is not a file")
        
        mime = mimetypes.guess_type(str(file))[0] or 'application/octet-stream'
        return FileResponse(path=str(file), filename=file.name, media_type=mime)

    @routerFile.delete("/delete-path")
    def delete_item_direct(path: str):
        """Deleta arquivo ou diretório por caminho absoluto"""
        target = Path(path)
        if not target.exists():
            raise HTTPException(status_code=404, detail="path not found")
        
        try:
            if target.is_dir():
                shutil.rmtree(target)
                return {"message": "directory deleted", "path": str(target)}
            else:
                target.unlink()
                return {"message": "file deleted", "path": str(target)}
        except PermissionError:
            raise HTTPException(status_code=403, detail="permission denied")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @routerFile.post("/create-folder-path")
    def create_folder_direct(path: str, name: str):
        """Cria nova pasta por caminho absoluto"""
        if not name:
            raise HTTPException(status_code=400, detail="name is required")
        
        target = Path(path) / name
        
        try:
            target.mkdir(parents=True, exist_ok=False)
            return {"message": "folder created", "path": str(target), "name": name}
        except FileExistsError:
            raise HTTPException(status_code=409, detail="folder already exists")
        except PermissionError:
            raise HTTPException(status_code=403, detail="permission denied")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @routerFile.post("/rename-path")
    def rename_item_direct(path: str, new_name: str):
        """Renomeia arquivo ou pasta por caminho absoluto"""
        target = Path(path)
        if not target.exists():
            raise HTTPException(status_code=404, detail="path not found")
        
        new_path = target.parent / new_name
        
        try:
            target.rename(new_path)
            return {"message": "renamed", "old_path": str(target), "new_path": str(new_path), "new_name": new_name}
        except FileExistsError:
            raise HTTPException(status_code=409, detail="target already exists")
        except PermissionError:
            raise HTTPException(status_code=403, detail="permission denied")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @routerFile.post("/upload-path")
    async def upload_to_path(file: UploadFile = File(...), path: str = Query("/tmp", description="Diretório destino absoluto")):
        """Upload de arquivo para um caminho absoluto no OS"""
        dest_dir = Path(path)
        if not dest_dir.exists():
            raise HTTPException(status_code=404, detail="destination path not found")
        if not dest_dir.is_dir():
            raise HTTPException(status_code=400, detail="destination is not a directory")
        
        dest = dest_dir / file.filename
        
        try:
            content = await file.read()
            with dest.open("wb") as buffer:
                buffer.write(content)
            return {
                "status": "ok",
                "filename": file.filename,
                "path": str(dest),
                "size": len(content),
                "size_human": format_size(len(content))
            }
        except PermissionError:
            raise HTTPException(status_code=403, detail="permission denied")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        
    @routerFile.get("/search-path")
    def search_path_direct(
        path: str = Query(..., description="Caminho absoluto raiz da busca"),
        query: str = "",
        ext: Optional[str] = Query(None),
        category: Optional[str] = Query(None),
        min_size: Optional[int] = Query(None),
        max_size: Optional[int] = Query(None),
        sort: str = Query("name"),
        limit: int = Query(50),
        content: Optional[str] = Query(None),
        machine_id: Optional[int] = None, mac: Optional[str] = None
    ):
        """Busca avançada por caminho absoluto"""
        # Remote forwarding if machine specified
        if machine_id or mac:
            try:
                machine = FilesTools.resolve_machine(machine_id=machine_id, mac=mac)
                if machine and getattr(machine, 'url_connect', None):
                    params = {
                        'path': path,
                        'query': query,
                        'ext': ext,
                        'category': category,
                        'min_size': min_size,
                        'max_size': max_size,
                        'sort': sort,
                        'limit': limit
                    }
                    if content:
                        params['content'] = content
                    try:
                        r = requests.get(machine.url_connect.rstrip('/') + '/files/search-path', params=params, timeout=8)
                        if r.ok:
                            return r.json()
                        raise HTTPException(status_code=502, detail=f"remote HTTP {r.status_code}")
                    except requests.RequestException as e:
                        logger.error("Error forwarding search_path to remote: %s", e)
                        raise HTTPException(status_code=502, detail="remote request failed")
            except Exception as E:
                logger.error('Error resolving machine for search_path_direct: %s', E)

        root = Path(path)
        if not root.exists() or not root.is_dir():
            raise HTTPException(status_code=404, detail="path not found or not a directory")
        
        if not query and not ext and not category and not content:
            raise HTTPException(status_code=400, detail="query, ext, category ou content obrigatório")
        
        results = []
        
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if query and query.lower() not in p.name.lower():
                continue
            if ext and p.suffix.lower() != ext.lower():
                continue
            file_cat = get_file_category(p.suffix)
            if category and file_cat != category.lower():
                continue
            
            try:
                stat = p.stat()
            except (PermissionError, OSError):
                continue
            
            if min_size and stat.st_size < min_size:
                continue
            if max_size and stat.st_size > max_size:
                continue
            
            if content:
                if stat.st_size > 1024 * 1024:
                    continue
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                    if content.lower() not in text.lower():
                        continue
                except:
                    continue
            
            results.append({
                "name": p.name,
                "path": str(p),
                "ext": p.suffix,
                "category": file_cat,
                "size_bytes": stat.st_size,
                "size_human": format_size(stat.st_size),
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "modified_ts": stat.st_mtime
            })
            
            if len(results) >= limit * 2:
                break
        
        if sort == "size":
            results.sort(key=lambda x: x["size_bytes"], reverse=True)
        elif sort == "date":
            results.sort(key=lambda x: x["modified_ts"], reverse=True)
        else:
            results.sort(key=lambda x: x["name"].lower())
        
        results = results[:limit]
        
        return {
            "mode": "direct",
            "root": str(root),
            "query": query,
            "count": len(results),
            "matches": results
        }
    