from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
import os
import sys
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from models.Machine import Machine
from Repository.Machines.MachineRepository import MachineRepository
from typing import Optional
import logging

# Logger specific to this service: server.services.machineservice
logger = logging.getLogger("server.services.machineservice")

# ═══════════════════════════════════════════════════════════════
# MachineService - Rotas de Info do Sistema e Dashboard
# ═══════════════════════════════════════════════════════════════

routerMachine = APIRouter(prefix="/machine", tags=["Machine"])
repo: Optional[MachineRepository] = None

class MachineService:
    @routerMachine.post("/create")
    def create(self,machine:Machine,request:Request) -> dict:
        if not request.session.get("authenticated"):
            raise HTTPException(status_code=401, detail="Not authenticated")

        global repo
        if repo is None:
            repo = MachineRepository()

        repo.create_machine(machine)
        return {
            "https":200,
            "status": "created"
        }

    @routerMachine.get("/all")
    def get_all_machines(request: Request):
        if not request.session.get("authenticated"):
            raise HTTPException(status_code=401, detail="Not authenticated")

        global repo
        if repo is None:
            repo = MachineRepository()

        machines = repo.get_all_machines()
        return [
            {
                "id": m.id,
                "address": m.address,
                "name": m.name,
                "interface": m.interface,
                "vendor": m.vendor,
                "is_randomized": m.is_randomized,
            }
            for m in machines
        ]
