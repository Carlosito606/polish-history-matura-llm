"""python -m harness  -> start the FastAPI server (HARNESS_HOST/HARNESS_PORT)."""
import uvicorn

from .config import SETTINGS


def main() -> None:
    uvicorn.run("harness.server:app", host=SETTINGS.harness_host, port=SETTINGS.harness_port,
                log_level="info", workers=1)


if __name__ == "__main__":
    main()
