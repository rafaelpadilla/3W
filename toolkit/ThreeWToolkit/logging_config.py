# ThreeWToolkit/logging_config.py
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

def setup_default_logging(logs_dir: Path, run_id: str, level: int = logging.INFO) -> Path:
    root = logging.getLogger()

    if getattr(root, "_threew_configured", False):
        return Path(getattr(root, "_threew_log_file"))

    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"run_{run_id}.log"

    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    root.setLevel(level)

    fh = RotatingFileHandler(log_file, maxBytes=5_000_000, backupCount=3)
    fh.setFormatter(fmt)

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)

    root.addHandler(sh)
    root.addHandler(fh)

    root._threew_configured = True
    root._threew_log_file = str(log_file)
    return log_file
