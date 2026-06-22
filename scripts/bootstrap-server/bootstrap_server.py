#!/usr/bin/env python3
"""
FoodAssistant Bootstrap Server
==============================
Minimal stdlib-only HTTP server that serves the web installer UI and
drives the firstboot.sh provisioner with live SSE log streaming.

Runs on port 80 as root (installed by install.sh Phase 1).
Auto-disables its own systemd unit when provisioning succeeds.
"""
import http.server
import json
import os
import subprocess
import sys
import threading
import time
import pathlib
import shutil
import queue
import socket
import urllib.parse

PORT = int(os.environ.get("BOOTSTRAP_PORT", "80"))
REPO_DIR = os.environ.get("REPO_DIR", "/opt/foodassistant-src")
LOG_QUEUE: "queue.Queue[str | None]" = queue.Queue()
INSTALL_LOCK = threading.Lock()
INSTALL_RUNNING = False
INSTALL_DONE = False
INSTALL_SUCCESS = False

UI_DIR = pathlib.Path(__file__).parent / "ui"
FIRSTBOOT = pathlib.Path(REPO_DIR) / "scripts" / "image-build" / "firstboot.sh"


# ---------------------------------------------------------------------------
# Hardware detection helpers (mirror install.sh logic in Python)
# ---------------------------------------------------------------------------
def _is_raspberry_pi() -> bool:
    for p in ("/proc/device-tree/model", "/sys/firmware/devicetree/base/model"):
        try:
            return "raspberry pi" in pathlib.Path(p).read_bytes().decode("utf-8", errors="ignore").lower()
        except OSError:
            pass
    return False


def _board_model() -> str:
    for p in ("/proc/device-tree/model", "/sys/firmware/devicetree/base/model"):
        try:
            return pathlib.Path(p).read_bytes().decode("utf-8", errors="ignore").rstrip("\x00").strip()
        except OSError:
            pass
    return "Unknown"


def _has_display() -> bool:
    return (
        pathlib.Path("/dev/dri/card0").exists()
        or bool(os.environ.get("WAYLAND_DISPLAY"))
        or bool(os.environ.get("DISPLAY"))
    )


def _has_streamdeck() -> bool:
    try:
        out = subprocess.check_output(["lsusb"], stderr=subprocess.DEVNULL, text=True)
        if "0fd9:" in out.lower():
            return True
    except Exception:
        pass
    # fallback via sysfs
    try:
        for p in pathlib.Path("/sys/bus/usb/devices").glob("*/idVendor"):
            if p.read_text().strip() == "0fd9":
                return True
    except Exception:
        pass
    return False


def _device_hostname() -> str:
    return socket.gethostname()


# ---------------------------------------------------------------------------
# Provisioning
# ---------------------------------------------------------------------------
def _run_install(config: dict) -> None:
    global INSTALL_RUNNING, INSTALL_DONE, INSTALL_SUCCESS

    env = os.environ.copy()
    env.update({
        "DEPLOYMENT_MODE": config.get("deployment_mode", "pi_hosted"),
        "REMOTE_SERVER_URL": config.get("remote_server_url", ""),
        "ENABLE_KIOSK": "true" if config.get("enable_kiosk") else "false",
        "ENABLE_STREAMDECK": "true" if config.get("enable_streamdeck") else "false",
        "ENABLE_MEALIE": "false",
        "ENABLE_OLLAMA": "false",
        "REPO_DIR": REPO_DIR,
    })

    LOG_QUEUE.put("==> Starting FoodAssistant provisioner...\n")

    try:
        proc = subprocess.Popen(
            ["bash", str(FIRSTBOOT)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            text=True,
            bufsize=1,
        )
        for line in proc.stdout:
            LOG_QUEUE.put(line)
        proc.wait()
        if proc.returncode == 0:
            LOG_QUEUE.put("\n✅ Installation complete! Redirecting...\n")
            INSTALL_SUCCESS = True
            # Signal SSE clients that we're done BEFORE shutting down, so the
            # browser can advance to Step 4. Schedule the actual shutdown 4s
            # later so all connected clients have time to drain the queue.
            def _deferred_shutdown():
                time.sleep(4)
                try:
                    subprocess.run(
                        ["systemctl", "disable", "--now", "foodassistant-bootstrap.service"],
                        check=False,
                    )
                except Exception:
                    pass
                # Hard exit in case systemctl didn't kill us
                os._exit(0)
            threading.Thread(target=_deferred_shutdown, daemon=True).start()
        else:
            LOG_QUEUE.put(f"\n❌ Provisioner exited with code {proc.returncode}\n")
    except Exception as exc:
        LOG_QUEUE.put(f"\n❌ Error running provisioner: {exc}\n")
    finally:
        LOG_QUEUE.put(None)  # sentinel — SSE stream ends
        INSTALL_RUNNING = False
        INSTALL_DONE = True


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------
class BootstrapHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # suppress default access log noise

    # ---- routing ----

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/" or path == "/index.html":
            self._serve_file(UI_DIR / "index.html", "text/html; charset=utf-8")
        elif path.startswith("/assets/"):
            rel = path.lstrip("/")
            self._serve_file(UI_DIR / rel, self._mime(rel))
        elif path == "/api/detect":
            self._json({
                "is_pi": _is_raspberry_pi(),
                "board_model": _board_model(),
                "has_display": _has_display(),
                "has_streamdeck": _has_streamdeck(),
                "hostname": _device_hostname(),
            })
        elif path == "/api/status":
            self._json({
                "running": INSTALL_RUNNING,
                "done": INSTALL_DONE,
                "success": INSTALL_SUCCESS,
            })
        elif path == "/api/log":
            self._stream_log()
        else:
            self._not_found()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/api/install":
            self._handle_install()
        else:
            self._not_found()

    # ---- handlers ----

    def _handle_install(self):
        global INSTALL_RUNNING, INSTALL_DONE, INSTALL_SUCCESS, LOG_QUEUE

        if not INSTALL_LOCK.acquire(blocking=False):
            self._json({"ok": False, "error": "Install already running"}, 409)
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            config = json.loads(body) if body else {}
        except json.JSONDecodeError:
            config = {}

        # Reset state for a fresh run
        INSTALL_RUNNING = True
        INSTALL_DONE = False
        INSTALL_SUCCESS = False
        LOG_QUEUE = queue.Queue()

        t = threading.Thread(target=_run_install, args=(config,), daemon=True)
        t.start()
        INSTALL_LOCK.release()

        self._json({"ok": True})

    def _stream_log(self):
        """Server-Sent Events endpoint — streams log lines until install ends."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        try:
            while True:
                try:
                    line = LOG_QUEUE.get(timeout=30)
                except queue.Empty:
                    # heartbeat to keep connection alive
                    self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
                    continue

                if line is None:
                    # sentinel — provisioning ended
                    status = "success" if INSTALL_SUCCESS else "error"
                    self.wfile.write(f"event: done\ndata: {status}\n\n".encode())
                    self.wfile.flush()
                    break

                # Escape newlines inside the data field
                escaped = line.replace("\n", "\ndata: ")
                self.wfile.write(f"data: {escaped}\n\n".encode())
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass

    # ---- helpers ----

    def _serve_file(self, path: pathlib.Path, content_type: str):
        if not path.exists():
            self._not_found()
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, data: dict, code: int = 200):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _not_found(self):
        self.send_response(404)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Not found")

    @staticmethod
    def _mime(path: str) -> str:
        ext = pathlib.Path(path).suffix.lower()
        return {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css",
            ".js": "application/javascript",
            ".json": "application/json",
            ".svg": "image/svg+xml",
            ".png": "image/png",
        }.get(ext, "application/octet-stream")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    server = http.server.ThreadingHTTPServer(("", PORT), BootstrapHandler)
    print(f"[bootstrap] Listening on port {PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
