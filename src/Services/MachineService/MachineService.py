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

    @routerMachine.post("/wake_on_lan")
    def wake_on_lan(id_machine:int) -> dict:
        """
        Sends a Wake-on-LAN (WOL) packet to the machine identified by the given ID.

        Args:
            id_machine (int): The unique identifier of the machine to wake.

        Returns:
            dict: A dictionary containing the result of the WOL operation.

        Raises:
            HTTPException: If the machine ID is not provided (None), raises a 404 error with an empty detail message.
        """
        # Validate input
        if id_machine is None:
            raise HTTPException(status_code=400, detail="Missing required parameter: id_machine")

        # Ensure repository instance
        global repo
        if repo is None:
            repo = MachineRepository()

        machine: Optional[Machine] = repo.get_machine_by_id(id_machine)
        if machine is None:
            raise HTTPException(status_code=404, detail="Machine not found")

        # Use Machine.wake_on_lan() helper (returns bool)
        try:
            ok = machine.wake_on_lan()
            if ok:
                return {"ok": True, "id": machine.id, "address": machine.address}
            else:
                raise HTTPException(status_code=500, detail="Failed to send Wake-on-LAN packet")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[ERROR] wake_on_lan failed for id {id_machine}: {e}")
            raise HTTPException(status_code=500, detail=str(e))