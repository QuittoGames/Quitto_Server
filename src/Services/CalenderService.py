from fastapi import APIRouter,HTTPException
import os
import datetime
import json
from pathlib import Path
import subprocess
import logging
# Logger specific to this service: server.services.calenderservice
logger = logging.getLogger("server.services.calenderservice")

routerCalender = APIRouter(prefix="/calender", tags=["Calender"])

class CalenderServices:
    @routerCalender.get("/events")
    def getCalender():
        OutlookFusion_path:Path = Path("/run/media/quitto/DATA/Projects/Python/OutlookFusion/src/core")
        if not OutlookFusion_path.exists():
            raise HTTPException(status_code=404,detail="OutlookFusion path not found")
        
        if not CalenderServices.isInstall(OutlookFusion_path):
            raise HTTPException(status_code=500,detail="OutlookFusion installation failed")
    
        try:
            result = subprocess.run(
                ["outfusion","list"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                raise HTTPException(status_code=500, detail=f"outfusion falhou: {result.stderr}")
            
            # Tenta parsear JSON do outfusion
            try:
                events = json.loads(result.stdout)
            except json.JSONDecodeError:
                # Se não for JSON, retorna raw como lista de linhas
                lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
                events = [{"title": l, "date": None, "time": None} for l in lines]
            
            return {"events": events, "count": len(events), "fetched_at": datetime.datetime.now().isoformat()}
        except FileNotFoundError:
            raise HTTPException(status_code=500, detail="outfusion não encontrado no PATH")
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=504, detail="outfusion demorou demais pra responder")
        except PermissionError:
            raise HTTPException(status_code=403, detail="Sem permissão pra executar outfusion")
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"Erro de I/O: {e}")
    
    def isInstall(OutlookFusion_path:Path) -> bool:
        IS_INSTALLED = 100
        try:
            if not os.path.exists("/usr/local/bin/outfusion"):
                script = OutlookFusion_path / "install.sh"
                result = subprocess.run(
                    ["bash", str(script)],
                    capture_output=True, text=True, timeout=120
                )
                if "IS_INSTALLED" in result.stdout and "100" in result.stdout:
                    return True
                
                if result.returncode != 0:
                    return False
            return True
        except FileNotFoundError:
            # bash ou o script não existe no sistema
            return False
        except subprocess.TimeoutExpired:
            # build demorou demais
            return False
        except PermissionError:
            # sem permissão pra executar o script
            return False
        except OSError as e:
            # erro genérico de I/O (disco cheio, path inválido, etc)a
            return False