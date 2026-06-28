from pathlib import Path
from dotenv import load_dotenv
import os

# Root project
BASE_DIR = Path(__file__).resolve().parents[2]

# Load .env
load_dotenv(BASE_DIR / ".env")

# Folder
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"

for folder in [RAW_DIR]:
    folder.mkdir(parents=True, exist_ok=True)