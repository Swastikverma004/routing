import random
from datetime import datetime, date
from sqlalchemy.orm import Session
from database import SessionLocal, Warehouse, DeliveryPartner, Customer, Order, Route
from config import (
    DEFAULT_WAREHOUSE_NAME, DEFAULT_WAREHOUSE_ADDRESS,
    DEFAULT_WAREHOUSE_LAT, DEFAULT_WAREHOUSE_LON
)

def seed_data():
    db = SessionLocal()
    try:
        print("Seeding database...")
        
        # 1. Clear existing data
        print("Clearing existing data...")
        db.query(Order).delete()
        db.query(Route).delete()
        db.query(Customer).delete()
        db.query(DeliveryPartner).delete()
        db.query(Warehouse).delete()
        db.commit()
        
        # 2. Add Warehouse
        print("Adding main warehouse...")
        warehouse = Warehouse(
            name=DEFAULT_WAREHOUSE_NAME,
            address=DEFAULT_WAREHOUSE_ADDRESS,
            latitude=DEFAULT_WAREHOUSE_LAT,
            longitude=DEFAULT_WAREHOUSE_LON
        )
        db.add(warehouse)
        db.commit()
        db.refresh(warehouse)
        
        # 3. Add Delivery Partners (15 partners)
        print("Adding 15 delivery partners...")
        partners = []
        names = [
            "Aarav Sharma", "Kabir Singh", "Vihaan Patel", "Aditya Reddy", 
            "Ishaan Gupta", "Sai Kumar", "Arjun Verma", "Rohan Mehta", 
            "Krishna Murthy", "Pranav Joshi", "Devendra Singh", "Yash Wardhan",
            "Anirudh Nair", "Madhav Rao", "Kartik Iyer"
        ]
        vehicle_types = ["Bike", "Scooter", "Electric Three-Wheeler"]
        
        for i, name in enumerate(names):
            partner = DeliveryPartner(
                name=name,
                phone=f"+91 98765 432{i:02d}",
                vehicle_type=random.choice(vehicle_types),
                status="active"
            )
            db.add(partner)
            partners.append(partner)
        db.commit()
        
        # 4. Add 500 Customers and Orders
        print("Generating 500 customers and orders...")
        
        # We will generate coordinates in clusters around Mohali to simulate realistic hotspots
        # Phase 7 (Central), Sector 62 (North-East), Sector 70 (West), Phase 11 (South-East), Sector 82 (South-West)
        hotspots = [
            (30.7042, 76.7179),  # Phase 7
            (30.7061, 76.7236),  # Phase 3B2
            (30.6865, 76.7329),  # Sector 62
            (30.6863, 76.7152),  # Sector 70
            (30.6725, 76.7335),  # Phase 11
            (30.6578, 76.7185),  # Sector 82 Industrial Area
            (30.6698, 76.7024),  # Sector 79
            (DEFAULT_WAREHOUSE_LAT, DEFAULT_WAREHOUSE_LON)
        ]
        
        for i in range(1, 501):
            # Select a random hotspot and add a small variance
            base_lat, base_lon = random.choice(hotspots)
            lat_offset = random.uniform(-0.02, 0.02)
            lon_offset = random.uniform(-0.02, 0.02)
            
            customer_lat = base_lat + lat_offset
            customer_lon = base_lon + lon_offset
            
            sectors = ["Phase 7", "Phase 3B2", "Sector 62", "Sector 70", "Phase 11", "Sector 82", "Sector 79", "Phase 5"]
            customer = Customer(
                name=f"Customer {i}",
                phone=f"+91 91234 56{i:03d}",
                address=f"Flat {random.randint(1,150)}, Block {random.choice(['A','B','C','D'])}, {random.choice(sectors)}, Mohali, Punjab, India",
                latitude=customer_lat,
                longitude=customer_lon
            )
            db.add(customer)
            db.commit()
            db.refresh(customer)
            
            # Create a corresponding order
            order = Order(
                customer_id=customer.id,
                warehouse_id=warehouse.id,
                order_date=date.today(),
                demand_quantity=random.randint(1, 5),  # 1 to 5 bags of flour
                status="pending"
            )
            db.add(order)
            
            if i % 100 == 0:
                print(f"Generated {i} customers and orders...")
                
        db.commit()
        print("Database seeded successfully with test data!")
        
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
