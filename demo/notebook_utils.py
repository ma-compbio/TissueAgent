import logging
import shutil
import sys
from contextlib import contextmanager

class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for stream in self.streams:
            stream.write(data)
            stream.flush()

    def flush(self):
        for stream in self.streams:
            stream.flush()

@contextmanager
def tee_output(path, mode="a"):
    stdout = sys.stdout
    stderr = sys.stderr
    file_handler = logging.FileHandler(path, mode=mode)
    file_handler.setLevel(logging.DEBUG)
    root_logger = logging.getLogger()
    # Copy formatter from existing handler if available
    if root_logger.handlers:
        file_handler.setFormatter(root_logger.handlers[0].formatter)
    root_logger.addHandler(file_handler)
    with open(path, mode) as f:
        tee = Tee(stdout, f)
        tee_err = Tee(stderr, f)
        sys.stdout = tee
        sys.stderr = tee_err
        try:
            yield
        finally:
            sys.stdout = stdout
            sys.stderr = stderr
            root_logger.removeHandler(file_handler)
            file_handler.close()

from config import DATA_DIR, DATASET_DIR, PDF_UPLOADS_DIR, SESSIONS_DIR, UPLOADS_DIR

def _reset_data_directories() -> None:
    """Clear and keep explicitly listed runtime folders, and delete all other subdirectories.

    - Keeps (but clears): data/dataset, data/uploads, data/pdfs, sessions/
    - Deletes entirely: any other subdirectories under data/
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    keep_and_clear = {DATASET_DIR, UPLOADS_DIR, PDF_UPLOADS_DIR}

    for child in DATA_DIR.iterdir():
        if not child.is_dir():
            continue
        if child in keep_and_clear:
            shutil.rmtree(child, ignore_errors=True)
            child.mkdir(parents=True, exist_ok=True)
        else:
            shutil.rmtree(child, ignore_errors=True)
    shutil.rmtree(SESSIONS_DIR, ignore_errors=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)