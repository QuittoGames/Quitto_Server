from fastapi import APIRouter, HTTPException, Request , UploadFile, File
from pathlib import Path
from data import data
from models.Machine import Machine
from models.Agent import Agent
from Services.MCP.MemoryService import MemoryService
from Services.Files.FilesTools import FilesTools 
import logging


# ═══════════════════════════════════════════════════════════════
# MCPService - Rotas de Info do Sistema e Dashboard
# ═══════════════════════════════════════════════════════════════

# Logger specific to this service: server.services.mcp.mcpservice
logger = logging.getLogger("server.services.mcp.mcpservice")

routerMCP = APIRouter(prefix="/mcp", tags=["MCP"])

class MCPService:
    @routerMCP.post("/initialize")
    def mcp_initialize():
        return {
            "protocolVersion": "0.1",
            "capabilities": {
                "tools": True,
                "resources": True
            },
            "serverInfo": {
                "name": "local-filesystem",
                "version": "0.1"
            }
        }

    @routerMCP.post("/")
    def mcp(payload: dict = None) -> dict:
        """Main MCP entrypoint. Accepts either direct POST body (tool registry request)
        or a JSON-RPC 2.0 envelope coming from the VS Code client.

        If a JSON-RPC envelope is received, dispatch to the appropriate handler
        and return a JSON-RPC response object. Otherwise return the full registry
        (same as the old behavior).
        """

        def jsonrpc_error(req_id, code, message):
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}

        # Detect JSON-RPC envelope
        if isinstance(payload, dict) and payload.get("jsonrpc") == "2.0":
            req_id = payload.get("id")
            method = payload.get("method")
            params = payload.get("params", {}) or {}

            # Map JSON-RPC method names to local handlers
            try:
                if method == "initialize":
                    result = MCPService.mcp_initialize()
                    return {"jsonrpc": "2.0", "id": req_id, "result": result}
                if method in ("tools.list", "list_tools", "tools.list_tools"):
                    result = MCPService.list_tools()
                    return {"jsonrpc": "2.0", "id": req_id, "result": result}
                if method in ("info", "server.info"):
                    result = MCPService.mcp_info()
                    return {"jsonrpc": "2.0", "id": req_id, "result": result}
                if method in ("tools.read_file", "read_file"):
                    # expect params to be an object with path/base
                    if not isinstance(params, dict):
                        return jsonrpc_error(req_id, -32602, "Invalid params, expected object")
                    result = MCPService.mcp_read_file(params)
                    return {"jsonrpc": "2.0", "id": req_id, "result": result}
                if method in ("save_in_IA_mem", "memory.save"):
                    if not isinstance(params, dict):
                        # allow raw string in params
                        params = {"info": params}
                    result = MCPService.save_in_IA_mem(params)
                    return {"jsonrpc": "2.0", "id": req_id, "result": result}

                # save_file requires multipart upload; can't be used via JSON body
                if method in ("save_file",):
                    return jsonrpc_error(req_id, -32601, "Method requires multipart upload; use HTTP multipart POST to /mcp/save_file")

                return jsonrpc_error(req_id, -32601, f"Method not found: {method}")
            except Exception as E:
                return jsonrpc_error(req_id, -32000, str(E))

        # Non-JSON-RPC flow: Build a comprehensive MCP JSON describing tools, resources and language policy
        agent = Agent()
        resources = getattr(agent, "resources", [])

        # resolved bases
        resolved = data.get_resolved_bases()
        bases = {}
        for base_name, base_items in resolved.items():
            bases[base_name] = []
            for item in base_items:
                if item is None:
                    bases[base_name].append(None)
                elif isinstance(item, Path):
                    bases[base_name].append({"type": "path", "value": str(item)})
                elif isinstance(item, Machine):
                    bases[base_name].append({
                        "type": "machine",
                        "id": item.id,
                        "address": item.address,
                        "name": item.name,
                        "interface": item.interface,
                        "vendor": item.vendor,
                        "is_randomized": item.is_randomized,
                    })
                else:
                    bases[base_name].append({"type": "unknown", "value": str(item)})

        language_policy = {
            "default": "pt-BR",
            "client_override_param": "lang",
            "client_override_header": "Accept-Language",
            "allow_english_on_request": True,
            "note_pt": "Por padrão responda em Português (pt-BR). Se o cliente solicitar 'en' via parâmetro 'lang' ou cabeçalho 'Accept-Language', responda em Inglês.",
            "note_en": "Respond in Portuguese (pt-BR) by default. If client requests 'en' via 'lang' parameter or 'Accept-Language' header, reply in English."
        }

        ai_instructions = {
            "use_descriptions_en_for_ai": True,
            "user_visible_default_language": "pt-BR",
            "when_addressing_user": "Prefer Portuguese, switch to English only if requested by client.",
            "use_base_promt_input": True,
            "note_for_base_promt": (
                "Nota: o base_promt (campo usado em `base_promt_input`) é carregado do "
                "banco de dados como o prompt base do agente. Por padrão ele provém do arquivo "
                "template.md (modelo base), mas pode ser sobrescrito no banco ou via API para "
                "customizar o comportamento do agente. Utilize-o como ponto de partida; alterações "
                "podem afetar diretamente as respostas do agente."
            )
        }

        # build a readable prompt combining default instructions + per-tool summary
        tools_items = getattr(agent, "tools", [])
        tools_summary_lines = []
        for t in tools_items:
            name = t.get("name")
            desc = t.get("description_en", "")
            access = t.get("access", {})
            example = t.get("example", "")
            tools_summary_lines.append(f"- {name}: {desc} | access={access} | example={example}")

        tools_infos_promt = Agent.READ_TOOL_PROTOCOL + "\n\nTOOLS SUMMARY:\n" + "\n".join(tools_summary_lines)

        return {
            "tool_registry_version": "1.0",
            "mcp_version": "0.2",
            "resources": resources,
            "agent": {
                "id": agent.id,
                "model": agent.model,
                "permissions": agent.permissions,
                "prompt_preview": getattr(agent, "promt", None),
                "base_promt_input":  agent.promt
            },
            "tools": {
                "items": tools_items,
                "tools_infos_promt": tools_infos_promt
            },
            "bases_path": bases,
            "language_policy": language_policy,
            "ai_instructions": ai_instructions,
        }

    @routerMCP.get("/info")
    def mcp_info():
        json = {
            "name": "quitto-server-filesystem-protocol-mcp",
        }
        # Use resolved bases (machine IDs -> Machine objects) for response
        resolved = data.get_resolved_bases()
        for base_name, base_items in resolved.items():
            json[base_name] = []
            for item in base_items:
                if item is None:
                    json[base_name].append(None)
                elif isinstance(item, Path):
                    json[base_name].append(str(item))
                elif isinstance(item, Machine):
                    json[base_name].append({
                        "id": item.id,
                        "address": item.address,
                        "name": item.name,
                        "interface": item.interface,
                        "vendor": item.vendor,
                        "is_randomized": item.is_randomized,
                    })
                else:
                    json[base_name].append(str(item))

        return [json]
    
    @routerMCP.post("/tools/list")
    def list_tools():
        agent = Agent()
        return getattr(agent, "tools", [])

        
    @routerMCP.post("/tools/read_file")
    def mcp_read_file(payload: dict):
        if not isinstance(payload,dict):
            raise HTTPException(status_code=422,detail="[ERROR] Invalid payload type for read_file: expected dict, got {}".format(type(payload).__name__))
        
        base = payload.get("base") # Base = Path allow to IA use
        path = payload.get("path")
        if not (base and path):
            raise HTTPException(
            status_code=422,
            detail="Missing required parameters: 'base' and/or 'path'. Please provide both to read a file."
            )
        content:dict = FilesTools.read_file_from_base(base,path)
        if "error" in content:
            raise HTTPException(status_code=404,detail="file not found in selected base")
        
        return {"content":content}
    
    @routerMCP.post("/tools/read_file_with_path")
    def mcp_read_file_with_path(payload: dict):
        if not isinstance(payload,dict):
            raise HTTPException(status_code=422,detail="[ERROR] Invalid payload type for read_file: expected dict, got {}".format(type(payload).__name__))
        
        path = payload.get("path")

        content:dict = FilesTools.read_file_with_path(path)
        if "error" in content:
            raise HTTPException(status_code=404,detail="file not found in selected base")
        
        return {"content":content}

    @routerMCP.post("/save_in_IA_mem")
    def save_in_IA_mem(payload: dict):
        """Persist incoming info into agent memory using MemoryService.

        Accepts JSON payload with either `info` or `data` keys. Returns {ok: bool}.
        """
        info = str(payload)
        
        try:
            mem = MemoryService()
            ok = mem.save_in_mem(str(info))
            if not ok:
                logger.error(f"[ERROR] Cant save in DB, ok: {ok}")
            return {"ok": bool(ok)}
        except Exception as E:
            return {"ok": False, "error": str(E)}

    @routerMCP.post("/save_file")
    async def save_file(name_path: str, file: UploadFile = File(...)):
        base_list = data.GLOBAL_PATHS.get(name_path)
        if not base_list:
            raise HTTPException(status_code=404, detail=f"base path not found for: {name_path}")

        base_entry = base_list[0]
        if isinstance(base_entry, Path):
            base_path = base_entry
        else:
            try:
                base_path = Path(str(base_entry))
            except Exception:
                raise HTTPException(status_code=400, detail="invalid base entry")

        try:
            contents = await file.read()
            if not contents:
                raise HTTPException(status_code=400, detail="empty upload")

            final_path = base_path / file.filename
            final_path.parent.mkdir(parents=True, exist_ok=True)

            with open(final_path, "wb") as f:
                f.write(contents)

            return {"saved": str(final_path)}
        except HTTPException:
            raise
        except Exception as E:
            raise HTTPException(status_code=500, detail=str(E))

    @routerMCP.get("/seach_file")
    def search_file(file_name:str, base_path_code:str = None):
        """Search for `file_name` across registered bases or inside a specific base.

        - If `base_path_code` is provided, search only that base and return the first match (no guessing).
        - If `base_path_code` is omitted, search all keys in `data.GLOBAL_PATHS` and return all matches.
        """
        results = []

        # Decide which bases to search
        if base_path_code:
            keys = [base_path_code]
        else:
            keys = list(data.GLOBAL_PATHS.keys())

        for key in keys:
            # skip unknown base keys
            if key not in data.GLOBAL_PATHS:
                continue
            try:
                found = FilesTools.search_file_in_base(key, file_name)
            except Exception as e:
                logger.debug(f"Error searching base {key}: {e}")
                found = None

            if found:
                results.append({"base": key, "path": str(found)})
                # if user requested a specific base, return immediately (no further attempts)
                if base_path_code:
                    return {"count": len(results), "matches": results}

        return {"count": len(results), "matches": results}
            