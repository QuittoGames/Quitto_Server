from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Request
from fastapi.responses import FileResponse
from pathlib import Path
from data import data
from .FilesTools import FilesTools
import os
import shutil
import psutil
import mimetypes
from datetime import datetime
from typing import Optional
from fastapi.responses import RedirectResponse
import logging

# Logger specific to this service: server.services.files.fileservice
logger = logging.getLogger("server.services.files.fileservice")

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

def _read_file_path(file_path: Path) -> dict:
    return FilesTools._read_file_path(file_path)

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
        entry = data.BASES.get(base)
        root = resolve_base_root(entry)
        if not root:
            return {"error": "base not found", "available": list(data.BASES.keys())}

        files = [str(p.relative_to(root)) for p in root.rglob("*.md")]
        return {"base": base, "count": len(files), "files": files}
    

    @routerFile.get("/read/{base}")
    def read_file(base: str, path: str):
        """Lê conteúdo de um arquivo"""
        candidate, err = _get_file_path_for(base, path)
        if err:
            return {"error": err}
        return _read_file_path(candidate)

    @routerFile.get("/find")
    def find_in_base(base: str = Query(..., description="Base name from data.BASES or an absolute path"), filename: str = Query(..., description="Filename or relative path to find"), limit: int = Query(50, description="Max matches to return")):
        """Busca um arquivo dentro de uma base (chave em data.BASES) ou em um caminho absoluto.

        - Se `base` for uma chave existente em `data.BASES`, procura em todas as entradas resolvidas dessa base.
        - Se `base` for um caminho, valida que ele esteja presente em `data.BASES` (mesma entrada) antes de pesquisar.
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

        # Case 1: base is a registered key in data.BASES
        if base in data.BASES:
            entries = data.BASES.get(base) or []
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

        # Case 2: base looks like a path — validate it's listed in data.BASES
        try:
            candidate_path = Path(base)
        except Exception:
            return {"error": "invalid base/path"}

        # Verify candidate_path is present in any data.BASES entry (exact match)
        found_in_bases = False
        for k, entries in data.BASES.items():
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
            return {"error": "path not registered in data.BASES"}

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
        content: Optional[str] = Query(None, description="Buscar dentro do conteúdo dos arquivos")
    ):
        """Busca avançada de arquivos na base"""
        entry = data.BASES.get(base)
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
        entry = data.BASES.get(base)
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
    def browse_directory(base: str, path: str = ""):
        """Navega por diretórios de uma base com detalhes completos"""
        entry = data.BASES.get(base)
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
    def download_file(base: str, path: str):
        """Download de arquivo"""
        entry = data.BASES.get(base)
        root = resolve_base_root(entry)
        if not root:
            raise HTTPException(status_code=404, detail="base not found")
        
        file = root / path
        if not file.exists():
            raise HTTPException(status_code=404, detail="file not found")
        
        if not file.is_file():
            raise HTTPException(status_code=400, detail="path is not a file")
        
        mime = mimetypes.guess_type(str(file))[0] or 'application/octet-stream'
        
        return FileResponse(
            path=str(file),
            filename=file.name,
            media_type=mime
        )
    
    @routerFile.delete("/delete/{base}")
    def delete_item(base: str, path: str):
        """Deleta arquivo ou diretório"""
        entry = data.BASES.get(base)
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
        entry = data.BASES.get(base)
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
        entry = data.BASES.get(base)
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
    def browse_path_direct(path: str = Query("/", description="Caminho absoluto no OS")):
        """Navega por qualquer diretório do OS dado um caminho absoluto"""
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
        content: Optional[str] = Query(None)
    ):
        """Busca avançada por caminho absoluto"""
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
    