from typing import Optional, Dict, List
from Services.MCP.MemoryService import MemoryService
from pathlib import Path
import os
import copy


class Agent:
    """
    Agent model.

    Fields:
      - `id`: PK for external DB/server
      - `model`: model name
      - `permissions`: per-role permission mapping (defaults to class PERMISSIONS)
      - `promt`: prompt template; if None use template from `data.BASE[]`
    """

    PERMISSIONS: Dict[str, List[str]] = {
        "planner": ["list"],
        "executor": ["read_file"],
        "memory": ["read_file", "write_file"]
    }

# Default internal prompt template that tells the AI how to read the tool registry.
# Written primarily in English for model understanding, with a short Portuguese
# instruction for user-facing answers (pt-BR by default).
    READ_TOOL_PROTOCOL = """
        INSTRUCTIONS FOR TOOL USAGE (for the assistant):

        You are given a tool registry describing available tools. Treat this registry
        as a declaration of capabilities only — DO NOT execute tools yourself.

        When you need to perform an action, follow this procedure:
        1) READ the registry and pick the single most appropriate tool by name.
        2) BUILD a JSON object with two keys: `tool` (string) and `arguments` (object).
            - `tool`: the exact tool `name` from the registry.
            - `arguments`: a mapping of parameter names to values required by the tool.
        3) DO NOT attempt to access files, network, or system resources directly.
            Only request the orchestrator/runtime to call the tool using the JSON you
            produce.
        4) If the tool may have side effects, include a short justification in
            `metadata.reason` explaining why the tool must be run.

        Return format example (only the JSON object, no extra text):
        {
        "tool": "read_file",
        "arguments": { "path": "ai/log.txt" },
        "metadata": { "reason": "Need log contents to answer why X failed" }
        }

        Notes for language:
        - Answer user-visible content in Portuguese (pt-BR) by default.
        - If the client requests English (lang=en or Accept-Language header), reply in English.
    """

    Agent_TOOLS = [
    {
        "name": "read_file",
        "description_en": "Read the content of a file. Supports: (1) base-relative reads (\n            use a registered base key + relative path), (2) absolute filesystem paths, and (3) a fallback filename search across configured bases.",
        "access": {"endpoint": "/mcp/tools/read_file", "method": "POST", "content_type": "application/json", "auth": "session"},
        "run_instructions_en": "POST JSON to /mcp/tools/read_file with {\"path\": \"<base>/<relative_path>\"} to read a file inside a registered base, or {\"path\": \"/abs/path/to/file\"} to read by absolute path. If you supply only a filename (e.g. \"README.md\"), the service will search configured bases and return the first match.",
        "version": "1.0",
        "parameters": [
            {"name": "path", "type": "string", "description_en": "Either: '<base>/<relative_path>' to read from a base, '/absolute/path' to read directly, or a bare filename to trigger a search across bases."}
        ],
        "returns": {"type": "object", "schema": {"content": "string"}},
        "required_roles": ["executor", "memory"],
        "side_effect": False,
        "safe": True,
        "example": "POST /mcp/tools/read_file {\"path\": \"ai/log.txt\"}  OR POST /mcp/tools/read_file {\"path\": \"/var/log/syslog\"}"
    },
    {
        "name": "search_files",
        "description_en": "Perform an advanced search for files inside a registered base. Supports filtering by name, extension, category, size, and text content (for small text files).",
        "access": {"endpoint": "/files/search/{base}", "method": "GET", "content_type": "application/json", "auth": "session"},
        "run_instructions_en": "Call GET /files/search/{base}?query=<name>&ext=.md&category=doc&min_size=0&max_size=10000&sort=name&limit=50 to search a specific base. Use the 'content' query parameter to search inside text files (<1MB).",
        "version": "1.0",
        "parameters": [
            {"name": "base", "type": "string", "description_en": "Registered base key (e.g. 'projects')"},
            {"name": "query", "type": "string", "description_en": "Substring to match in filenames"},
            {"name": "ext", "type": "string", "description_en": "Filter by extension (e.g. .py, .md)"},
            {"name": "category", "type": "string", "description_en": "High-level category (code, doc, img, etc)"},
            {"name": "min_size", "type": "int", "description_en": "Minimum size in bytes"},
            {"name": "max_size", "type": "int", "description_en": "Maximum size in bytes"},
            {"name": "sort", "type": "string", "description_en": "Sort by: name, size, date"},
            {"name": "limit", "type": "int", "description_en": "Max results to return"},
            {"name": "content", "type": "string", "description_en": "Text to search inside files (only for small text files)"}
        ],
        "returns": {"type": "object", "schema": {"matches": "array of file metadata"}},
        "required_roles": ["executor"],
        "side_effect": False,
        "safe": True,
        "example": "GET /files/search/projects?query=README&ext=.md"
    },
    {
        "name": "read_path",
        "description_en": "Read a file by absolute filesystem path. Use when you need to read arbitrary paths allowed by the server configuration.",
        "access": {"endpoint": "/files/read-path", "method": "GET", "content_type": "application/json", "auth": "session"},
        "run_instructions_en": "GET /files/read-path?path=/absolute/path/to/file. Returns file content and metadata. This bypasses base resolution and reads the provided absolute path if allowed.",
        "version": "1.0",
        "parameters": [
            {"name": "path", "type": "string", "description_en": "Absolute filesystem path to read (e.g. /etc/hosts)"}
        ],
        "returns": {"type": "object", "schema": {"content": "string", "path": "string", "size_bytes": "int"}},
        "required_roles": ["executor"],
        "side_effect": False,
        "safe": False,
        "example": "GET /files/read-path?path=/var/log/syslog"
    },
    {
        "name": "save_file",
        "description_en": "Save an uploaded file into a specified base folder.",
        "access": {"endpoint": "/mcp/save_file", "method": "POST (multipart/form-data)", "content_type": "multipart/form-data", "auth": "session"},
        "run_instructions_en": "POST multipart/form-data to /mcp/save_file with fields 'name_path' (base key) and 'file' (binary). Returns {\"saved\": \"/abs/path\"}.",
        "version": "1.0",
        "parameters": [
            {"name": "name_path", "type": "string", "description_en": "Base key where the file will be saved (e.g. 'projects')"},
            {"name": "file", "type": "file", "description_en": "Binary file upload"}
        ],
        "returns": {"type": "object", "schema": {"saved": "string (absolute path)"}},
        "required_roles": ["memory"],
        "side_effect": True,
        "safe": False,
        "example": "POST /mcp/save_file (multipart form)"
    },
    {
        "name": "list_bases",
        "description_en": "List configured base roots (paths) available to the MCP and their status.",
        "access": {"endpoint": "/mcp/info", "method": "GET", "content_type": "application/json", "auth": "session"},
        "run_instructions_en": "GET /mcp/info to retrieve resolved bases and their types. Alternatively call GET /mcp for registry + bases.",
        "parameters": [],
        "returns": {"type": "object", "schema": {"bases": "object"}},
        "required_roles": ["planner", "executor", "memory"],
        "example": "GET /mcp/info or POST /mcp to receive bases listing"
    },
    {
        "name": "save_in_IA_mem",
        "description_en": "Persist a JSON payload or text into the agent memory store (DB).",
        "access": {"endpoint": "/mcp/save_in_IA_mem", "method": "POST", "content_type": "application/json", "auth": "session"},
        "run_instructions_en": "POST JSON to /mcp/save_in_IA_mem with {\"info\": \"...\"}. Returns {\"ok\": true} on success.",
        "version": "1.0",
        "parameters": [{"name": "info", "type": "string", "description_en": "Text or JSON serialised string to save"}],
        "returns": {"type": "object", "schema": {"ok": "boolean"}},
        "required_roles": ["memory"],
        "side_effect": True,
        "safe": True,
        "example": "POST /mcp/save_in_IA_mem {\"info\": \"some prompt text\"}"
    },
    {
        "name": "list_machines",
        "description_en": "Return machines registered in the MCP database with their metadata.",
        "access": {"endpoint": "/machine/all", "method": "GET", "content_type": "application/json", "auth": "session"},
        "run_instructions_en": "GET /machine/all. Returns an array of machine objects with id, address, name, interface, vendor.",
        "parameters": [],
        "returns": {"type": "array", "schema": {"id": "int", "address": "string", "name": "string"}},
        "required_roles": ["planner", "executor"],
        "example": "GET /machine/all"
    },
    {
        "name": "wake_on_lan",
        "description_en": "Send a Wake-on-LAN magic packet to a registered machine by its address.",
        "access": {"endpoint": "/machine/wol", "method": "POST", "content_type": "application/json", "auth": "session"},
        "run_instructions_en": "POST JSON to /machine/wol or equivalent endpoint with {\"id\": <machine_id>} to trigger WOL. Returns {\"ok\": true/false}.",
        "version": "1.0",
        "parameters": [{"name": "machine_id", "type": "int", "description_en": "ID of the machine to wake"}],
        "returns": {"type": "object", "schema": {"ok": "boolean"}},
        "required_roles": ["executor"],
        "side_effect": True,
        "safe": False,
        "example": "POST /machine/wol {\"id\": 1}"
    },
    {
        "name": "create_project",
        "description_en": "Create a new project skeleton using the server's ProjectSetup service.",
        "access": {"endpoint": "/create_project", "method": "GET", "content_type": "querystring", "auth": "session"},
        "run_instructions_en": "Call GET /create_project?name=MyApp&language=py&path=/optional/path. Returns stdout/stderr/returncode in JSON.",
        "version": "1.0",
        "parameters": [
            {"name": "name", "type": "string"},
            {"name": "language", "type": "string"},
            {"name": "path", "type": "string", "description_en": "Optional root path"}
        ],
        "returns": {"type": "object", "schema": {"stdout": "string", "stderr": "string", "returncode": "int"}},
        "required_roles": ["planner"],
        "side_effect": True,
        "safe": False,
        "example": "GET /create_project?name=MyApp&language=py&path=/path"
    },
    {
        "name": "get_calendar_events",
        "description_en": "Fetch calendar events from the configured calendar integration.",
        "access": {"endpoint": "/calender/events", "method": "GET", "content_type": "application/json", "auth": "session"},
        "run_instructions_en": "GET /calender/events. Returns array of events in JSON. Ensure calendar integration is installed on server.",
        "parameters": [],
        "returns": {"type": "array", "schema": {"events": "array"}},
        "required_roles": ["planner"],
        "example": "GET /calender/events"
    },
    {
        "name": "health_check",
        "description_en": "Basic health/status endpoint for the MCP server.",
        "access": {"endpoint": "/health", "method": "GET", "content_type": "application/json", "auth": "none"},
        "run_instructions_en": "GET /health. Public health status; no auth required.",
        "version": "1.0",
        "parameters": [],
        "returns": {"type": "object", "schema": {"status": "string", "timestamp": "string"}},
        "required_roles": [],
        "side_effect": False,
        "safe": True,
        "example": "GET /health"
    },
    {
        "name": "read_file_with_path",
        "description_en": "Read a file by absolute filesystem path via the MCP read_file_with_path endpoint.",
        "access": {"endpoint": "/mcp/tools/read_file_with_path", "method": "POST", "content_type": "application/json", "auth": "session"},
        "run_instructions_en": "POST JSON to /mcp/tools/read_file_with_path with {\"path\": \"/absolute/path/to/file\"} to read a file by absolute path.",
        "version": "1.0",
        "parameters": [
            {"name": "path", "type": "string", "description_en": "Absolute filesystem path to read (e.g. /etc/hosts)"}
        ],
        "returns": {"type": "object", "schema": {"content": "string", "path": "string", "size_bytes": "int"}},
        "required_roles": ["executor"],
        "side_effect": False,
        "safe": False,
        "example": "POST /mcp/tools/read_file_with_path {\"path\":\"/var/log/syslog\"}"
    },
    {
        "name": "search_bases",
        "description_en": "Search for a filename across registered bases or inside a specific base using the MCP search endpoint.",
        "access": {"endpoint": "/mcp/seach_file", "method": "GET", "content_type": "application/json", "auth": "session"},
        "run_instructions_en": "GET /mcp/seach_file?file_name=NAME&base_path_code=CODE to search for NAME across bases or within a specific base.",
        "version": "1.0",
        "parameters": [
            {"name": "file_name", "type": "string", "description_en": "Filename to search for (e.g. README.md)"},
            {"name": "base_path_code", "type": "string", "description_en": "Optional base key to restrict the search"}
        ],
        "returns": {"type": "object", "schema": {"matches": "array of {base, path}"}},
        "required_roles": ["executor"],
        "side_effect": False,
        "safe": True,
        "example": "GET /mcp/seach_file?file_name=README.md"
    },
    {
        "name": "server_info",
        "description_en": "Return detailed server info and resolved bases.",
        "access": {"endpoint": "/info", "method": "GET", "content_type": "application/json", "auth": "none"},
        "run_instructions_en": "GET /info to receive server metadata and optionally bases (may require auth in some deployments).",
        "version": "1.0",
        "parameters": [],
        "returns": {"type": "array", "schema": {}},
        "required_roles": [],
        "side_effect": False,
        "safe": True,
        "example": "GET /info"
    }
]

    # make available as class attribute
    TOOLS = Agent_TOOLS

    # Default resources registry
    RESOURCES = [
        {
            "name": "default_behavior_template",
            "type": "text/markdown",
            "description_en": "Template that defines how the AI should behave within this MCP system.",
            "content": None
        }
    ]
    
    def __init__(
        self,
        id: Optional[int] = None,
        model: str = "model_name",
        promt: Optional[str] = None,
        permissions: Optional[Dict[str, List[str]]] = None,
    ):
        self.id = id
        self.model = model
        repo = MemoryService()
        if promt is None:
            # try DB prompt
            db_prompt = repo.get_promt(id)
            if db_prompt:
                self.promt = db_prompt
            else:
                # try default template file (may be a Path)
                base_template = repo.get_base_templete()
                if isinstance(base_template, Path) and base_template.exists():
                    try:
                        with open(base_template, "r", encoding="utf-8") as f:
                            self.promt = f.read()
                    except Exception:
                        self.promt = Agent.READ_TOOL_PROTOCOL
                elif isinstance(base_template, str):
                    self.promt = base_template
                else:
                    self.promt = Agent.READ_TOOL_PROTOCOL
        else:
            self.promt = promt
                
        # allow instance-level override of permissions
        self.permissions = permissions.copy() if permissions is not None else Agent.PERMISSIONS.copy()

        # attach tools and resources to the agent instance (can be overridden)
        # Default catalog and resources are defined as class variables below.
        self.tools = copy.deepcopy(getattr(Agent, "TOOLS", {}))
        # resources: inject agent prompt into the default_behavior_template content
        self.resources = copy.deepcopy(getattr(Agent, "RESOURCES", []))
        for r in self.resources:
            if r.get("name") == "default_behavior_template":
                r["content"] = getattr(self, "promt", None)
