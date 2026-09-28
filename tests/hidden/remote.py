import functools, http.server, os, threading
from pathlib import Path
import pytest

@pytest.fixture
def served(tmp_path_factory):
    servers = []
    def serve(files: dict[str, str]) -> str:
        root = tmp_path_factory.mktemp("www")
        for rel, text in files.items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(text)
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
        host = os.environ.get("BAKEOFF_HTTP_HOST", "127.0.0.1")
        srv = http.server.ThreadingHTTPServer((host, 0), handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        servers.append(srv)
        return f"http://{host}:{srv.server_address[1]}"
    yield serve
    for s in servers:
        s.shutdown()
