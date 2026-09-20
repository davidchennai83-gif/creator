from app.api.planned import planned_router
router = planned_router("Orders", [("GET", ""), ("POST", ""), ("GET", "/{order_id}"), ("PUT", "/{order_id}/status")])
