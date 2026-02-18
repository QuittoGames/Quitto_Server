from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from data import data
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
        return SystemInfo.system()
    
    @routerWeb.get("/info/python")
    def info_python():
        """Info do Python"""
        return SystemInfo.python()
    
    @routerWeb.get("/info/disk")
    def info_disk():
        """Info dos discos"""
        return SystemInfo.disk()
    
    @routerWeb.get("/info/network")
    def info_network():
        """Info de rede"""
        return SystemInfo.network()
    
    @routerWeb.get("/info/datetime")
    def info_datetime():
        """Data e hora atual"""
        return SystemInfo.datetime_info()
    
    @routerWeb.get("/info/env")
    def info_env():
        """Variáveis de ambiente"""
        return SystemInfo.env()
    
    @routerWeb.get("/info/process")
    def info_process():
        """Info do processo"""
        return SystemInfo.process()
    
    @routerWeb.get("/info/all")
    def info_all():
        """TUDO junto - info completa do servidor"""
        return SystemInfo.all()
    
    # ─── Utilitários ────────────────────────────────────────────
    
    @routerWeb.get("/bases")
    def list_bases():
        """Lista as bases disponíveis"""
        try:
            result = {}
            for name, paths in data.BASES.items():
                # paths pode conter Path e outros objetos (ex: Machine)
                path_objs = [p for p in paths if isinstance(p, Path)]
                path_list = [str(p) for p in path_objs]
                exists_list = [p.exists() for p in path_objs]
                readable_list = [os.access(p, os.R_OK) if p.exists() else False for p in path_objs]
                result[name] = {
                    "path": path_list,
                    "exists": all(exists_list) if path_objs else False,
                    "readable": all(readable_list) if path_objs else False
                }
            return result
        except Exception as e:
            # Retorna JSON com erro para evitar resposta HTML que quebra o parse no frontend
            return {"error": f"failed to list bases: {str(e)}"}

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
