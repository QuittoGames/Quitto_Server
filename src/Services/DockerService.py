from fastapi import APIRouter, HTTPException, Query
from data import data
import os
import logging
import subprocess
# Logger specific to this service: server.services.dockerservice
logger = logging.getLogger("server.services.dockerservice")

routerDocker = APIRouter(tags=["Docker"])

class DockerService:
    @routerDocker.post("/docker_list")
    def docker_list(name: str = Query(..., description="Container Name")):
        if name == "" or name is None:
            raise HTTPException(status_code=404, detail="Name is null")

        docker_list = subprocess.run(["docker","ps","--filter",f"name={name}"], capture_output=True, text=True)

        if docker_list is None:
            raise HTTPException(status_code=404,detail="Docker ps is null")
        
        if docker_list.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Docker command failed: {docker_list.stderr}")

        containers = docker_list.stdout.strip().split("\n")

        return{
            "docker": containers,
            "returncode": docker_list.returncode
        }
