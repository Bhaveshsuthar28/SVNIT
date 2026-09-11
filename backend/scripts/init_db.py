import logging
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.database import Base, engine
from app.models import TrajectoryRecord  # noqa: F401

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def init_db() -> None:
    logger.info("Creating PostgreSQL tables and indexes if they do not exist.")
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema is ready.")


if __name__ == "__main__":
    init_db()
