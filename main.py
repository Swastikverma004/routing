import os
from fastapi import FastAPI, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import BaseModel

import database
from database import get_db, Warehouse, DeliveryPartner, Customer, Order, Route, engine, Base, SessionLocal
from optimizer import run_delivery_optimization, handle_midday_new_order

# Create database tables automatically on startup
Base.metadata.create_all(bind=engine)

# Auto-seed default warehouse and partners if database is empty (crucial for clean deployments like Render)
def auto_seed_db():
    db = SessionLocal()
    try:
        if db.query(Warehouse).count() == 0:
            print("Auto-seeding default Mohali warehouse...")
            from config import DEFAULT_WAREHOUSE_NAME, DEFAULT_WAREHOUSE_ADDRESS, DEFAULT_WAREHOUSE_LAT, DEFAULT_WAREHOUSE_LON
            warehouse = Warehouse(
                name=DEFAULT_WAREHOUSE_NAME,
                address=DEFAULT_WAREHOUSE_ADDRESS,
                latitude=DEFAULT_WAREHOUSE_LAT,
                longitude=DEFAULT_WAREHOUSE_LON
            )
            db.add(warehouse)
            db.commit()
            
        if db.query(DeliveryPartner).count() == 0:
            print("Auto-seeding 15 active delivery partners...")
            names = [
                "Aarav Sharma", "Kabir Singh", "Vihaan Patel", "Aditya Reddy", 
                "Ishaan Gupta", "Sai Kumar", "Arjun Verma", "Rohan Mehta", 
                "Krishna Murthy", "Pranav Joshi", "Devendra Singh", "Yash Wardhan",
                "Anirudh Nair", "Madhav Rao", "Kartik Iyer"
            ]
            for i, name in enumerate(names):
                partner = DeliveryPartner(
                    name=name,
                    phone=f"+91 98765 432{i:02d}",
                    vehicle_type="Bike" if i % 2 == 0 else "Scooter",
                    status="active"
                )
                db.add(partner)
            db.commit()
            print("Auto-seeding completed.")
    except Exception as e:
        print(f"Error during auto-seeding: {e}")
    finally:
        db.close()

auto_seed_db()

app = FastAPI(title="Smart Wheat Flour Delivery System", version="1.0.0")

# Setup directories
os.makedirs("templates", exist_ok=True)
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)

# Mount static and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Request Models
class MiddayOrderRequest(BaseModel):
    name: str
    phone: str
    address: str
    quantity: int

class WarehouseRequest(BaseModel):
    name: str
    address: str

# --- HTML VIEWS ---

@app.get("/", response_class=HTMLResponse)
def get_admin_dashboard(request: Request, db: Session = Depends(get_db)):
    warehouse = db.query(Warehouse).first()
    partners_count = db.query(DeliveryPartner).filter(DeliveryPartner.status == "active").count()
    orders_count = db.query(Order).count()
    routes_count = db.query(Route).count()
    
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "warehouse": warehouse,
        "partners_count": partners_count,
        "orders_count": orders_count,
        "routes_count": routes_count
    })

@app.get("/partner/{partner_id}", response_class=HTMLResponse)
def get_partner_dashboard(request: Request, partner_id: int, db: Session = Depends(get_db)):
    partner = db.query(DeliveryPartner).filter(DeliveryPartner.id == partner_id).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Delivery partner not found")
        
    # Get active route for this partner
    route = db.query(Route).filter(Route.partner_id == partner_id, Route.status == "active").first()
    
    return templates.TemplateResponse("partner.html", {
        "request": request,
        "partner": partner,
        "route": route
    })


# --- REST API ENDPOINTS ---

@app.get("/api/dashboard/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    total_orders = db.query(Order).count()
    completed_orders = db.query(Order).filter(Order.status == "delivered").count()
    pending_orders = db.query(Order).filter(Order.status == "pending").count()
    active_routes = db.query(Route).filter(Route.status == "active").all()
    
    total_distance = sum(r.total_distance for r in active_routes)
    total_duration = sum(r.total_duration for r in active_routes)
    
    return {
        "total_orders": total_orders,
        "completed_orders": completed_orders,
        "pending_orders": pending_orders,
        "routes_count": len(active_routes),
        "total_distance_km": round(total_distance, 2),
        "total_duration_mins": round(total_duration, 1)
    }

@app.get("/api/routes")
def get_active_routes(db: Session = Depends(get_db)):
    routes = db.query(Route).all()
    result = []
    
    for route in routes:
        orders_list = []
        # route.orders is sorted by sequence_number
        for order in route.orders:
            orders_list.append({
                "id": order.id,
                "customer_name": order.customer.name,
                "customer_phone": order.customer.phone,
                "address": order.customer.address,
                "latitude": order.customer.latitude,
                "longitude": order.customer.longitude,
                "quantity": order.demand_quantity,
                "sequence": order.sequence_number,
                "status": order.status
            })
            
        result.append({
            "id": route.id,
            "partner_id": route.partner_id,
            "partner_name": route.partner.name,
            "partner_phone": route.partner.phone,
            "vehicle_type": route.partner.vehicle_type,
            "total_distance": round(route.total_distance, 2),
            "total_duration": round(route.total_duration, 1),
            "polyline": route.polyline_geometry,
            "status": route.status,
            "orders": orders_list
        })
        
    return result

@app.get("/api/partners")
def get_partners(db: Session = Depends(get_db)):
    partners = db.query(DeliveryPartner).all()
    return [{
        "id": p.id,
        "name": p.name,
        "phone": p.phone,
        "vehicle_type": p.vehicle_type,
        "status": p.status
    } for p in partners]

@app.post("/api/routes/optimize")
def optimize_routes(db: Session = Depends(get_db)):
    res = run_delivery_optimization(db)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res

@app.post("/api/orders/add-midday")
def add_midday_order(payload: MiddayOrderRequest, db: Session = Depends(get_db)):
    res = handle_midday_new_order(
        db,
        customer_name=payload.name,
        customer_phone=payload.phone,
        customer_address=payload.address,
        demand_quantity=payload.quantity
    )
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res

@app.post("/api/warehouse")
def add_or_update_warehouse(payload: WarehouseRequest, db: Session = Depends(get_db)):
    from geocoder import geocode_address
    
    # Ensure it's in Mohali by appending if not present
    addr = payload.address
    if "mohali" not in addr.lower():
        addr += ", Mohali, Punjab, India"
        
    lat, lon = geocode_address(db, addr)
    if lat is None or lon is None:
        raise HTTPException(status_code=400, detail="Failed to geocode warehouse address in Mohali.")
        
    # Check if a warehouse already exists
    warehouse = db.query(Warehouse).first()
    if warehouse:
        warehouse.name = payload.name
        warehouse.address = addr
        warehouse.latitude = lat
        warehouse.longitude = lon
    else:
        warehouse = Warehouse(
            name=payload.name,
            address=addr,
            latitude=lat,
            longitude=lon
        )
        db.add(warehouse)
        
    db.commit()
    db.refresh(warehouse)
    
    return {
        "status": "success",
        "message": "Warehouse updated successfully.",
        "id": warehouse.id,
        "name": warehouse.name,
        "address": warehouse.address,
        "latitude": warehouse.latitude,
        "longitude": warehouse.longitude
    }


@app.post("/api/orders/{order_id}/deliver")
def deliver_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    order.status = "delivered"
    db.commit()
    
    # Check if all orders on this route are delivered
    route = order.route
    if route:
        all_delivered = all(o.status == "delivered" for o in route.orders)
        if all_delivered:
            route.status = "completed"
            db.commit()
            
    return {"status": "success", "message": f"Order {order_id} marked as delivered."}
