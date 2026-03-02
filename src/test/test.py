import sys
from pathlib import Path
import argparse

# make project root importable so absolute imports like `from DB.DBConnection` work
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from data import data
try:
    from DB.DBConnection import DBConnection
except Exception:
    DBConnection = None

from models.Machine import Machine


def quick_setup():
    project_root = Path(__file__).parents[1].resolve()
    data.GLOBAL_PATHS = {
        "projects": [project_root],
        "home": [Path.home()]
    }
    data.MACHINES = [
        Machine(address="AA:BB:CC:DD:EE:FF", id=1, name="local-test", interface="lo", vendor="Generic", is_randomized=False, url_connect=None)
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Quick test mode: do not connect to DB")
    args = parser.parse_args()

    if args.quick:
        quick_setup()
    else:
        try:
            data.load_apps()
        except Exception as e:
            print("Warning: load_apps failed:", e)
        try:
            data.load_machines()
        except Exception as e:
            print("Warning: load_machines failed:", e)

    # If no machines were loaded (or DB env missing), fall back to quick setup
    if not data.MACHINES:
        print("No machines found — falling back to quick test setup.")
        quick_setup()
        args.quick = True

    print("GLOBAL_PATHS:")
    print(data.GLOBAL_PATHS)

    print("MACHINES:")
    print(data.MACHINES)
    

    # optional: test DBConnection if available and not quick
    if not args.quick and DBConnection:
        try:
            db = DBConnection()
            print("DB pool initialized")
            db.close_all()
        except Exception as e:
            print("DBConnection failed:", e)

    print("request tests")
    # HTTP POST helper: try requests, fallback to urllib
    try:
        import requests as _requests

        def post_json(url, payload, timeout=10):
            resp = _requests.post(url, json=payload, timeout=timeout)
            return resp.status_code, resp.json()
    except Exception:
        import urllib.request
        import json as _json

        def post_json(url, payload, timeout=10):
            data_bytes = _json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data_bytes, method="POST")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_body = resp.read().decode("utf-8")
                try:
                    parsed = _json.loads(resp_body)
                except Exception:
                    parsed = resp_body
                return resp.getcode(), parsed

    url = f"http://100.114.146.77:8000/read_path"
    status, body = post_json(url, {"path": "~/.profile"}, timeout=10)
    print(status)
    print(body)


if __name__ == "__main__":
    main()