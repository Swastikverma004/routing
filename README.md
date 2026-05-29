# Smart Wheat Flour Delivery & Routing System

A professional, zero-cost (free open-source) delivery management and route optimization system built with **FastAPI**, **SQLAlchemy**, **Nominatim (Geocoding)**, and **OSRM (Routing)**.

## Project Features & Architecture

The project is structured according to your 6-step build plan:
1. **PostgreSQL Database Support**: Powered by SQLAlchemy with native PostgreSQL compatibility. Defaults to an instant-run SQLite configuration for zero-setup local development.
2. **Nominatim Geocoding**: Converts addresses into spatial coordinates automatically, featuring a local database caching layer to eliminate repeat API costs and Nominatim rate-limiting policies.
3. **K-Means Spatial Clustering**: Partitions 500+ customer drop points into geographically balanced clusters (20-30 stops per delivery partner).
4. **OSRM Route Optimization**: Solves the Traveling Salesperson Problem (TSP) for each driver's cluster using OSRM's public routing API. This calculates the optimal sequence of stops and returns exact road geometries.
5. **Windows Task Scheduler Integration**: Daily morning dispatches are automated at 6:00 AM using Windows Task Scheduler (`schtasks`), executing a CLI cron script.
6. **Dynamic Mid-Day Ordering**: Mid-day orders are geocoded, assigned to the nearest active partner route, and recalculated via OSRM *without* affecting other drivers.

---

## Directory Structure
```
map/
├── requirements.txt            # Python environment dependencies
├── config.py                   # Global system credentials and settings
├── database.py                 # SQLAlchemy schemas (Warehouses, Partners, Customers, Routes, Orders)
├── geocoder.py                 # Nominatim geocoding client with database caching
├── router.py                   # OSRM Trip API interface for TSP solving and geometry
├── optimizer.py                # K-Means clustering and route compilation logic
├── main.py                     # FastAPI application backend and REST API routes
├── init_db.py                  # Database & schema creation engine
├── seed_db.py                  # Seeding script with mock Delhi spatial dataset (500 orders)
├── cron_job.py                 # CLI trigger script for 6 AM route generation
├── schedule_windows_task.py    # Windows Task Scheduler registration script
├── templates/
│   ├── admin.html              # Admin Dashboard with interactive Leaflet map & dispatches
│   └── partner.html            # Mobile-responsive checklist for drivers
└── static/
    ├── css/
    │   └── style.css           # Premium theme styling (Outfit fonts, glass panels, cards)
    └── js/
        └── admin.js            # Leaflet draw routines, tooltips, AJAX operations
```

---

## Quickstart Instructions

### 1. Install Dependencies
Run the installation in your terminal:
```bash
pip install -r requirements.txt
```
*(Note: Use `py -3.12` to ensure you are executing python under the environment containing these packages.)*

### 2. Configure Environment Variables (`.env`)
By default, the project runs on **SQLite** for immediate, zero-configuration local runs.
To connect to your local **PostgreSQL** instance:
1. Open `.env`.
2. Comment out the SQLite line.
3. Uncomment and fill in your PostgreSQL credentials:
```env
DB_USER=postgres
DB_PASSWORD=YOUR_PASSWORD
DB_HOST=localhost
DB_PORT=5432
DB_NAME=delivery_db
```

### 3. Initialize & Seed Database
Build the database tables and populate them with a mock Delhi delivery dataset (500 customers, 15 partners, 1 main warehouse):
```bash
py -3.12 init_db.py
py -3.12 seed_db.py
```

### 4. Run the Server
Launch the FastAPI application:
```bash
py -3.12 -m uvicorn main:app --reload
```
- **Admin Dashboard**: Open `http://127.0.0.1:8000/` in your browser.
- **Partner Portal Example**: Open `http://127.0.0.1:8000/partner/1` to view "Aarav Sharma's" daily mobile-responsive stop checklist.

---

## Daily Automation (6:00 AM Cron)
The morning route calculation is managed by Windows Task Scheduler. To register/overwrite the task, run:
```bash
py -3.12 schedule_windows_task.py
```
This registers a daily background task named `WheatFlourDailyRouting` that executes at 6:00 AM every morning. Execution logs are stored in `logs/cron_optimization.log`.
