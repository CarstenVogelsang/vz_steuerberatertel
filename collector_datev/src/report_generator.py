"""HTML Report Generator for search workflow documentation.

Generates a searchable HTML document that documents the entire search
process including queries, results, filtering, and validation scores.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class SearchResultEntry:
    """Single search result entry for the report."""

    url: str
    title: str
    is_filtered: bool = False
    filter_reason: str = ""
    is_linkedin: bool = False
    validation_score: int = 0
    validation_confidence: str = ""
    validation_matches: list[str] = field(default_factory=list)
    validation_error: str = ""
    is_match: bool = False


@dataclass
class ReportEntry:
    """Report entry for a single Steuerberater search."""

    name: str
    plz: str
    city: str
    search_query: str
    search_results: list[SearchResultEntry] = field(default_factory=list)
    final_website: str = ""
    final_confidence: str = ""
    linkedin_url: str = ""
    error: str = ""


class HTMLReportGenerator:
    """Generates HTML reports for search workflow documentation."""

    def __init__(self, plz_filter: str = "", output_dir: Path | None = None):
        """Initialize the report generator.

        Args:
            plz_filter: PLZ filter used for this search session
            output_dir: Directory to save reports (default: data/reports)
        """
        self.plz_filter = plz_filter
        self.output_dir = output_dir or Path("data/reports")
        self.entries: list[ReportEntry] = []
        self.start_time = datetime.now()
        self.stats = {
            "total": 0,
            "found": 0,
            "high_confidence": 0,
            "medium_confidence": 0,
            "low_confidence": 0,
            "no_result": 0,
            "linkedin_found": 0,
        }

    def add_entry(self, entry: ReportEntry) -> None:
        """Add a search entry to the report."""
        self.entries.append(entry)
        self.stats["total"] += 1

        if entry.final_website:
            self.stats["found"] += 1
            if entry.final_confidence == "hoch":
                self.stats["high_confidence"] += 1
            elif entry.final_confidence == "mittel":
                self.stats["medium_confidence"] += 1
            elif entry.final_confidence == "niedrig":
                self.stats["low_confidence"] += 1
        else:
            self.stats["no_result"] += 1

        if entry.linkedin_url:
            self.stats["linkedin_found"] += 1

    def save(self) -> Path:
        """Generate and save HTML report.

        Returns:
            Path to the saved report file
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"search_report_{self.start_time.strftime('%Y-%m-%d_%H-%M')}.html"
        path = self.output_dir / filename

        html = self._generate_html()
        path.write_text(html, encoding="utf-8")
        return path

    def _generate_html(self) -> str:
        """Generate the complete HTML report."""
        entries_html = "\n".join(self._render_entry(i, e) for i, e in enumerate(self.entries, 1))

        return f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Steuerberater-Suche Report - {self.start_time.strftime('%Y-%m-%d %H:%M')}</title>
    <style>
        * {{
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
            line-height: 1.5;
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #007bff;
            padding-bottom: 10px;
        }}
        .meta {{
            background: #fff;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .meta p {{
            margin: 5px 0;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 10px;
            margin-top: 15px;
        }}
        .stat {{
            background: #e9ecef;
            padding: 10px;
            border-radius: 5px;
            text-align: center;
        }}
        .stat-value {{
            font-size: 24px;
            font-weight: bold;
            color: #007bff;
        }}
        .stat-label {{
            font-size: 12px;
            color: #666;
        }}
        .entry {{
            background: #fff;
            border: 1px solid #ddd;
            border-radius: 8px;
            margin: 20px 0;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .entry-header {{
            background: #f8f9fa;
            padding: 15px;
            border-bottom: 1px solid #ddd;
        }}
        .entry-header h3 {{
            margin: 0 0 5px 0;
            color: #333;
        }}
        .entry-header .location {{
            color: #666;
            font-size: 14px;
        }}
        .entry-body {{
            padding: 15px;
        }}
        .search-query {{
            background: #e7f3ff;
            padding: 10px;
            border-radius: 5px;
            font-family: monospace;
            margin: 10px 0;
            color: #0056b3;
        }}
        .results-section {{
            margin: 15px 0;
        }}
        .results-section h4 {{
            margin: 10px 0;
            color: #555;
            border-bottom: 1px solid #eee;
            padding-bottom: 5px;
        }}
        .result {{
            padding: 8px 10px;
            border-bottom: 1px dotted #eee;
            display: flex;
            align-items: flex-start;
            gap: 10px;
        }}
        .result:last-child {{
            border-bottom: none;
        }}
        .result-status {{
            flex-shrink: 0;
            width: 24px;
            text-align: center;
        }}
        .result-content {{
            flex-grow: 1;
        }}
        .result-url {{
            word-break: break-all;
            color: #007bff;
        }}
        .result-title {{
            font-size: 13px;
            color: #666;
            margin-top: 3px;
        }}
        .result.filtered {{
            background: #fff5f5;
            color: #999;
        }}
        .result.filtered .result-url {{
            text-decoration: line-through;
            color: #999;
        }}
        .result.matched {{
            background: #d4edda;
            border-left: 3px solid #28a745;
        }}
        .result.linkedin {{
            background: #e8f4fd;
            border-left: 3px solid #0077b5;
        }}
        .linkedin-badge {{
            background: #0077b5;
            color: white;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 11px;
            margin-left: 5px;
        }}
        .validation {{
            background: #f8f9fa;
            padding: 8px 10px;
            margin: 5px 0;
            border-radius: 5px;
            font-size: 13px;
        }}
        .validation .score {{
            font-weight: bold;
        }}
        .validation .score.high {{
            color: #28a745;
        }}
        .validation .score.medium {{
            color: #ffc107;
        }}
        .validation .score.low {{
            color: #dc3545;
        }}
        .validation .matches {{
            color: #666;
            font-size: 12px;
        }}
        .validation .error {{
            color: #dc3545;
        }}
        .final-result {{
            background: #f0fff4;
            border: 1px solid #28a745;
            border-radius: 5px;
            padding: 10px;
            margin-top: 15px;
        }}
        .final-result.no-match {{
            background: #fff5f5;
            border-color: #dc3545;
        }}
        .final-result h4 {{
            margin: 0 0 10px 0;
            color: #28a745;
        }}
        .final-result.no-match h4 {{
            color: #dc3545;
        }}
        .filter-reason {{
            font-size: 11px;
            color: #999;
            margin-left: 5px;
        }}
        .entry-number {{
            background: #007bff;
            color: white;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 12px;
            margin-right: 10px;
        }}
    </style>
</head>
<body>
    <h1>Steuerberater Website-Suche Report</h1>

    <div class="meta">
        <p><strong>Datum:</strong> {self.start_time.strftime('%Y-%m-%d %H:%M')}</p>
        <p><strong>PLZ-Filter:</strong> {self.plz_filter or 'Kein Filter'}</p>
        <p><strong>Dauer:</strong> {self._format_duration()}</p>

        <div class="stats">
            <div class="stat">
                <div class="stat-value">{self.stats['total']}</div>
                <div class="stat-label">Eintraege</div>
            </div>
            <div class="stat">
                <div class="stat-value">{self.stats['found']}</div>
                <div class="stat-label">Gefunden</div>
            </div>
            <div class="stat">
                <div class="stat-value">{self.stats['high_confidence']}</div>
                <div class="stat-label">Hohe Konfidenz</div>
            </div>
            <div class="stat">
                <div class="stat-value">{self.stats['medium_confidence']}</div>
                <div class="stat-label">Mittlere Konfidenz</div>
            </div>
            <div class="stat">
                <div class="stat-value">{self.stats['no_result']}</div>
                <div class="stat-label">Kein Ergebnis</div>
            </div>
            <div class="stat">
                <div class="stat-value">{self.stats['linkedin_found']}</div>
                <div class="stat-label">LinkedIn</div>
            </div>
        </div>
    </div>

    {entries_html}

</body>
</html>"""

    def _render_entry(self, index: int, entry: ReportEntry) -> str:
        """Render a single entry as HTML."""
        results_html = ""

        if entry.search_results:
            results_items = []
            for r in entry.search_results:
                css_class = "result"
                status_icon = "✅"

                if r.is_linkedin:
                    css_class += " linkedin"
                    status_icon = "🔗"
                elif r.is_filtered:
                    css_class += " filtered"
                    status_icon = "❌"
                elif r.is_match:
                    css_class += " matched"
                    status_icon = "✅"

                filter_info = ""
                if r.filter_reason:
                    filter_info = f'<span class="filter-reason">({r.filter_reason})</span>'

                linkedin_badge = ""
                if r.is_linkedin:
                    linkedin_badge = '<span class="linkedin-badge">LinkedIn</span>'

                validation_html = ""
                if r.validation_score > 0 or r.validation_error:
                    confidence_class = ""
                    if r.validation_confidence == "hoch":
                        confidence_class = "high"
                    elif r.validation_confidence == "mittel":
                        confidence_class = "medium"
                    else:
                        confidence_class = "low"

                    if r.validation_error:
                        validation_html = f'<div class="validation"><span class="error">Fehler: {r.validation_error}</span></div>'
                    else:
                        matches_str = ", ".join(r.validation_matches) if r.validation_matches else "keine"
                        validation_html = f'''<div class="validation">
                            Score: <span class="score {confidence_class}">{r.validation_score}</span>
                            ({r.validation_confidence}) |
                            <span class="matches">Matches: {matches_str}</span>
                        </div>'''

                results_items.append(f'''
                <div class="{css_class}">
                    <div class="result-status">{status_icon}</div>
                    <div class="result-content">
                        <div class="result-url">{r.url}{linkedin_badge}{filter_info}</div>
                        <div class="result-title">{r.title[:80]}{'...' if len(r.title) > 80 else ''}</div>
                        {validation_html}
                    </div>
                </div>''')

            results_html = f'''
            <div class="results-section">
                <h4>Suchergebnisse ({len(entry.search_results)})</h4>
                {"".join(results_items)}
            </div>'''

        # Final result section
        if entry.final_website:
            final_html = f'''
            <div class="final-result">
                <h4>✅ Ergebnis</h4>
                <p><strong>Website:</strong> {entry.final_website}</p>
                <p><strong>Konfidenz:</strong> {entry.final_confidence}</p>
                {f'<p><strong>LinkedIn:</strong> {entry.linkedin_url}</p>' if entry.linkedin_url else ''}
            </div>'''
        else:
            linkedin_note = f'<p><strong>LinkedIn gefunden:</strong> {entry.linkedin_url}</p>' if entry.linkedin_url else ''
            final_html = f'''
            <div class="final-result no-match">
                <h4>❌ Keine passende Website gefunden</h4>
                {linkedin_note}
            </div>'''

        return f'''
        <div class="entry">
            <div class="entry-header">
                <h3><span class="entry-number">{index}/{self.stats['total']}</span>{entry.name}</h3>
                <div class="location">PLZ: {entry.plz} | Ort: {entry.city}</div>
            </div>
            <div class="entry-body">
                <h4>Suchanfrage</h4>
                <div class="search-query">{entry.search_query}</div>
                {results_html}
                {final_html}
            </div>
        </div>'''

    def _format_duration(self) -> str:
        """Format the duration since start."""
        duration = datetime.now() - self.start_time
        minutes = duration.seconds // 60
        seconds = duration.seconds % 60
        return f"{minutes} Min {seconds} Sek"
