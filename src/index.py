from data import data
from tool import tool
from fastapi import FastAPI,Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import asyncio
import logging
import os
from starlette.middleware.sessions import SessionMiddleware
# Rate limiter integration removed; no LimitService dependency

data_local = data()

#Sete Configs In app 
def configure_logging():
    """Configure console logging with a compact, readable format."""
    root = logging.getLogger()
    # remove existing handlers to avoid duplicates
    for h in list(root.handlers):
        root.removeHandler(h)
    ch = logging.StreamHandler()
    fmt = logging.Formatter("%(asctime)s %(levelname)s: %(message)s", "%Y-%m-%d %H:%M:%S")
    ch.setFormatter(fmt)
    root.addHandler(ch)
    level = logging.DEBUG if getattr(data_local, "Debug", False) else logging.INFO
    root.setLevel(level)


configure_logging()

logger = logging.getLogger("server")
app = FastAPI(title="Quitto MCP Servers")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY")
)

@app.middleware("http")
async def pass_through_middleware(request: Request, call_next):
    # Rate limiter removed — pass requests through directly
    return await call_next(request)

@app.on_event("startup")
async def startup():
    """Registra rotas e módulos ao iniciar (funciona com uvicorn index:app)"""
    try:
        load_dotenv()
        await tool.add_path_modules(data_local)
        await tool.add_rotes(app)

        if data_local.Debug:
            await tool.verify_modules()
    except Exception as E:
        # log full traceback to help diagnose startup failures
        logger.exception("Erro no startup")


async def main():
    try:
        await tool.add_path_modules(data_local)
        await tool.add_rotes(app)
        data_local.load_apps()
        data_local.load_machines()
        if data_local.Debug:
            await tool.verify_modules()
    except StopAsyncIteration as E:
        logger.error(f"Erro StopAsyncIteration: {E}")

if __name__ == "__main__":
    asyncio.run(main())
