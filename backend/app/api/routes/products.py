from app.api.planned import planned_router
router = planned_router("Products and inventory", [("GET", ""), ("POST", ""), ("GET", "/inventory"), ("GET", "/{product_id}"), ("PUT", "/{product_id}"), ("DELETE", "/{product_id}")])
