from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from data import data
from models.GlobalPaths import GlobalPaths
import os
import sys
from pathlib import Path
import logging
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from Repository.System.SystemInfo import SystemInfo

# Logger specific to this service: server.services.webservice
logger = logging.getLogger("server.services.webservice")

# ═══════════════════════════════════════════════════════════════
# WebService - Rotas de Info do Sistema e Dashboard
# ═══════════════════════════════════════════════════════════════

routerWeb = APIRouter(prefix="/api", tags=["System Info"])

class WebService:
    """Service para rotas web e informações do sistema"""
    
    # ─── Info do Sistema ────────────────────────────────────────
    
    @routerWeb.get("/info/system")
    def info_system():
        """Info geral do sistema operacional"""
        logger.info("/info/system requested")
        result = SystemInfo.system()
        if isinstance(result, dict):
            logger.debug("system info keys: %s", list(result.keys()))
        else:
            logger.debug("system info: %s", type(result).__name__)
        return result
    
    @routerWeb.get("/info/python")
    def info_python():
        """Info do Python"""
        logger.info("/info/python requested")
        result = SystemInfo.python()
        logger.debug("python info keys: %s", list(result.keys()) if isinstance(result, dict) else type(result).__name__)
        return result
    
    @routerWeb.get("/info/disk")
    def info_disk():
        """Info dos discos"""
        logger.info("/info/disk requested")
        result = SystemInfo.disk()
        if isinstance(result, dict) and "disks" in result:
            logger.debug("disk count: %d", len(result.get("disks", [])))
        else:
            logger.debug("disk info: %s", type(result).__name__)
        return result
    
    @routerWeb.get("/info/network")
    def info_network():
        """Info de rede"""
        logger.info("/info/network requested")
        result = SystemInfo.network()
        logger.debug("network summary: hostname=%s local_ip=%s", result.get("hostname"), result.get("local_ip") if isinstance(result, dict) else "N/A")
        return result
    
    @routerWeb.get("/info/datetime")
    def info_datetime():
        """Data e hora atual"""
        logger.info("/info/datetime requested")
        result = SystemInfo.datetime_info()
        logger.debug("datetime summary: local=%s utc=%s", result.get("local"), result.get("utc") if isinstance(result, dict) else "N/A")
        return result
    
    @routerWeb.get("/info/env")
    def info_env():
        """Variáveis de ambiente"""
        logger.info("/info/env requested")
        result = SystemInfo.env()
        if isinstance(result, dict):
            logger.debug("env keys: %s", list(result.keys()))
        else:
            logger.debug("env info: %s", type(result).__name__)
        return result
    
    @routerWeb.get("/info/process")
    def info_process():
        """Info do processo"""
        logger.info("/info/process requested")
        result = SystemInfo.process()
        logger.debug("process summary: pid=%s cwd=%s", result.get("pid") if isinstance(result, dict) else "N/A", result.get("cwd") if isinstance(result, dict) else "N/A")
        return result
    
    @routerWeb.get("/info/all")
    def info_all():
        """TUDO junto - info completa do servidor"""
        logger.info("/info/all requested")
        result = SystemInfo.all()
        if isinstance(result, dict):
            logger.debug("all info sections: %s", list(result.keys()))
        else:
            logger.debug("all system info: %s", type(result).__name__)
        return result
    
    # ─── Utilitários ────────────────────────────────────────────
    
    @routerWeb.get("/global_paths")
    def list_global_paths():
        """Lista as global_paths (registered global paths) disponíveis"""
        try:
            # Ensure MACHINE_BASES / BASES are loaded and resolved
            try:
                data.load_machines()
            except Exception:
                # non-fatal; proceed with whatever is available
                pass

            # Ensure we have an up-to-date view including remote machines
            try:
                data.load_global_paths()
            except Exception:
                # non-fatal
                pass

            # Provide both legacy-friendly summary and a structured `entries` field
            legacy = {}
            try:
                resolved = data.get_resolved_bases() or {}
                for name, entries in resolved.items():
                    path_objs = [p for p in entries if isinstance(p, Path)]
                    path_list = [str(p) for p in path_objs]
                    exists_list = [p.exists() for p in path_objs]
                    readable_list = [os.access(p, os.R_OK) if p.exists() else False for p in path_objs]
                    legacy[name] = {
                        "path": path_list,
                        "exists": all(exists_list) if path_objs else False,
                        "readable": all(readable_list) if path_objs else False
                    }
            except Exception:
                legacy = {}

            gp = GlobalPaths.from_mapping(data.GLOBAL_PATHS or {})

            return {"legacy": legacy, "entries": gp.to_primitive()}
        except Exception as e:
            # Retorna JSON com erro para evitar resposta HTML que quebra o parse no frontend
            return {"error": f"failed to list global_paths: {str(e)}"}

    @routerWeb.get("/machines")
    def list_machines():
        """Lista as máquinas conhecidas (MAC, nome, interface, vendor, etc)"""
        # Garante que as máquinas estão carregadas
        data.load_machines()
        machines = []
        for m in data.MACHINES:
            machines.append({
                "name": getattr(m, "name", None),
                "address": getattr(m, "address", None),
                "interface": getattr(m, "interface", None),
                "vendor": getattr(m, "vendor", None),
                "is_randomized": getattr(m, "is_randomized", False)
            })
        return {"machines": machines}
    
    @routerWeb.get("/health")
    def health_check():
        """Health check simples"""
        import datetime
        return {
            "status": "ok",
            "timestamp": datetime.datetime.now().isoformat(),
            "uptime_info": "Server is running"
        }
