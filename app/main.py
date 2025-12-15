import sys

from fastapi import FastAPI
from fastapi.routing import APIRoute

from api.admin_providers import router as admin_providers_router
from api.files import router as files_router
from api.indexes import router as indexes_router
from api.health import router as health_router
from config import get_config
from database import init_db
from utils.logger import configure_logging
from utils.middlewares import AllowHostsMiddleware, RequestIdMiddleware

config = get_config()
logger = configure_logging(config)

app = FastAPI(title="vector-stores.sentralix.ru")


def log_startup_info() -> None:
    logger.info("=" * 50)
    logger.info("  Запуск vector-stores.sentralix.ru")
    logger.info("  Версия Python: %s", sys.version.split()[0])
    logger.info(
        "  Разрешенные хосты: %s",
        ", ".join(config.allow_hosts) if config.allow_hosts else "все",
    )
    logger.info("  Логирование в файл: %s", config.log_file)
    logger.info("  Уровень логирования: %s", config.log_level)
    logger.info("  Сервер запущен: http://0.0.0.0:8000")
    logger.info("  Ручки бэкенда:")

    routes: list[tuple[str, str]] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        methods = sorted(m for m in (route.methods or set()) if m not in {"HEAD", "OPTIONS"})
        methods_str = ",".join(methods) if methods else "-"
        routes.append((route.path, methods_str))

    for path, methods_str in sorted(routes):
        logger.info("    %s %s", methods_str, path)

    logger.info("=" * 50)

app.add_middleware(AllowHostsMiddleware, allow_hosts=config.allow_hosts)
app.add_middleware(RequestIdMiddleware)

app.include_router(health_router)
app.include_router(files_router)
app.include_router(indexes_router)
app.include_router(admin_providers_router)


@app.on_event("startup")
async def _startup() -> None:
    init_db()
    log_startup_info()
