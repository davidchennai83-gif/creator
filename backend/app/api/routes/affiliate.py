from app.api.planned import planned_router
router = planned_router("Affiliate marketing", [("GET", "/networks"), ("GET", "/products"), ("POST", "/products"), ("GET", "/links"), ("POST", "/links"), ("GET", "/clicks"), ("GET", "/commissions"), ("GET", "/revenue"), ("POST", "/promote")])
