from fastapi import APIRouter, HTTPException, Request
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from Repository.User.UserRepository import UserRepository
from models.User import User
from Services.UserServices.Login.LoginBody import LoginBody
import logging

# Logger specific to this service: server.services.user.login.loginservice
logger = logging.getLogger("server.services.user")

# ═══════════════════════════════════════════════════════════════
# UserService - Rotas de Info do Sistema e Dashboard
# ═══════════════════════════════════════════════════════════════

routerUser = APIRouter(prefix="/api/auth/user", tags=["User"])

class UserService:
    @routerUser.get('/name')
    def get_name(request: Request):
        """Return the current authenticated user's name.

        Returns 401 if not authenticated, or 404 if session exists but name missing.
        """
        if not request.session.get("authenticated"):
            raise HTTPException(
                status_code=401,
                detail="Unauthorized: not authenticated"
            )
        name = request.session.get("name")
        if not name:
            raise HTTPException(
                status_code=404,
                detail="Session user name missing"
            )
        return {"name": name}