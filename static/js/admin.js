let map;
let warehouseMarker;
let routeLayers = {};     // Maps routeId -> Leaflet LayerGroup containing polyline and markers
let routeGeometries = {};  // Maps routeId -> Leaflet Polyline object
let activeRouteId = null;

// Premium color palette for routes (HSL values for consistent vibrancy)
const ROUTE_COLORS = [
    "#4f46e5", // Indigo
    "#06b6d4", // Cyan
    "#059669", // Emerald
    "#db2777", // Pink
    "#d97706", // Amber
    "#dc2626", // Red
    "#7c3aed", // Violet
    "#2563eb", // Blue
    "#0891b2", // Teal
    "#16a34a", // Green
    "#ea580c", // Orange
    "#be185d", // Rose
    "#475569", // Slate
    "#84cc16", // Lime
    "#e11d48"  // Crimson
];

document.addEventListener("DOMContentLoaded", () => {
    initMap();
    loadDashboardData();
});

// Initialize Leaflet Map
function initMap() {
    map = L.map("map").setView([WAREHOUSE_LAT, WAREHOUSE_LON], 11);
    
    // OpenStreetMap high fidelity light tiles
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
    
    // Custom Warehouse Icon (Home SVG representation)
    const warehouseIcon = L.divIcon({
        className: 'warehouse-div-icon',
        html: `<div style="background-color: #dc2626; border: 2.5px solid white; width: 34px; height: 34px; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; box-shadow: 0 4px 10px rgba(0,0,0,0.3);"><i class="fa-solid fa-warehouse" style="font-size: 0.9rem;"></i></div>`,
        iconSize: [34, 34],
        iconAnchor: [17, 17]
    });
    
    warehouseMarker = L.marker([WAREHOUSE_LAT, WAREHOUSE_LON], { icon: warehouseIcon })
        .addTo(map)
        .bindPopup(`<strong>${WAREHOUSE_NAME}</strong><br>Starting point for all flour dispatches.`);
}

// Fetch dashboard stats and routes
async function loadDashboardData() {
    try {
        // 1. Fetch Stats
        const statsResponse = await fetch("/api/dashboard/stats");
        if (statsResponse.ok) {
            const stats = await statsResponse.json();
            document.getElementById("stat-orders").innerText = stats.total_orders;
            document.getElementById("stat-distance").innerText = stats.total_distance_km.toFixed(1);
            document.getElementById("stat-routes").innerText = stats.routes_count;
        }
        
        // 2. Fetch Routes
        const routesResponse = await fetch("/api/routes");
        if (routesResponse.ok) {
            const routes = await routesResponse.json();
            renderRoutesAndMap(routes);
        }
    } catch (err) {
        console.error("Error loading dashboard data:", err);
    }
}

// Draw routes on map and populate sidebar list
function renderRoutesAndMap(routes) {
    // Clear existing layers
    Object.values(routeLayers).forEach(layer => map.removeLayer(layer));
    routeLayers = {};
    routeGeometries = {};
    
    const container = document.getElementById("routes-container");
    container.innerHTML = "";
    
    if (routes.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; color: var(--text-muted); font-size: 0.85rem; padding: 30px;">
                <i class="fa-solid fa-map-location-dot" style="font-size: 2rem; margin-bottom: 12px; display: block; color: var(--border);"></i>
                <p style="font-weight: 600;">No active routes generated.</p>
                <button onclick="triggerFullReoptimization()" class="btn btn-primary" style="margin-top: 12px;">Calculate Routes Now</button>
            </div>
        `;
        return;
    }
    
    routes.forEach((route, index) => {
        const color = ROUTE_COLORS[index % ROUTE_COLORS.length];
        const routeLayerGroup = L.layerGroup().addTo(map);
        routeLayers[route.id] = routeLayerGroup;
        
        // 1. Render sidebar route card
        const routeCard = document.createElement("div");
        routeCard.className = `route-item ${activeRouteId === route.id ? 'selected' : ''}`;
        routeCard.id = `route-card-${route.id}`;
        routeCard.onclick = () => selectRoute(route.id);
        
        // Build stop list HTML
        let stopsHtml = "";
        route.orders.forEach(order => {
            const statusClass = order.status === "delivered" ? "delivered" : "";
            const statusIcon = order.status === "delivered" ? '<i class="fa-solid fa-check"></i>' : order.sequence;
            
            stopsHtml += `
                <div class="stop-item">
                    <span class="stop-badge ${statusClass}">${statusIcon}</span>
                    <div class="stop-details">
                        <div class="stop-name">${order.customer_name} <span class="mono" style="font-size: 0.65rem; color: var(--primary);">(${order.quantity} bags)</span></div>
                        <div class="stop-addr">${order.address}</div>
                    </div>
                </div>
            `;
        });
        
        routeCard.innerHTML = `
            <div class="route-header">
                <div class="route-title"><i class="fa-solid fa-user-ninja" style="color: ${color}; margin-right: 6px;"></i> ${route.partner_name}</div>
                <div class="route-color-pill" style="background-color: ${color};"></div>
            </div>
            <div class="route-metrics">
                <span><i class="fa-solid fa-location-dot"></i> ${route.orders.length} stops</span>
                <span><i class="fa-solid fa-road"></i> ${route.total_distance.toFixed(1)} km</span>
                <span><i class="fa-solid fa-clock"></i> ${route.total_duration.toFixed(0)}m</span>
            </div>
            <div style="font-size: 0.7rem; color: var(--text-muted); margin-bottom: 4px;">
                <i class="fa-solid fa-phone"></i> Partner ID ${route.partner_id} &bull; <a href="/partner/${route.partner_id}" target="_blank" onclick="event.stopPropagation();">Driver Link <i class="fa-solid fa-external-link" style="font-size: 0.6rem;"></i></a>
            </div>
            <div class="route-stops-list">
                ${stopsHtml}
            </div>
        `;
        container.appendChild(routeCard);
        
        // 2. Draw route path geometry on Leaflet
        if (route.polyline) {
            try {
                const geojson = JSON.parse(route.polyline);
                
                // Leaflet coordinates are [lat, lon], GeoJSON are [lon, lat], so we invert
                const latLons = geojson.coordinates.map(coord => [coord[1], coord[0]]);
                
                // Draw route line
                const polyline = L.polyline(latLons, {
                    color: color,
                    weight: 5,
                    opacity: 0.75,
                    lineJoin: 'round'
                }).addTo(routeLayerGroup);
                
                // Bind tooltip to line
                polyline.bindTooltip(`Route: ${route.partner_name} (${route.total_distance.toFixed(1)} km)`);
                routeGeometries[route.id] = polyline;
                
            } catch (err) {
                console.error("Failed to parse polyline geometry for route:", route.id, err);
            }
        }
        
        // 3. Draw customer pins on Leaflet
        route.orders.forEach(order => {
            if (order.latitude && order.longitude) {
                const isDelivered = order.status === "delivered";
                const badgeColor = isDelivered ? "#10b981" : color;
                const innerHtml = isDelivered 
                    ? `<i class="fa-solid fa-check" style="font-size: 0.6rem;"></i>` 
                    : order.sequence;
                
                const pinIcon = L.divIcon({
                    className: 'customer-div-icon',
                    html: `<div style="background-color: ${badgeColor}; border: 2px solid white; width: 22px; height: 22px; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 0.65rem; box-shadow: var(--shadow);">${innerHtml}</div>`,
                    iconSize: [22, 22],
                    iconAnchor: [11, 11]
                });
                
                L.marker([order.latitude, order.longitude], { icon: pinIcon })
                    .addTo(routeLayerGroup)
                    .bindPopup(`
                        <strong>Stop #${order.sequence}: ${order.customer_name}</strong><br>
                        Address: ${order.address}<br>
                        Quantity: ${order.quantity} flour bags<br>
                        Driver: ${route.partner_name}<br>
                        Status: <span style="font-weight: bold; color: ${isDelivered ? '#10b981' : '#3b82f6'};">${order.status.toUpperCase()}</span>
                    `);
            }
        });
    });
}

// Select a route in sidebar and focus on map
function selectRoute(routeId) {
    // Reset previous selection
    if (activeRouteId && document.getElementById(`route-card-${activeRouteId}`)) {
        document.getElementById(`route-card-${activeRouteId}`).classList.remove("selected");
        if (routeGeometries[activeRouteId]) {
            routeGeometries[activeRouteId].setStyle({ weight: 5, opacity: 0.75 });
        }
    }
    
    activeRouteId = routeId;
    
    // Highlight new selection
    const card = document.getElementById(`route-card-${routeId}`);
    if (card) {
        card.classList.add("selected");
    }
    
    const polyline = routeGeometries[routeId];
    if (polyline) {
        polyline.setStyle({ weight: 8, opacity: 0.95 });
        // Zoom and center map to fit polyline
        map.fitBounds(polyline.getBounds(), { padding: [40, 40], maxZoom: 14 });
    }
}

// Trigger daily morning re-optimization API
async function triggerFullReoptimization() {
    if (!confirm("Are you sure you want to recalculate and optimize all routes? This will wipe and rebuild today's route sequences.")) {
        return;
    }
    
    const btn = document.querySelector(".header-actions button");
    const originalText = btn.innerHTML;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Calculating...`;
    btn.disabled = true;
    
    try {
        const response = await fetch("/api/routes/optimize", { method: "POST" });
        if (response.ok) {
            alert("Optimal routes generated successfully!");
            activeRouteId = null;
            await loadDashboardData();
        } else {
            const err = await response.json();
            alert("Optimization failed: " + (err.detail || "Unknown error"));
        }
    } catch (err) {
        console.error(err);
        alert("Network error.");
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

// Submit midday new customer order
async function submitMiddayOrder(event) {
    event.preventDefault();
    
    const btn = document.getElementById("btn-submit-order");
    const originalText = btn.innerHTML;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Geocoding & Routing...`;
    btn.disabled = true;
    
    const payload = {
        name: document.getElementById("cust-name").value.strip ? document.getElementById("cust-name").value.strip() : document.getElementById("cust-name").value,
        phone: document.getElementById("cust-phone").value,
        address: document.getElementById("cust-addr").value,
        quantity: parseInt(document.getElementById("cust-qty").value)
    };
    
    try {
        const response = await fetch("/api/orders/add-midday", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        
        if (response.ok) {
            const res = await response.json();
            alert(`Midday Order Dispatched!\nAssigned to partner: ${res.assigned_partner}\nRoute sequence recalculated automatically!`);
            
            // Clear form
            document.getElementById("cust-name").value = "";
            document.getElementById("cust-phone").value = "";
            document.getElementById("cust-addr").value = "";
            document.getElementById("cust-qty").value = "2";
            
            // Set activeRouteId to the updated route so it stays highlighted and open
            activeRouteId = res.route_id;
            
            // Refresh data
            await loadDashboardData();
            
            // Focus on the updated route
            setTimeout(() => {
                selectRoute(res.route_id);
            }, 100);
            
        } else {
            const err = await response.json();
            alert("Dispatch failed: " + (err.detail || "Unknown error"));
        }
    } catch (err) {
        console.error(err);
        alert("Network connection error.");
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}
