"""FastAPI route definitions and dependency injection for GLP Studio."""

__all__ = ["runs_router", "system_router"]


def __getattr__(name: str):
    if name == "runs_router":
        from .runs import router

        return router
    if name == "system_router":
        from .system import router

        return router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
