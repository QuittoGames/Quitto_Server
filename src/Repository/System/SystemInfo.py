import logging
import platform
import os
import sys
import socket
import datetime
import shutil
from data import data

logger = logging.getLogger("server.system.info")


# ═══════════════════════════════════════════════════════════════
# SystemInfo - Coleta de informações do sistema
# ═══════════════════════════════════════════════════════════════
class SystemInfo:
    """Classe utilitária para coletar informações do sistema"""
    
    @staticmethod
    def system() -> dict:
        """Info geral do sistema operacional"""
        return {
            "os": platform.system(),
            "os_release": platform.release(),
            "os_version": platform.version(),
            "hostname": socket.gethostname(),
            "architecture": platform.machine(),
            "processor": platform.processor() or "N/A",
            "node": platform.node(),
        }
    
    @staticmethod
    def python() -> dict:
        """Info do Python em execução"""
        return {
            "version": sys.version.split()[0],
            "full_version": sys.version,
            "executable": sys.executable,
            "platform": sys.platform,
            "implementation": platform.python_implementation(),
            "compiler": platform.python_compiler(),
            "path": sys.path[:5],
        }
    
    @staticmethod
    def disk(partitions: list = None) -> dict:
        """Info dos discos montados"""
        if partitions is None:
            partitions = ["/", "/home", "/run/media/quitto/DATA"]
        
        disks = []
        for partition in partitions:
            try:
                usage = shutil.disk_usage(partition)
                disks.append({
                    "mount": partition,
                    "total_gb": round(usage.total / (1024**3), 2),
                    "used_gb": round(usage.used / (1024**3), 2),
                    "free_gb": round(usage.free / (1024**3), 2),
                    "percent_used": round((usage.used / usage.total) * 100, 1)
                })
            except:
                pass
        return {"disks": disks}
    
    @staticmethod
    def network() -> dict:
        """Info básica de rede"""
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
        except:
            hostname = "unknown"
            local_ip = "127.0.0.1"
        
        return {
            "hostname": hostname,
            "local_ip": local_ip,
            "fqdn": socket.getfqdn(),
        }
    
    @staticmethod
    def datetime_info() -> dict:
        """Data e hora atual"""
        now = datetime.datetime.now()
        utc_now = datetime.datetime.utcnow()
        return {
            "local": now.strftime("%Y-%m-%d %H:%M:%S"),
            "utc": utc_now.strftime("%Y-%m-%d %H:%M:%S"),
            "timezone": datetime.datetime.now().astimezone().tzname(),
            "timestamp": int(now.timestamp()),
            "iso": now.isoformat(),
        }
    
    @staticmethod
    def env(safe_vars: list = None) -> dict:
        """Variáveis de ambiente úteis (sem expor senhas)"""
        if safe_vars is None:
            safe_vars = ["USER", "HOME", "SHELL", "LANG", "PATH", "PWD", "TERM"]
        return {k: os.environ.get(k, "N/A") for k in safe_vars}
    
    @staticmethod
    def process() -> dict:
        """Info do processo atual"""
        return {
            "pid": os.getpid(),
            "ppid": os.getppid(),
            "cwd": os.getcwd(),
            "uid": os.getuid() if hasattr(os, 'getuid') else "N/A",
            "gid": os.getgid() if hasattr(os, 'getgid') else "N/A",
        }
    
    @staticmethod
    def all() -> dict:
        """Todas as informações juntas"""
        return {
            "system": SystemInfo.system(),
            "python": SystemInfo.python(),
            "disk": SystemInfo.disk(),
            "network": SystemInfo.network(),
            "datetime": SystemInfo.datetime_info(),
            "env": SystemInfo.env(),
            "process": SystemInfo.process(),
            "bases": {k: str(v) for k, v in data.GLOBAL_PATHS.items()}
        }
