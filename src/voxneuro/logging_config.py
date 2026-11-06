"""Minimal privacy-conscious logging defaults."""

import logging


def configure_logging(level: int = logging.INFO) -> None:
    """Configure logs without recording filenames, audio, or participant IDs."""
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
