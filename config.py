import os
from dotenv import load_dotenv

load_dotenv()

# Database configuration
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "delivery_db")

# Construct SQLAlchemy database URL
# e.g., postgresql://postgres:postgres@localhost:5432/delivery_db
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# Admin default warehouse config (if we need to initialize one)
DEFAULT_WAREHOUSE_NAME = "Main Wheat Flour Warehouse (Mohali)"
DEFAULT_WAREHOUSE_ADDRESS = "Phase 7, Mohali, Punjab, India"
DEFAULT_WAREHOUSE_LAT = 30.7042
DEFAULT_WAREHOUSE_LON = 76.7179

# Geocoding settings
GEOGRAPHIC_LIMIT = "Mohali, Punjab, India"  # To bias/limit Nominatim search results
NOMINATIM_USER_AGENT = "smart_delivery_manager_v1"

