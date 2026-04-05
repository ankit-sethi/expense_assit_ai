import logging
import shutil
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from pipelines.pdf_pipeline import run_pdf_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# inbox/ sits one level above app/
INBOX_DIR     = Path(__file__).parent.parent / "inbox"
PROCESSED_DIR = INBOX_DIR / "processed"
FAILED_DIR    = INBOX_DIR / "failed"


class PDFHandler(FileSystemEventHandler):

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() != ".pdf":
            return

        # Brief wait to ensure the file is fully written to disk
        time.sleep(2)

        # Optional password sidecar: e.g. statement.pdf.password (plain text)
        password = None
        sidecar = path.with_suffix(".pdf.password")
        if sidecar.exists():
            password = sidecar.read_text().strip()
            logger.info(f"[WATCHER] Password sidecar found for {path.name}")

        logger.info(f"[WATCHER] Processing: {path.name}")
        try:
            summary = run_pdf_pipeline(str(path), password=password)
            logger.info(f"[WATCHER] Done — {summary}")
            PROCESSED_DIR.mkdir(exist_ok=True)
            shutil.move(str(path), PROCESSED_DIR / path.name)
            if sidecar.exists():
                shutil.move(str(sidecar), PROCESSED_DIR / sidecar.name)
        except Exception as e:
            logger.error(f"[WATCHER] Failed to process {path.name}: {e}")
            FAILED_DIR.mkdir(exist_ok=True)
            shutil.move(str(path), FAILED_DIR / path.name)


def run_watcher():
    INBOX_DIR.mkdir(exist_ok=True)
    PROCESSED_DIR.mkdir(exist_ok=True)
    FAILED_DIR.mkdir(exist_ok=True)

    handler  = PDFHandler()
    observer = Observer()
    observer.schedule(handler, str(INBOX_DIR), recursive=False)
    observer.start()
    logger.info(f"[WATCHER] Watching {INBOX_DIR} — drop a PDF to auto-import.")

    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    run_watcher()
