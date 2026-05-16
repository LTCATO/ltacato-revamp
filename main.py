import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

# pyrefly: ignore [missing-import]
from flask import send_from_directory

from utils.app_setup import create_app

app = create_app()

_STATIC = Path(__file__).resolve().parent / "static"


@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory(_STATIC, filename)

if __name__ == "__main__":
    app.run(debug=True)
