from app.api.planned import planned_router
router = planned_router("Payments", [("GET", ""), ("POST", "/checkout"), ("POST", "/webhook")])
