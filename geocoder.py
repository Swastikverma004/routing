import time
import requests
from sqlalchemy.orm import Session
from database import GeocodeCache, Customer
from config import NOMINATIM_USER_AGENT

# Mohali bounding box coordinates for Nominatim viewbox parameter:
# left: 76.60, top: 30.80, right: 76.85, bottom: 30.59
MOHALI_VIEWBOX = "76.60,30.80,76.85,30.59"

def geocode_address(db: Session, address: str) -> tuple[float, float] | tuple[None, None]:
    """
    Geocodes an address string using Nominatim, with database caching.
    Returns (latitude, longitude) or (None, None) if not found.
    """
    if not address:
        return None, None
        
    cleaned_address = address.strip()
    
    # 1. Check database cache
    cached = db.query(GeocodeCache).filter(GeocodeCache.address == cleaned_address).first()
    if cached:
        # print(f"[Cache Hit] Address: '{cleaned_address}' -> ({cached.latitude}, {cached.longitude})")
        return cached.latitude, cached.longitude
        
    # 2. Cache Miss - Query Nominatim API
    # Enforce Nominatim's strict rate limit: 1 request per second
    # We sleep 1 second before calling the API
    time.sleep(1.0)
    
    url = "https://nominatim.openstreetmap.org/search"
    headers = {
        "User-Agent": NOMINATIM_USER_AGENT
    }
    params = {
        "q": cleaned_address,
        "format": "json",
        "limit": 1,
        "viewbox": MOHALI_VIEWBOX,
        "bounded": 1  # Bias results to Mohali
    }
    
    print(f"[Cache Miss] Querying Nominatim API for: '{cleaned_address}'...")
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data:
                lat = float(data[0]["lat"])
                lon = float(data[0]["lon"])
                
                # Save to cache
                new_cache = GeocodeCache(
                    address=cleaned_address,
                    latitude=lat,
                    longitude=lon
                )
                db.add(new_cache)
                db.commit()
                
                print(f"[Cache Saved] '{cleaned_address}' -> ({lat}, {lon})")
                return lat, lon
            else:
                # If bounded search inside Delhi failed, try a wider search without bounding box bias
                print(f"Bounded search failed for '{cleaned_address}'. Retrying general search...")
                time.sleep(1.0)
                params.pop("viewbox", None)
                params.pop("bounded", None)
                response = requests.get(url, headers=headers, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data:
                        lat = float(data[0]["lat"])
                        lon = float(data[0]["lon"])
                        
                        new_cache = GeocodeCache(
                            address=cleaned_address,
                            latitude=lat,
                            longitude=lon
                        )
                        db.add(new_cache)
                        db.commit()
                        
                        print(f"[Cache Saved (Unbounded)] '{cleaned_address}' -> ({lat}, {lon})")
                        return lat, lon
                
                print(f"[Geocode Alert] No results found for address: '{cleaned_address}'")
                return None, None
        else:
            print(f"[Geocode Error] Nominatim returned status code {response.status_code}")
            return None, None
    except Exception as e:
        print(f"[Geocode Exception] Error during geocoding: {e}")
        return None, None

def geocode_customer(db: Session, customer_id: int) -> bool:
    """
    Geocodes a specific customer's address and saves the coordinates to their record.
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        return False
        
    lat, lon = geocode_address(db, customer.address)
    if lat is not None and lon is not None:
        customer.latitude = lat
        customer.longitude = lon
        db.commit()
        return True
    return False
