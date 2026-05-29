from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, 
    ForeignKey, DateTime, Date, Text, Numeric
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from config import DATABASE_URL

Base = declarative_base()

class Warehouse(Base):
    __tablename__ = "warehouses"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    address = Column(String(500), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    
    orders = relationship("Order", back_populates="warehouse")
    routes = relationship("Route", back_populates="warehouse")

class DeliveryPartner(Base):
    __tablename__ = "delivery_partners"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    vehicle_type = Column(String(100), nullable=True)
    status = Column(String(50), default="active")  # 'active', 'inactive'
    
    routes = relationship("Route", back_populates="partner")

class Customer(Base):
    __tablename__ = "customers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    address = Column(String(500), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    orders = relationship("Order", back_populates="customer")

class Route(Base):
    __tablename__ = "routes"
    
    id = Column(Integer, primary_key=True, index=True)
    partner_id = Column(Integer, ForeignKey("delivery_partners.id"), nullable=False)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    total_distance = Column(Float, default=0.0)  # in km
    total_duration = Column(Float, default=0.0)  # in minutes
    polyline_geometry = Column(Text, nullable=True)  # OSRM geometry polyline string
    status = Column(String(50), default="pending")  # 'pending', 'active', 'completed'
    created_at = Column(DateTime, default=datetime.utcnow)
    
    partner = relationship("DeliveryPartner", back_populates="routes")
    warehouse = relationship("Warehouse", back_populates="routes")
    orders = relationship("Order", back_populates="route", order_by="Order.sequence_number")

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    order_date = Column(Date, nullable=False, default=datetime.utcnow().date)
    demand_quantity = Column(Integer, default=1)  # e.g., bags of flour
    status = Column(String(50), default="pending")  # 'pending', 'assigned', 'delivered'
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=True)
    sequence_number = Column(Integer, nullable=True)
    
    customer = relationship("Customer", back_populates="orders")
    warehouse = relationship("Warehouse", back_populates="orders")
    route = relationship("Route", back_populates="orders")

class GeocodeCache(Base):
    __tablename__ = "geocode_cache"
    
    id = Column(Integer, primary_key=True, index=True)
    address = Column(String(500), unique=True, nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# Engine and Session creation
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
