from fastapi import FastAPI
 
from api.health import router as health_router
from config import get_config
from utils.logger import configure_logging
from utils.middlewares import AllowHostsMiddleware, RequestIdMiddleware
 
config = get_config()
configure_logging(config)
 
app = FastAPI(title="vector-stores.sentralix.ru")
 
app.add_middleware(AllowHostsMiddleware, allow_hosts=config.allow_hosts)
app.add_middleware(RequestIdMiddleware)
 
app.include_router(health_router)
