import os
import logging
from dataclasses import dataclass
from data import data
import subprocess
from fastapi import FastAPI
from Services.Files.FileService import routerFile
from Services.WebService import routerWeb
from Services.MainService import routerMain
from Services.SetupProjectService import routerProject
from Services.MCP.MCPService import routerMCP
from Services.DockerService import routerDocker
from Services.CalenderService import routerCalender
from Services.MachineService.MachineService import routerMachine
import sys

logger = logging.getLogger("mcp.tool")

@dataclass
class tool:

    @staticmethod
    async def verify_modules():
        logger.info("Verificando módulos...")
        try:
            req_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "requirements", "requirements.txt"))
            if os.path.exists(req_path):
                subprocess.run([sys.executable, "-m", "pip", "install", "-r", req_path], check=True)
                logger.info("Módulos verificados!")
            else:
                logger.error("Arquivo requirements.txt não encontrado")
        except Exception as E:
            logger.error(f"Erro ao verificar módulos: {E}")

    @staticmethod
    async def add_path_modules(data_local: data):
        if data_local.modules_local is None:
            return
        try:
            for i in data_local.modules_local:
                sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), i)))
                if data_local.Debug:
                    logger.debug(f"Module_local: {i}")
        except Exception as E:
            logger.error(f"Erro ao adicionar módulos: {E}")

    @staticmethod
    async def add_rotes(app: FastAPI):
        try:
            # Machine routes
            app.include_router(router=routerMachine)
            app.include_router(router=routerMain)
            app.include_router(router=routerFile)
            app.include_router(router=routerMCP)
            app.include_router(router=routerWeb)
            app.include_router(router=routerProject)
            app.include_router(router=routerDocker)
            app.include_router(router=routerCalender)

            # Adiciona rotas de autenticação/usuario (LoginService)
            from Services.UserServices.Login.LoginService import routerLogin
            app.include_router(router=routerLogin)

            from fastapi.staticfiles import StaticFiles
            web_dir = os.path.join(os.path.dirname(__file__), "web")
            app.mount("/static", StaticFiles(directory=web_dir), name="static")
            # Also expose common subfolders at root paths for compatibility
            css_dir = os.path.join(web_dir, "css")
            js_dir = os.path.join(web_dir, "js")
            pages_dir = os.path.join(web_dir, "pages")
            img_dir = os.path.join(web_dir, "img")
            if os.path.exists(css_dir):
                app.mount("/css", StaticFiles(directory=css_dir), name="css")
                # ensure paths under /static also resolve (e.g. /static/css/style.css)
                app.mount("/static/css", StaticFiles(directory=css_dir), name="static-css")
            if os.path.exists(js_dir):
                app.mount("/js", StaticFiles(directory=js_dir), name="js")
                app.mount("/static/js", StaticFiles(directory=js_dir), name="static-js")
            if os.path.exists(pages_dir):
                app.mount("/pages", StaticFiles(directory=pages_dir), name="pages")
                app.mount("/static/pages", StaticFiles(directory=pages_dir), name="static-pages")
            if os.path.exists(img_dir):
                app.mount("/img", StaticFiles(directory=img_dir), name="img")
                app.mount("/static/img", StaticFiles(directory=img_dir), name="static-img")
        except Exception as E:
            # log full traceback to help diagnose route registration failures
            logger.exception("[ERROR] MCP não conseguiu adicionar rotas")

    @staticmethod
    def switch_clients():
        """Faz Trasição de Nome abistrato para seu endereço MAC original"""
        pass