import requests
import json

OSRM_TRIP_URL = "http://router.project-osrm.org/trip/v1/driving"

def solve_tsp_osrm(depot_coords: tuple[float, float], stop_coords: list[tuple[float, float]]) -> dict | None:
    """
    Calls OSRM Trip API to solve the Traveling Salesperson Problem (TSP)
    for a depot and a list of stops.
    
    depot_coords: (latitude, longitude)
    stop_coords: list of (latitude, longitude)
    
    Returns a dictionary containing:
        - 'sequence': list of indices indicating the optimal visit order of the input stops (0-indexed).
        - 'distance': total route distance in km.
        - 'duration': total route duration in minutes.
        - 'geometry': GeoJSON geometry string of the route.
    """
    if not stop_coords:
        return {
            "sequence": [],
            "distance": 0.0,
            "duration": 0.0,
            "geometry": None
        }
        
    # OSRM coordinates are specified as longitude,latitude separated by semicolons
    # Depot must be the first coordinate
    all_coords = [depot_coords] + stop_coords
    coord_strings = [f"{lon},{lat}" for lat, lon in all_coords]
    coords_path = ";".join(coord_strings)
    
    url = f"{OSRM_TRIP_URL}/{coords_path}"
    params = {
        "source": "first",       # Start trip at the first coordinate (depot)
        "roundtrip": "true",     # Return to the depot at the end
        "overview": "full",      # Get detailed route shape
        "geometries": "geojson"  # Return route shape in GeoJSON format
    }
    
    print(f"[OSRM] Querying TSP for {len(stop_coords)} stops...")
    try:
        response = requests.get(url, params=params, timeout=20)
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == "Ok":
                trip = data["trips"][0]
                distance_km = trip["distance"] / 1000.0  # meters to km
                duration_mins = trip["duration"] / 60.0  # seconds to minutes
                geometry_geojson = json.dumps(trip["geometry"])
                
                # The response waypoints tell us the sequence.
                # waypoints[0] is the depot (input index 0)
                # waypoints[i] corresponds to input index i
                # waypoints[i]['waypoint_index'] is the position in the trip.
                waypoints = data["waypoints"]
                
                # We want to find the sequence of stops (excluding depot).
                # The depot is at waypoint_index = 0.
                # Stop sequence maps each stop to its sequence order.
                # input coordinate index i (1 to len(stop_coords)) maps to waypoint_index.
                # Let's map them.
                sequence = [0] * len(stop_coords)
                for i in range(1, len(waypoints)):
                    # waypoints[i] corresponds to stop_coords[i-1]
                    seq_pos = waypoints[i]["waypoint_index"]
                    # seq_pos is the order of visit (1 to N)
                    sequence[i - 1] = seq_pos
                    
                return {
                    "sequence": sequence,
                    "distance": distance_km,
                    "duration": duration_mins,
                    "geometry": geometry_geojson
                }
            else:
                print(f"[OSRM Error] Code: {data.get('code')}")
                return None
        else:
            print(f"[OSRM Error] HTTP Status: {response.status_code}")
            return None
    except Exception as e:
        print(f"[OSRM Exception] Error calculating OSRM route: {e}")
        return None
