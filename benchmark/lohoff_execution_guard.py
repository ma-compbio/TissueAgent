"""Python-child audit policy for isolated Lohoff benchmark execution.

Loaded as sitecustomize in analysis subprocesses, never in the model/controller.
All arms use the same policy; no credentials are inherited by analysis children.
"""
import os
from pathlib import Path
import sys

workspace = Path(os.environ['LOHOFF_WORKSPACE']).resolve()
repository = Path(os.environ['LOHOFF_REPOSITORY']).resolve()
environment = Path(os.environ['LOHOFF_ENVIRONMENT']).resolve()
guard_file = Path(__file__).resolve()


def inside(path, root):
    return path == root or root in path.parents


def audit(event, args):
    if event in {'open', 'os.listdir', 'os.scandir'} and args:
        raw = args[0]
        if isinstance(raw, (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(raw)).absolute()
            # Resolve aliases, including symlinks into another run's artifacts.
            path = path.resolve()
            if (inside(path, repository) and not inside(path, workspace)
                    and not inside(path, environment) and path != guard_file):
                raise PermissionError('Benchmark isolation: repository files outside this workspace are unavailable')
            if path.name in {'.bashrc', '.zshrc', '.env', 'auth.json'}:
                raise PermissionError('Credential files are unavailable to analysis code')
            if event == 'open' and len(args) > 2:
                flags = args[2] or 0
                if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC):
                    if not inside(path, workspace) and str(path) != '/dev/null':
                        raise PermissionError('Benchmark writes must remain in this workspace')
    if event in {'os.system', 'os.exec', 'os.posix_spawn', 'os.fork'}:
        raise PermissionError('Nested shell execution is disabled in this benchmark')
    if event == 'subprocess.Popen':
        # Figure comparison can use the installed OCR binary; no other child tools.
        executable = os.path.basename(str(args[0]))
        if executable != 'tesseract':
            raise PermissionError('Nested processes are limited to the installed OCR tool')
    if event in {'socket.connect', 'socket.getaddrinfo'}:
        raise PermissionError('Analysis subprocesses use supplied local inputs only')


sys.addaudithook(audit)
