import logging
import sys


def setup_logging():
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Remove any handlers added by basicConfig or uvicorn before us
    root.handlers.clear()

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
    )
    root.addHandler(console)

    # Graylog via GELF TCP (optional — only when GRAYLOG_HOST is set)
    try:
        from src.config import settings
        if settings.graylog_host:
            import graypy
            gelf = graypy.GELFTCPHandler(
                host=settings.graylog_host,
                port=settings.graylog_port,
                localname=f"{settings.graylog_app_env}_{settings.graylog_source}",
            )
            root.addHandler(gelf)
            logging.getLogger(__name__).info(
                "Graylog handler attached: %s:%s", settings.graylog_host, settings.graylog_port
            )
    except Exception as exc:
        logging.getLogger(__name__).warning("Graylog setup failed: %s", exc)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
