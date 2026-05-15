"""苏格拉底·七 Web 家教系统 — 入口文件（薄适配层）。"""

from contextlib import asynccontextmanager
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

# Ensure web/ is on sys.path for socratic package imports
_web_dir = Path(__file__).parent
if str(_web_dir) not in sys.path:
    sys.path.insert(0, str(_web_dir))

from socratic.app.config import AppSettings
from socratic.app.container import AppContainer

# ── Settings ──
_settings = AppSettings.from_env()

# ── Container ──
_container = AppContainer(_settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("启动配置检查...")
    _container.check_config()
    _container.init_services()
    print("配置检查通过，服务已就绪")
    yield
    print("服务关闭")


app = FastAPI(title="苏格拉底·七 Web 家教系统", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Attach container to app state so dependencies can access it
app.state.container = _container

# ── Route Modules ──
from socratic.adapters.api.lesson_routes import router as lesson_router
from socratic.adapters.api.panel_routes import router as panel_router
from socratic.adapters.api.textbook_routes import router as textbook_router

app.include_router(lesson_router)
app.include_router(textbook_router)
app.include_router(panel_router)

# ── Static Files ──
app.mount("/", StaticFiles(directory=str(_web_dir / "static"), html=True), name="static")


def main():
    print("启动服务 http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
