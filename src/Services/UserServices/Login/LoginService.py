from fastapi import APIRouter, HTTPException, Request
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from Repository.User.UserRepository import UserRepository
from models.User import User
from Services.UserServices.Login.LoginBody import LoginBody
import logging

# Logger specific to this service: server.services.user.login.loginservice
logger = logging.getLogger("server.services.user.login.loginservice")

# ═══════════════════════════════════════════════════════════════
# LoginService - Rotas de Info do Sistema e Dashboard
# ═══════════════════════════════════════════════════════════════

routerLogin = APIRouter(prefix="/api/auth", tags=["Login"])

class LoginService:
    @routerLogin.post("/login")
    def login(request: Request, data: LoginBody):
        repo = UserRepository()

        client_user:User = repo.get_user_by_name(data.name.lower())

        if client_user is None:
            raise HTTPException(status_code=404, detail="User not found")

        if not client_user.verify_password(data.password):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        request.session["user_id"] = client_user.get_id()
        request.session["name"] = client_user.get_name()
        request.session["authenticated"] = True

        return {"ok": True}

    @routerLogin.get("/check")
    def check_login(request: Request):
        user_id = request.session.get("user_id")
        name = request.session.get("name")
        auth = request.session.get("authenticated")
        
        if user_id and name and auth:
            return {"authenticated": True, "user_id": user_id, "name": name}
        raise HTTPException(status_code=401, detail="Not authenticated")