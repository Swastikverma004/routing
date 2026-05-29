import json
import numpy as np
from sklearn.cluster import KMeans
from sqlalchemy.orm import Session
from database import Warehouse, DeliveryPartner, Customer, Order, Route
from router import solve_tsp_osrm
from geocoder import geocode_address

def run_delivery_optimization(db: Session) -> dict:
    """
    Step 3 & Step 4 Master Optimizer:
    1. Fetches all active delivery partners and pending orders.
    2. Clusters orders spatially using K-Means.
    3. Solves the TSP for each partner cluster using the OSRM Trip API.
    4. Saves the generated routes and order sequence numbers to the database.
    """
    # 1. Fetch Warehouse, Active Partners, and Pending Orders
    warehouse = db.query(Warehouse).first()
    if not warehouse:
        return {"status": "error", "message": "No warehouse found in database. Please seed or add one."}
        
    partners = db.query(DeliveryPartner).filter(DeliveryPartner.status == "active").all()
    if not partners:
        return {"status": "error", "message": "No active delivery partners found."}
        
    orders = db.query(Order).filter(Order.status == "pending").all()
    if not orders:
        return {"status": "success", "message": "No pending orders to optimize."}
        
    n_partners = len(partners)
    n_orders = len(orders)
    
    print(f"[Optimizer] Starting optimization for {n_orders} orders and {n_partners} partners.")
    
    # 2. Extract Customer coordinates for clustering
    # Make sure we only cluster orders that have valid customer coordinates
    valid_orders = []
    coords = []
    
    for order in orders:
        customer = order.customer
        if customer.latitude is not None and customer.longitude is not None:
            valid_orders.append(order)
            coords.append([customer.latitude, customer.longitude])
        else:
            print(f"[Optimizer Warning] Order {order.id} has customer {customer.name} with missing coordinates. Skipping.")
            
    if not valid_orders:
        return {"status": "error", "message": "No orders have valid customer geocoding coordinates."}
        
    coords_arr = np.array(coords)
    
    # Determine number of clusters (K)
    # Cannot have more clusters than valid orders
    K = min(n_partners, len(valid_orders))
    print(f"[Optimizer] Running K-Means clustering with K={K} clusters...")
    
    # Run K-Means Spatial Clustering (Step 3)
    kmeans = KMeans(n_clusters=K, random_state=42, n_init='auto')
    cluster_labels = kmeans.fit_predict(coords_arr)
    
    # Group orders by their assigned cluster
    clusters = {i: [] for i in range(K)}
    for idx, order in enumerate(valid_orders):
        label = cluster_labels[idx]
        clusters[label].append(order)
        
    # Clear any old active/pending routes before recalculating
    print("[Optimizer] Cleaning up old active routes...")
    old_routes = db.query(Route).filter(Route.status.in_(["pending", "active"])).all()
    for old_route in old_routes:
        # Reset assigned orders back to pending
        for order in old_route.orders:
            order.route_id = None
            order.sequence_number = None
            order.status = "pending"
        db.delete(old_route)
    db.commit()
    
    depot_coords = (warehouse.latitude, warehouse.longitude)
    routes_created = 0
    
    # 3. Solve TSP and build routes for each cluster (Step 4)
    for cluster_id, cluster_orders in clusters.items():
        if not cluster_orders:
            continue
            
        partner = partners[cluster_id]
        print(f"\n[Optimizer] Processing Route for Partner: {partner.name} (Cluster {cluster_id}) with {len(cluster_orders)} stops.")
        
        # Prepare stop coordinates for OSRM
        stop_coords = [(order.customer.latitude, order.customer.longitude) for order in cluster_orders]
        
        # Call OSRM Trip API
        tsp_result = solve_tsp_osrm(depot_coords, stop_coords)
        if not tsp_result:
            print(f"[Optimizer Error] OSRM failed for partner {partner.name}. Skipping cluster.")
            continue
            
        # Create the new Route record
        new_route = Route(
            partner_id=partner.id,
            warehouse_id=warehouse.id,
            total_distance=tsp_result["distance"],
            total_duration=tsp_result["duration"],
            polyline_geometry=tsp_result["geometry"],
            status="active"
        )
        db.add(new_route)
        db.commit()
        db.refresh(new_route)
        
        # 4. Save order sequences back to database
        # tsp_result['sequence'] contains the sequence index (1 to N) for each stop coordinate
        sequence_positions = tsp_result["sequence"]
        
        for idx, order in enumerate(cluster_orders):
            order.route_id = new_route.id
            order.sequence_number = sequence_positions[idx]
            order.status = "assigned"
            
        db.commit()
        routes_created += 1
        print(f"[Optimizer] Route successfully created for {partner.name}: Distance = {new_route.total_distance:.2f} km, Duration = {new_route.total_duration:.1f} mins")
        
    return {
        "status": "success",
        "message": f"Successfully created {routes_created} routes and assigned {len(valid_orders)} orders.",
        "routes_count": routes_created,
        "assigned_orders": len(valid_orders)
    }

def handle_midday_new_order(db: Session, customer_name: str, customer_phone: str, customer_address: str, demand_quantity: int) -> dict:
    """
    Step 6: Handle Mid-Day New Orders
    1. Geocodes the new customer's address using Nominatim.
    2. Inserts new Customer and Order records into the database.
    3. Finds the nearest partner's route by calculating the distance from the new customer
       to the closest delivery stop currently assigned to any active route.
    4. Assigns the new order to the selected route.
    5. Re-runs the OSRM Trip API ONLY on that modified route to recalculate the optimal sequence.
    """
    # 1. Geocode customer address
    lat, lon = geocode_address(db, customer_address)
    if lat is None or lon is None:
        return {"status": "error", "message": "Failed to geocode customer address."}
        
    # 2. Fetch Warehouse
    warehouse = db.query(Warehouse).first()
    if not warehouse:
        return {"status": "error", "message": "No warehouse found."}
        
    # 3. Create Customer and Order
    customer = Customer(
        name=customer_name,
        phone=customer_phone,
        address=customer_address,
        latitude=lat,
        longitude=lon
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    
    order = Order(
        customer_id=customer.id,
        warehouse_id=warehouse.id,
        demand_quantity=demand_quantity,
        status="pending"
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    
    # 4. Fetch all active routes
    active_routes = db.query(Route).filter(Route.status == "active").all()
    if not active_routes:
        # If no active routes exist, we can't assign to nearest. Keep order pending.
        return {
            "status": "warning",
            "message": "New order created but kept pending: No active routes exist currently.",
            "order_id": order.id
        }
        
    # 5. Find the nearest route
    # We will find the closest individual stop on any active route
    min_dist = float('inf')
    selected_route = None
    
    for route in active_routes:
        for route_order in route.orders:
            c = route_order.customer
            if c.latitude is not None and c.longitude is not None:
                # Calculate simple Euclidean distance representation
                dist = np.sqrt((c.latitude - lat)**2 + (c.longitude - lon)**2)
                if dist < min_dist:
                    min_dist = dist
                    selected_route = route
                    
    if not selected_route:
        # Fallback to the first route if somehow no coordinates are available
        selected_route = active_routes[0]
        
    print(f"[Mid-day Router] Assigning new order to partner: {selected_route.partner.name} (Route ID: {selected_route.id})")
    
    # 6. Assign new order to selected route
    order.route_id = selected_route.id
    order.status = "assigned"
    db.commit()
    
    # 7. Recalculate ONLY the selected route (Step 6)
    # Get all orders on this route (including the new one)
    route_orders = db.query(Order).filter(Order.route_id == selected_route.id).all()
    
    depot_coords = (warehouse.latitude, warehouse.longitude)
    stop_coords = [(ro.customer.latitude, ro.customer.longitude) for ro in route_orders]
    
    # Call OSRM Trip API for the modified list of coordinates
    tsp_result = solve_tsp_osrm(depot_coords, stop_coords)
    if not tsp_result:
        # Fallback sequence in case OSRM fails
        print("[Mid-day Router Warning] OSRM recalculation failed, applying append sequence.")
        # Just append at the end
        order.sequence_number = len(route_orders)
        db.commit()
        return {
            "status": "success",
            "message": f"Assigned to {selected_route.partner.name} (OSRM failed, sequence appended).",
            "order_id": order.id,
            "route_id": selected_route.id
        }
        
    # Save the updated route parameters
    selected_route.total_distance = tsp_result["distance"]
    selected_route.total_duration = tsp_result["duration"]
    selected_route.polyline_geometry = tsp_result["geometry"]
    
    # Update all sequence numbers
    sequence_positions = tsp_result["sequence"]
    for idx, ro in enumerate(route_orders):
        ro.sequence_number = sequence_positions[idx]
        
    db.commit()
    print(f"[Mid-day Router] Route {selected_route.id} successfully updated: {len(route_orders)} stops, distance = {selected_route.total_distance:.2f} km")
    
    return {
        "status": "success",
        "message": f"Successfully assigned to {selected_route.partner.name} and recalculated route.",
        "order_id": order.id,
        "route_id": selected_route.id,
        "assigned_partner": selected_route.partner.name,
        "new_stops_count": len(route_orders),
        "new_distance_km": selected_route.total_distance
    }
