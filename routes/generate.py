"""Generation endpoints.

Legacy /api/generate remains synchronous for compatibility.
New /api/generation-jobs endpoints expose the job model and run work in the background.
"""
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request

import config
from application.generation_service import UserNotFoundError, create_job, generate_outfit, run_job
from database import get_generation_job
from limiter import limiter
from models import GenerateRequest, GenerateResponse, GenerationJobCreateResponse, GenerationJobStatusResponse
from routes.user import require_user

router = APIRouter()


@router.post("/generate", response_model=GenerateResponse)
@limiter.limit(config.GENERATE_RATE_LIMIT)
async def generate(
    request: Request,
    body: GenerateRequest,
    user_id: int = Depends(require_user),
):
    try:
        return await generate_outfit(user_id=user_id, body=body)
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail="用户不存在")
    except Exception:
        raise HTTPException(status_code=502, detail="图片生成失败，请稍后重试")


@router.post("/generation-jobs", response_model=GenerationJobCreateResponse)
@limiter.limit(config.GENERATE_RATE_LIMIT)
async def create_generation_job_endpoint(
    request: Request,
    body: GenerateRequest,
    user_id: int = Depends(require_user),
):
    job_id = await create_job(user_id, body)
    asyncio.create_task(run_job(job_id))
    return GenerationJobCreateResponse(job_id=job_id, status="queued")


@router.get("/generation-jobs/{job_id}", response_model=GenerationJobStatusResponse)
async def get_generation_job_endpoint(
    job_id: int,
    user_id: int = Depends(require_user),
):
    job = await get_generation_job(job_id, user_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return GenerationJobStatusResponse(
        job_id=job_id,
        status=job["status"],
        result=job.get("result_json"),
        error_message=job.get("error_message"),
    )
