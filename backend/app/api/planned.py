from fastapi import APIRouter, HTTPException


def planned_router(feature: str, endpoints: list[tuple[str, str]]) -> APIRouter:
    """Keep planned API contracts discoverable without inventing successful results."""
    router = APIRouter()
    def not_implemented():
        raise HTTPException(501, f"{feature} is not implemented yet")
    for method, path in endpoints:
        router.add_api_route(path, not_implemented, methods=[method], summary=f"{feature} (not implemented)", name=f"{feature}_{method}_{path}", responses={501: {"description": "Not implemented"}})
    return router
