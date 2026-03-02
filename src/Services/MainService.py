from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from data import data
import os
import datetime
import logging

# Logger specific to this service: server.services.mainservice
logger = logging.getLogger("server.services.mainservice")

routerMain = APIRouter()

# ═══════════════════════════════════════════════════════════════
# MainService - Rotas principais da aplicação MCP
# ═══════════════════════════════════════════════════════════════

class MainService:
    """Service para rotas principais e status do servidor"""
    
    @routerMain.get("/server", response_class=HTMLResponse)
    def server_dashboard():
        """Serve o dashboard web do MCP"""
        html_path = os.path.join(os.path.dirname(__file__), "..", "web", "index.html")
        try:
            with open(html_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return "<h1>MCP Server Online</h1><p>Dashboard não encontrado</p>"
        
    @routerMain.get("/files-manager", response_class=HTMLResponse)
    def files_manager():
        """Serve a página de gerenciamento de arquivos"""
        html_path = os.path.join(os.path.dirname(__file__), "..", "web", "pages", "files.html")
        try:
            with open(html_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return "<h1>File Manager</h1><p>Página não encontrada</p>"

    @routerMain.get("/login.html")
    def redirect_login():
        # Serve the login page file directly instead of redirecting
        html_path = os.path.join(os.path.dirname(__file__), "..", "web", "pages", "login.html")
        if os.path.exists(html_path):
            return FileResponse(html_path)
        return RedirectResponse(url="/pages/login.html")

    @routerMain.get("/pages/login.html")
    def redirect_pages_login():
        # The static files mount also serves /pages/*; prefer returning the file
        html_path = os.path.join(os.path.dirname(__file__), "..", "web", "pages", "login.html")
        if os.path.exists(html_path):
            return FileResponse(html_path)
        # fallback to redirect (should not loop because mount would handle it)
        return RedirectResponse(url="/pages/login.html")
    
    @routerMain.get("/health")
    def health_check():
        """Health check do servidor"""
        return {
            "status": "healthy",
            "timestamp": datetime.datetime.now().isoformat(),
            "uptime": "Server is running"
        }
    
    @routerMain.get("/info")
    def server_info():
        """Informações detalhadas do servidor"""
        return {
            "server": {
                "name": "Quitto MCP Server",
                "version": "1.0.0",
                "protocol": "mcp"
            },
            "bases": {k: str(v) for k, v in data.GLOBAL_PATHS.items()},
            "routes": {
                "files": [
                    "GET /files/list/{base}",
                    "GET /files/read/{base}",
                    "GET /files/search/{base}",
                    "GET /files/tree/{base}",
                    "GET /files/stats/{base}",
                    "POST /files/add"
                ],
                "api": [
                    "GET /api/info/system",
                    "GET /api/info/python",
                    "GET /api/info/disk",
                    "GET /api/info/network",
                    "GET /api/info/datetime",
                    "GET /api/info/all",
                    "GET /api/global_paths",
                    "GET /api/health"
                ],
                "main": [
                    "GET /",
                    "GET /server",
                    "GET /health",
                    "GET /info"
                ]
            }
        }


    @routerMain.get("/")
    def info():
        """Informações detalhadas do servidor"""
        return {
            "server": {
                "name": "Quitto Server",
                "version": "1.0.0",
                "protocol": "server"
            },
            "server": {
                "name": "Quitto MCP Server",
                "version": "0.2",
                "tool_registry_version": "1.0",
                "protocol": "mcp"
            },
            "bases": {k: str(v) for k, v in data.GLOBAL_PATHS.items()},
            "routes": {
                "files": [
                    "GET /files/list/{base}",
                    "GET /files/read/{base}",
                    "GET /files/search/{base}",
                    "GET /files/tree/{base}",
                    "GET /files/stats/{base}",
                    "POST /files/add"
                ],
                "api": [
                    "GET /api/info/system",
                    "GET /api/info/python",
                    "GET /api/info/disk",
                    "GET /api/info/network",
                    "GET /api/info/datetime",
                    "GET /api/info/all",
                    "GET /api/global_paths",
                    "GET /api/health"
                ],
                "main": [
                    "GET /",
                    "GET /server",
                    "GET /health",
                    "GET /info"
                ]
            }
        }

    @routerMain.get("/machines", response_class=HTMLResponse)
    def machines_page():
        """Serve the machines management page."""
        return FileResponse("web/pages/machines.html")
