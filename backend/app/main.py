import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import r
from app.core.errors import CrisError

logging.basicConfig(level=logging.INFO, format='{"t":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}')

app = FastAPI(title="Container & Resource Isolation System (CRIS)", version="0.1.0",
              description="Real Linux namespaces + cgroups v2 control plane, experiments and OS laboratory simulators.")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(r)


@app.exception_handler(CrisError)
async def cris_error(_: Request, e: CrisError):
    return JSONResponse(status_code=e.status, content={"error": {"code": e.code, "message": e.message, "detail": e.detail}})


@app.exception_handler(ValueError)
async def value_error(_: Request, e: ValueError):
    return JSONResponse(status_code=422, content={"error": {"code": "validation_error", "message": str(e), "detail": {}}})
