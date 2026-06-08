"""Docker sandbox with Jupyter Kernel Gateway for isolated code execution.

Provides ContainerManager for Docker lifecycle and KernelClient for executing Python/R code via the Jupyter wire
protocol.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field

import docker
import requests
import websocket

from config import (
    DATA_DIR,
    DOCKER_CONTAINER_NAME,
    DOCKER_IMAGE_NAME,
    KERNEL_GATEWAY_HOST,
    KERNEL_GATEWAY_PORT,
    KERNEL_GATEWAY_URL,
    MAX_OUTPUT_CHARS,
    ROOT,
)
from agents.agent_utils import truncate_output

EXECUTION_TIMEOUT = 300  # 5 minutes

IMAGE_MIME_TYPES = {"image/png", "image/jpeg"}


class KernelUnavailableError(RuntimeError):
    """Raised when no Jupyter Kernel Gateway is reachable at the configured URL.

    Surfaces the two valid backends (Docker sandbox vs. a local gateway) so the
    operator knows how to recover, instead of leaking a raw ``ConnectionError``.
    """

    def __init__(self, url: str):
        super().__init__(
            f"Could not reach a Jupyter Kernel Gateway at {url}. No code "
            f"backend is running. Either enable the Docker sandbox from the "
            f"Settings page (starts a container automatically), or start a "
            f"local Jupyter Kernel Gateway listening on that address."
        )


@dataclass
class ExecutionResult:
    """Structured result from a kernel execution, carrying text and images."""

    text: str
    images: list[str] = field(default_factory=list)  # base64-encoded data URIs


class ContainerManager:
    """Manages the Docker container running Jupyter Kernel Gateway."""

    def __init__(self):
        """Initialise the Docker client and container reference."""
        self._client = docker.from_env()
        self._container = None

    def ensure_image(self) -> None:
        """Build the Docker image if it doesn't exist."""
        try:
            self._client.images.get(DOCKER_IMAGE_NAME)
            logging.info(f"Docker image '{DOCKER_IMAGE_NAME}' already exists.")
        except docker.errors.ImageNotFound:
            logging.info(f"Building Docker image '{DOCKER_IMAGE_NAME}'...")
            dockerfile_dir = str(ROOT / "docker")
            self._client.images.build(
                path=dockerfile_dir,
                tag=DOCKER_IMAGE_NAME,
                rm=True,
            )
            logging.info(f"Docker image '{DOCKER_IMAGE_NAME}' built successfully.")

    def ensure_running(self) -> None:
        """Start the sandbox container if not already running."""
        self.ensure_image()

        try:
            container = self._client.containers.get(DOCKER_CONTAINER_NAME)
            if container.status == "running":
                logging.info(f"Container '{DOCKER_CONTAINER_NAME}' is already running.")
                self._container = container
                self._wait_for_healthy()
                return
            logging.info(f"Starting stopped container '{DOCKER_CONTAINER_NAME}'...")
            container.start()
            self._container = container
        except docker.errors.NotFound:
            logging.info(f"Creating container '{DOCKER_CONTAINER_NAME}'...")
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            self._container = self._client.containers.run(
                image=DOCKER_IMAGE_NAME,
                name=DOCKER_CONTAINER_NAME,
                detach=True,
                ports={"8888/tcp": (KERNEL_GATEWAY_HOST, KERNEL_GATEWAY_PORT)},
                volumes={
                    "tissueagent-pyenv": {"bind": "/opt/venv", "mode": "rw"},
                    "tissueagent-rlibs": {"bind": "/opt/R/library", "mode": "rw"},
                    str(DATA_DIR.resolve()): {
                        "bind": "/workspace",
                        "mode": "rw",
                    },
                },
                working_dir="/workspace",
                cap_drop=["ALL"],
                security_opt=["no-new-privileges:true"],
            )

        self._wait_for_healthy()

    def _wait_for_healthy(self, timeout: float = 30) -> None:
        """Poll the Kernel Gateway until it responds."""
        deadline = time.monotonic() + timeout
        url = f"{KERNEL_GATEWAY_URL}/api/kernelspecs"
        while time.monotonic() < deadline:
            try:
                resp = requests.get(url, timeout=2)
                if resp.status_code == 200:
                    logging.info("Kernel Gateway is healthy.")
                    return
            except requests.ConnectionError:
                pass
            time.sleep(0.5)
        raise TimeoutError(
            f"Kernel Gateway did not become healthy within {timeout}s"
        )

    def stop(self) -> None:
        """Stop the container (preserves state for next startup)."""
        if self._container is None:
            try:
                self._container = self._client.containers.get(DOCKER_CONTAINER_NAME)
            except docker.errors.NotFound:
                return
        try:
            self._container.stop(timeout=10)
            logging.info(f"Container '{DOCKER_CONTAINER_NAME}' stopped.")
        except Exception as e:
            logging.warning(f"Error stopping container: {e}")


# ---------------------------------------------------------------------------
# Jupyter wire protocol helpers
# ---------------------------------------------------------------------------

def _make_execute_request(code: str) -> dict:
    """Build a Jupyter execute_request message."""
    return {
        "header": {
            "msg_id": str(uuid.uuid4()),
            "username": "agent",
            "session": str(uuid.uuid4()),
            "msg_type": "execute_request",
            "version": "5.3",
        },
        "parent_header": {},
        "metadata": {},
        "content": {
            "code": code,
            "silent": False,
            "store_history": True,
            "user_expressions": {},
            "allow_stdin": False,
            "stop_on_error": True,
        },
        "buffers": [],
        "channel": "shell",
    }


class KernelClient:
    """Executes code on Jupyter kernels via the Kernel Gateway REST/WS API."""

    KERNEL_NAMES = {"python": "python3", "r": "ir"}

    def __init__(self, base_url: str = KERNEL_GATEWAY_URL):
        """Initialise the client with the Kernel Gateway base URL."""
        self._base_url = base_url
        self._ws_base = base_url.replace("http://", "ws://").replace(
            "https://", "wss://"
        )
        self._kernels: dict[str, str] = {}  # language -> kernel_id
        self._seeded: set[str] = set()
        # Working directory the next kernel will chdir into when seeded.
        # ``set_workspace()`` updates this; lazy chdir keeps a missing
        # workspace from breaking startup.
        self._workspace: Path | None = None

    def set_workspace(self, path: Path) -> None:
        """Point future kernel executions at *path* as their working dir.

        Implementation note: any kernels already alive are shut down so
        the next ``execute()`` starts fresh kernels that chdir into the
        new workspace as part of seeding. This is cheap (a few hundred
        ms) and avoids the alternative of injecting chdir into every
        execute call, which would silently fail if the user pasted a
        ``cd`` of their own.
        """
        previous = self._workspace
        self._workspace = Path(path)
        if previous != self._workspace and self._kernels:
            self.shutdown_kernels()

    def execute(self, code: str, language: str = "python") -> ExecutionResult:
        """Execute code on a kernel and return text output and any images.

        When no kernel backend is reachable, returns an ``ExecutionResult``
        carrying an actionable ``[ERROR]`` message rather than raising — the
        agent can then report the problem to the user instead of the run
        crashing with a bare ``ConnectionError`` traceback.
        """
        try:
            kernel_id = self._get_or_start_kernel(language)
        except KernelUnavailableError as e:
            logging.error(str(e))
            return ExecutionResult(text=f"[ERROR] {e}")
        ws_url = f"{self._ws_base}/api/kernels/{kernel_id}/channels"

        ws = websocket.create_connection(ws_url)
        try:
            msg = _make_execute_request(code)
            msg_id = msg["header"]["msg_id"]
            ws.send(json.dumps(msg))

            output_parts: list[str] = []
            images: list[str] = []
            deadline = time.monotonic() + EXECUTION_TIMEOUT

            while time.monotonic() < deadline:
                ws.settimeout(max(0.1, deadline - time.monotonic()))
                try:
                    raw = ws.recv()
                except websocket.WebSocketTimeoutException:
                    break
                response = json.loads(raw)

                # Only process messages that are responses to our request
                parent_msg_id = response.get("parent_header", {}).get("msg_id")
                if parent_msg_id != msg_id:
                    continue

                msg_type = response.get("msg_type") or response.get("header", {}).get(
                    "msg_type", ""
                )

                if msg_type == "stream":
                    output_parts.append(response["content"]["text"])
                elif msg_type in ("execute_result", "display_data"):
                    data = response["content"].get("data", {})
                    # Capture images first (a single message can have both)
                    for mime in IMAGE_MIME_TYPES:
                        if mime in data:
                            b64 = data[mime]
                            images.append(f"data:{mime};base64,{b64}")
                    if "text/plain" in data:
                        output_parts.append(data["text/plain"])
                    elif "text/html" in data:
                        output_parts.append(data["text/html"])
                elif msg_type == "error":
                    tb = response["content"].get("traceback", [])
                    output_parts.append("\n".join(tb))
                elif msg_type == "status":
                    if response["content"].get("execution_state") == "idle":
                        break
            else:
                output_parts.append(
                    f"\n[ERROR] Execution timed out after {EXECUTION_TIMEOUT}s."
                )
        finally:
            ws.close()

        text = truncate_output("".join(output_parts), MAX_OUTPUT_CHARS)
        return ExecutionResult(text=text, images=images)

    def _get_or_start_kernel(self, language: str) -> str:
        """Return an existing kernel id or start a new one."""
        if language in self._kernels:
            return self._kernels[language]

        kernel_name = self.KERNEL_NAMES.get(language)
        if kernel_name is None:
            raise ValueError(f"Unsupported language: {language}")

        try:
            resp = requests.post(
                f"{self._base_url}/api/kernels",
                json={"name": kernel_name},
                timeout=30,
            )
        except requests.ConnectionError as e:
            raise KernelUnavailableError(self._base_url) from e
        resp.raise_for_status()
        kernel_id = resp.json()["id"]
        self._kernels[language] = kernel_id
        logging.info(f"Started {language} kernel: {kernel_id}")

        return kernel_id

    def _seed_kernel(self, language: str) -> None:
        """Chdir a freshly-started kernel into the active project workspace.

        Idempotent per (kernel) — once a kernel has been seeded, we
        leave it alone. ``set_workspace`` triggers a kernel shutdown
        when the workspace path actually changes, so the next call
        through here picks up the new directory.
        """
        if language in self._seeded:
            return
        self._seeded.add(language)

        workspace = self._workspace
        if workspace is None:
            return

        workspace_str = str(workspace.resolve()).replace("\\", "/")
        if language == "python":
            seed = (
                "import os\n"
                f"os.makedirs({workspace_str!r}, exist_ok=True)\n"
                f"os.chdir({workspace_str!r})\n"
            )
        elif language == "r":
            seed = (
                f'dir.create("{workspace_str}", recursive = TRUE, showWarnings = FALSE)\n'
                f'setwd("{workspace_str}")\n'
            )
        else:
            return

        try:
            self.execute(seed, language=language)
        except Exception as e:
            logging.warning(f"Failed to seed {language} kernel cwd: {e}")

    def shutdown_kernels(self) -> None:
        """Delete all active kernels (for cleanup between agent runs)."""
        for language, kernel_id in list(self._kernels.items()):
            try:
                requests.delete(
                    f"{self._base_url}/api/kernels/{kernel_id}", timeout=10
                )
                logging.info(f"Shut down {language} kernel: {kernel_id}")
            except Exception as e:
                logging.warning(f"Error shutting down {language} kernel: {e}")
        self._kernels.clear()
