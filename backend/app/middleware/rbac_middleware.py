"""Authorization is a FastAPI dependency, not a no-op HTTP middleware."""
from app.api.deps import require_roles as role_required

__all__ = ["role_required"]
