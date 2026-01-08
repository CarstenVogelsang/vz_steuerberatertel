#!/usr/bin/env python3
"""Flask Application Runner.

Usage:
    python run.py              # Development server on port 5002
    python run.py --port 8080  # Custom port
    flask run                  # Alternative using Flask CLI
"""

import argparse
from app import create_app

app = create_app()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Flask development server")
    parser.add_argument("--port", type=int, default=5123, help="Port to run on")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--debug", action="store_true", default=True, help="Enable debug mode")
    args = parser.parse_args()

    print(f"\n🚀 Starting Collector DATEV Web Interface")
    print(f"   URL: http://{args.host}:{args.port}")
    print(f"   Debug: {args.debug}\n")

    app.run(host=args.host, port=args.port, debug=args.debug)
