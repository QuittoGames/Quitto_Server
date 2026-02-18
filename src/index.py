from data import data
from tool import tool
from fastapi import FastAPI
from dotenv import load_dotenv
import asyncio
import logging
import os
from starlette.middleware.sessions import SessionMiddleware

logger = logging.getLogger("server")
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


data_local = data()
app = FastAPI(title="Quitto MCP Servers")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY")
)


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
        data_local.load_machines()
        if data_local.Debug:
            await tool.verify_modules()
    except StopAsyncIteration as E:
        logger.error(f"Erro StopAsyncIteration: {E}")

if __name__ == "__main__":
    asyncio.run(main())
