from fastapi import APIRouter, HTTPException, Query, Request
from data import data
import os
import logging
from pathlib import Path
import subprocess
from platform import platform

logger = logging.getLogger("server.services.setupprojectservice")
routerProject = APIRouter(tags=["Project Setup"])

class SetupProjectService:
    @routerProject.get("/create_project")
    def create_project(
        request:Request,
        name: str = Query(..., description="Nome do projeto"),
        language: str = Query(..., description="Linguagem do projeto"),
        path: str = Query(None, description="Caminho do projeto"),
    ):
        if not request.session.get("authenticated"):
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        OS = platform()
        if OS != "Windows":
            envPath: Path = Path(os.environ.get("HOME")) / ".config" / "ProjectSetup3.0"
        else:
            envPath: Path = Path(os.environ.get("APPDATA")) / "ProjectSetup3.0"
            
        if not os.path.exists(envPath):
            raise HTTPException(status_code=404, detail="ProjectSetup3.0 not found")
        
        service: Path = Path("/run/media/quitto/DATA/Projects/Python/ProjectSetup-3.0/projectsetup3/Services/CLIService.py")
        logger.debug("Service Path: {}".format(service))

        result = subprocess.run(
            ["python3", str(service), path or None, language, name],
            capture_output=True,
            text=True
        )

        logger.info(f"ProjectSetup result: returncode={result.returncode}")
        logger.debug(f"stdout={result.stdout}, stderr={result.stderr}")

        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
