"""Reset Service.

Provides functionality to reset BStBK collector data.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from flask import current_app

from app import db
from app.models import CollectResult, Kammer, Kanzlei, PlzCollector, Steuerberater


class ResetService:
    """Service for resetting BStBK data."""

    @classmethod
    def full_reset(cls, archive: bool = False) -> dict:
        """Delete all BStBK collector data.

        Deletes data from:
        - steuerberater (depends on kanzlei)
        - collect_result (depends on plz_collector and kanzlei)
        - kanzlei (depends on kammer)
        - plz_collector (where collector_type='bstbk')

        Note: Kammer table is NOT deleted (shared reference data)

        Args:
            archive: If True, create a backup before deleting

        Returns:
            Dictionary with counts of deleted records
        """
        backup_path = None

        if archive:
            backup_path = cls._create_backup()

        # Count before deletion
        steuerberater_count = Steuerberater.query.count()
        collect_result_count = CollectResult.query.count()
        kanzlei_count = Kanzlei.query.count()
        plz_collector_count = PlzCollector.query.filter_by(collector_type="bstbk").count()

        # Delete in correct order (respecting foreign keys)
        # 1. Steuerberater (references kanzlei)
        Steuerberater.query.delete()

        # 2. CollectResult (references plz_collector and kanzlei)
        CollectResult.query.delete()

        # 3. Kanzlei (references kammer and rechtsform)
        Kanzlei.query.delete()

        # 4. PlzCollector (only bstbk entries)
        PlzCollector.query.filter_by(collector_type="bstbk").delete()

        db.session.commit()

        return {
            "success": True,
            "deleted": {
                "steuerberater": steuerberater_count,
                "collect_result": collect_result_count,
                "kanzlei": kanzlei_count,
                "plz_collector": plz_collector_count,
            },
            "backup_path": str(backup_path) if backup_path else None,
        }

    @classmethod
    def _create_backup(cls) -> Path:
        """Create a backup of the database before reset.

        Returns:
            Path to the backup file
        """
        db_path = current_app.config.get("DATABASE_PATH")
        if not db_path:
            # Fallback: use default location
            db_path = current_app.config["PROJECT_ROOT"] / "data" / "collector.db"

        db_path = Path(db_path)
        if not db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")

        # Create backup directory if needed
        backup_dir = db_path.parent / "backups"
        backup_dir.mkdir(exist_ok=True)

        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"collector_{timestamp}.db"

        # Copy database file
        shutil.copy2(db_path, backup_path)

        return backup_path

    @classmethod
    def get_stats(cls) -> dict:
        """Get current data statistics.

        Returns:
            Dictionary with record counts
        """
        return {
            "steuerberater": Steuerberater.query.count(),
            "kanzlei": Kanzlei.query.count(),
            "kammer": Kammer.query.count(),
            "plz_collector": PlzCollector.query.filter_by(collector_type="bstbk").count(),
            "collect_result": CollectResult.query.count(),
        }
