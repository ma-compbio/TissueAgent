import shutil
import tarfile
import zipfile

from pathlib import Path
from typing import Union

from config import DATA_DIR

def extract_file(filepath: Union[Path, str]) -> str:
    filepath = Path(filepath)
    if not filepath.is_absolute():
        filepath = DATA_DIR / filepath
    res_path = filepath.parent

    extension = filepath.suffix
    try: 
        if not filepath.exists():
            raise FileNotFoundError(f"File path '{filepath}' not found.")


        if (extension in [".tar", ".gz", ".bz2", ".xz"] or 
            filepath.suffixes[-2:] in [".tar", ".gz"]):
            try: 
                with tarfile.open(filepath, 'r:*') as tar_ref:
                    tar_ref.extractall(filepath)
            except tarfile.ReadError:
                return "Error: The TAR file is corrupted or not a valid TAR archive."

        elif extension == ".zip":
            try: 
                with zipfile.ZipFile(filepath, "r") as zip_ref:
                    if not zip_ref.namelist():
                        raise zipfile.BadZipFile("The ZIP file is empty or corrupted.")
                    zip_ref.extractall(res_path)
            except zipfile.BadZipFile:
                return "Error: The file is not a valid ZIP archive or is corrupted."
            except zipfile.LargeZipFile:
                return "Error: ZIP file is too large, consider using ZIP64 format."

        else:
            raise ValueError(f"Unsupported archive format: {filepath.suffix}")

    except FileNotFoundError as e:
        return f"Error: {e}"
    except ValueError as e:
        return f"Error: {e}"
    except PermissionError:
        return "Error: Permission denied, check file/folder permissions."

    unwanted_patterns = ["__MACOSX", ".DS_Store"]
    for unwanted_pattern in unwanted_patterns:
        for unwanted in res_path.rglob(unwanted_pattern):
            if unwanted.is_dir():
                shutil.rmtree(unwanted)
            else:
                unwanted.unlink()

    return f"Success: ZIP file extracted to {res_path}."
