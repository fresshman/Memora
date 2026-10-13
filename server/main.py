"""Memora FastAPI 后端入口。

启动：
    conda activate langchain-learn
    python -m server.main
或：
    uvicorn server.main:app --host 127.0.0.1 --port 8000 --reload
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from memora.log import setup_logging
from memora import config

from . import routes

logger = setup_logging()
logger.info("Memora FastAPI 后端启动中（推理后端=%s）", config.INFERENCE_BACKEND)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Memora FastAPI 后端已就绪")
    yield
    logger.info("Memora FastAPI 后端关闭")


app = FastAPI(
    title="Memora API",
    description="端侧离线私密对话智能复盘工具 · FastAPI 后端",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.health.router, tags=["系统"])
app.include_router(routes.review.router, prefix="/api", tags=["复盘"])
app.include_router(routes.qa.router, prefix="/api", tags=["问答"])
app.include_router(routes.voice.router, prefix="/api", tags=["语音"])
app.include_router(routes.live.router, prefix="/api", tags=["实时"])
app.include_router(routes.records.router, prefix="/api/records", tags=["记录"])
app.include_router(routes.export_router.router, prefix="/api", tags=["导出"])
app.include_router(routes.models.router, prefix="/api", tags=["模型"])


# ---------------------------------------------------------------------------
# 端侧离线：若已构建静态前端（web/out），由后端单端口同源托管，用户无需 Node
# ---------------------------------------------------------------------------
_WEB_OUT = config.PROJECT_ROOT / "web" / "out"

if _WEB_OUT.exists():
    from fastapi.staticfiles import StaticFiles

    # html=True：/ 返回 index.html；trailingSlash 导出的 /qa/ 返回 qa/index.html，
    # /qa 由 StaticFiles 自动 307 到 /qa/。/api 路由已先注册，优先匹配不受影响。
    app.mount("/", StaticFiles(directory=str(_WEB_OUT), html=True), name="web")
    logger.info("已托管静态前端 %s，单端口访问首页即可", _WEB_OUT)
else:
    @app.get("/")
    def root():
        return {
            "name": "Memora API", "version": "0.2.0",
            "hint": "未构建前端（web/out 不存在）；开发模式请 cd web && npm run dev",
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
