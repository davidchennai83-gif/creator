from app.api.planned import planned_router
router = planned_router("Customers", [("GET", ""), ("POST", ""), ("GET", "/{customer_id}")])
