from dataclasses import dataclass
import logging
from pathlib import Path
from models.App import App
import json

logger = logging.getLogger("server.services.apps.appservice")

@dataclass
class AppService:
    path_data:Path = ("/home/quitto/.config/quitto_server")

    def load_apps(self) -> list:
        apps:list = []
        try:
            if not self.path_data.exists():
                return apps

            with open(self.path_data / "apps.json", "r", encoding="utf-8") as f:
                content:dict = json.load(f.read())

            for app in content:
                apps.append(App(
                    name=app["name"],
                    app_path=app["path"]
                ))
            return apps
        except PermissionError as e:
            logger.exception("[ERROR] Permission denied while loading apps: %s", e)
        except Exception as e:
            logger.exception("[ERROR] Unexpected error while loading apps: %s", e)

