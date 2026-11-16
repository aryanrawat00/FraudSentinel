from fastapi import HTTPException, Request

DEMO_USER_ID = "user_demo_analyst"


def require_demo_identity(request: Request) -> str:
    """Explicit local demo identity; never accept a client-selected user or role."""
    if not request.app.state.settings.demo_mode:
        raise HTTPException(status_code=403, detail="Demo access is disabled")
    return DEMO_USER_ID
