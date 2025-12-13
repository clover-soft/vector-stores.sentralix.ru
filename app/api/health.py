from fastapi import APIRouter

from config import get_config

router = APIRouter(tags=["system"])


@router.get("/health")
def health():
    config = get_config()
    return {
        "status": "ok",
        "running_in_container": config.running_in_container,
        "database_uri_set": bool(config.database_uri),
    }
