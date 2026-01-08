"""BStBK Collector Debug UI.

Web-basierte Debug-Oberfläche für interaktives Debugging des BStBK Collectors.
Läuft auf Port 5002 und ermöglicht:
- Anzeige der extrahierten Daten
- Weiter/Überspringen/Stopp Steuerung
- Echtzeit-Statistiken
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from threading import Event, Thread
from typing import TYPE_CHECKING, Optional

from flask import Flask, jsonify, render_template, request

if TYPE_CHECKING:
    from src.parser_bstbk import ParsedBStBKEntry

logger = logging.getLogger(__name__)


class DebugUI:
    """Web-basierte Debug-Oberfläche für BStBK Collector."""

    def __init__(self, port: int = 5005):
        """Initialize the Debug UI server.

        Args:
            port: Port number for the Flask server (default: 5005)
        """
        self.port = port

        # Create Flask app with correct template folder
        self.app = Flask(
            __name__,
            template_folder="../app/templates",
            static_folder="../app/static",
        )

        # Disable Flask's default logging in production
        log = logging.getLogger("werkzeug")
        log.setLevel(logging.WARNING)

        # Shared state between Collector and UI
        self.current_entry: Optional[ParsedBStBKEntry] = None
        self.current_url: Optional[str] = None
        self.current_plz: Optional[str] = None
        self.stats = {
            "total": 0,
            "success": 0,
            "skipped": 0,
            "errors": 0,
            "plz_total": 0,
            "plz_current": 0,
        }

        # Synchronization between Collector and UI
        self.action_event = Event()
        self.user_action: Optional[str] = None  # 'next', 'skip', 'stop'

        # Feedback storage: list of {url, plz, feedback, timestamp}
        self.feedback_log: list[dict] = []

        self._setup_routes()

    def _setup_routes(self):
        """Configure Flask routes."""

        @self.app.route("/")
        def index():
            """Render the main debug UI page."""
            return render_template("debug/index.html")

        @self.app.route("/api/current")
        def get_current():
            """Return current state for UI polling."""
            entry_data = None
            if self.current_entry:
                # Convert dataclass to dict, handling nested dataclasses
                entry_data = {
                    "kanzlei": asdict(self.current_entry.kanzlei),
                    "steuerberater": [asdict(s) for s in self.current_entry.steuerberater],
                    "is_einzelperson": self.current_entry.is_einzelperson,
                }
                # Convert date objects to strings
                for stb in entry_data["steuerberater"]:
                    if stb.get("bestelldatum"):
                        stb["bestelldatum"] = str(stb["bestelldatum"])

            return jsonify({
                "entry": entry_data,
                "url": self.current_url,
                "plz": self.current_plz,
                "stats": self.stats,
                "waiting": not self.action_event.is_set(),
            })

        @self.app.route("/api/action", methods=["POST"])
        def post_action():
            """Handle user action (next, skip, stop)."""
            data = request.get_json()
            action = data.get("action") if data else None

            if action in ("next", "skip", "stop"):
                self.user_action = action
                self.action_event.set()
                logger.info(f"Debug UI: Benutzer-Aktion '{action}'")
                return jsonify({"ok": True, "action": action})

            return jsonify({"ok": False, "error": "Invalid action"}), 400

        @self.app.route("/api/stats")
        def get_stats():
            """Return just the stats for lightweight polling."""
            return jsonify(self.stats)

        @self.app.route("/api/feedback", methods=["POST"])
        def post_feedback():
            """Save user feedback for the current entry."""
            from datetime import datetime

            data = request.get_json()
            feedback_text = data.get("feedback") if data else None

            if not feedback_text or not feedback_text.strip():
                return jsonify({"ok": False, "error": "Empty feedback"}), 400

            # Store feedback with context
            feedback_entry = {
                "url": self.current_url,
                "plz": self.current_plz,
                "feedback": feedback_text.strip(),
                "timestamp": datetime.now().isoformat(),
                "entry_name": None,
            }

            # Add entry name if available
            if self.current_entry and self.current_entry.kanzlei:
                feedback_entry["entry_name"] = self.current_entry.kanzlei.name

            self.feedback_log.append(feedback_entry)
            logger.info(f"Feedback gespeichert: {feedback_text[:50]}...")

            return jsonify({"ok": True, "count": len(self.feedback_log)})

        @self.app.route("/api/feedback", methods=["GET"])
        def get_feedback():
            """Return all collected feedback."""
            return jsonify(self.feedback_log)

        @self.app.route("/api/feedback/export")
        def export_feedback():
            """Export feedback as downloadable text file."""
            from flask import Response

            if not self.feedback_log:
                return jsonify({"ok": False, "error": "No feedback to export"}), 404

            lines = []
            for fb in self.feedback_log:
                lines.append(f"=== {fb['timestamp']} ===")
                lines.append(f"URL: {fb['url']}")
                lines.append(f"PLZ: {fb['plz']}")
                if fb.get("entry_name"):
                    lines.append(f"Name: {fb['entry_name']}")
                lines.append(f"Feedback: {fb['feedback']}")
                lines.append("")

            content = "\n".join(lines)
            return Response(
                content,
                mimetype="text/plain",
                headers={"Content-Disposition": "attachment; filename=debug_feedback.txt"},
            )

    def show_entry(
        self,
        url: str,
        entry: Optional[ParsedBStBKEntry],
        plz: str = None,
        is_success: bool = True,
    ) -> str:
        """Show an entry in the UI and wait for user action.

        Args:
            url: The URL of the detail page
            entry: The parsed entry (or None if parsing failed)
            plz: Current PLZ being processed
            is_success: Whether parsing was successful

        Returns:
            User action: 'next', 'skip', or 'stop'
        """
        self.current_url = url
        self.current_entry = entry
        self.current_plz = plz
        self.stats["total"] += 1

        if is_success and entry:
            self.stats["success"] += 1
        elif not entry:
            self.stats["errors"] += 1

        # Clear previous action and wait for new one
        self.action_event.clear()
        self.user_action = None

        logger.debug(f"Debug UI: Warte auf Benutzer-Aktion für {url}")
        self.action_event.wait()

        action = self.user_action or "next"

        if action == "skip":
            self.stats["skipped"] += 1

        return action

    def update_plz_progress(self, current: int, total: int):
        """Update PLZ progress counters.

        Args:
            current: Current PLZ index (1-based)
            total: Total number of PLZ to process
        """
        self.stats["plz_current"] = current
        self.stats["plz_total"] = total

    def start(self):
        """Start the Debug UI server in a background thread."""
        def run_server():
            # Disable reloader in thread context
            self.app.run(
                host="127.0.0.1",
                port=self.port,
                debug=False,
                use_reloader=False,
                threaded=True,
            )

        thread = Thread(target=run_server, daemon=True)
        thread.start()

        logger.info(f"Debug UI gestartet auf http://localhost:{self.port}")
        print(f"\n🌐 Debug UI: http://localhost:{self.port}\n")

    def reset_stats(self):
        """Reset all statistics."""
        self.stats = {
            "total": 0,
            "success": 0,
            "skipped": 0,
            "errors": 0,
            "plz_total": 0,
            "plz_current": 0,
        }
        self.current_entry = None
        self.current_url = None
        self.current_plz = None
