"""Streamlit Cloud entrypoint shim.
This app was originally deployed with Main file = 'app (2).py'.
Keep this file so Cloud can boot even if Settings were never updated.
"""
from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).with_name("app.py")), run_name="__main__")
