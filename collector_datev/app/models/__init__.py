"""SQLAlchemy Models.

All database models are imported here for easy access.
"""

from app.models.category import Category
from app.models.domain import Domain
from app.models.job import Job
from app.models.log_entry import LogEntry
from app.models.plz import Plz

# BStBK Collector Models
from app.models.kammer import Kammer
from app.models.rechtsform import Rechtsform
from app.models.kanzlei import Kanzlei
from app.models.steuerberater import Steuerberater
from app.models.plz_collector import PlzCollector
from app.models.collect_result import CollectResult

# AI Configuration
from app.models.ai_config import AIConfig, AVAILABLE_MODELS

__all__ = [
    # Existing models
    "Category",
    "Domain",
    "Job",
    "LogEntry",
    "Plz",
    # BStBK Collector models
    "Kammer",
    "Rechtsform",
    "Kanzlei",
    "Steuerberater",
    "PlzCollector",
    "CollectResult",
    # AI Configuration
    "AIConfig",
    "AVAILABLE_MODELS",
]
