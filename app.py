#!/usr/bin/env python3
"""
Main Application Entry Point.
Stream: Natural Language Processing
Title: Low-resource and Multilingual Language Modeling via Prompt Engineering and In-context Learning, Applied to Customer Support Chatbot Automation

Usage:
    python3 app.py
    python3 app.py --port 8080
"""

import os
import sys
import argparse
from backend.server import run_server

def main():
    default_port = int(os.environ.get("PORT", 8000))
    parser = argparse.ArgumentParser(
        description="Multilingual & Low-Resource Customer Support Chatbot via Prompt Engineering & In-Context Learning"
    )
    parser.add_argument("--port", type=int, default=default_port, help=f"Port to bind server (default: {default_port})")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host interface (default: 0.0.0.0)")
    args = parser.parse_args()

    run_server(port=args.port, host=args.host)

if __name__ == "__main__":
    main()
