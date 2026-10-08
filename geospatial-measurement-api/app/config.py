"""Application settings, read from environment variables with safe defaults."""
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./geo_api.db")

# Maximum size of an uploaded file, and of everything inside an uploaded zip.
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "50")) * 1024 * 1024
MAX_UNZIPPED_BYTES = int(os.getenv("MAX_UNZIPPED_MB", "200")) * 1024 * 1024

ALLOWED_EXTENSIONS = {".zip", ".kml"}


