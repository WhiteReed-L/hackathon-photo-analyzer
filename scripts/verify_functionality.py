"""
End-to-end functionality smoke tests for the Fashion AI FastAPI app.

This script starts the ASGI app in-process via httpx.ASGITransport and verifies
the non-OpenAI critical paths:

- app startup / DB initialization
- registration and cookie-based auth
- /api/user/me
- upload authentication
- image validation/re-encoding
- protected asset access
- conversation session/message endpoints
- legacy conversation sync with clothing_tags
- generation job authorization/status for a manually created job

By default it does NOT call OpenAI. Set RUN_AI_JOB=1 to also create a real
/api/generation-jobs task and poll it, which requires valid OpenAI config.
"""
from __future__ import annotations

import asyncio
import io
import os
import sys
import uuid
from pathlib import Path

import httpx
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def make_test_image() -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (32, 32), color=(220, 120, 80))
    img.save(buf, format="PNG")
    return buf.getvalue()


async def assert_status(resp: httpx.Response, expected: int, label: str) -> dict:
    if resp.status_code != expected:
        raise AssertionError(f"{label}: expected {expected}, got {resp.status_code}: {resp.text}")
    try:
        return resp.json()
    except Exception:
        return {}


async def main() -> None:
    # Ensure config.validate_config() passes during app lifespan in local smoke tests.
    os.environ.setdefault("OPENAI_API_KEY", "sk-smoke-test-placeholder")
    os.environ.setdefault("COOKIE_SECURE", "false")

    from database import create_generation_job, get_generation_job
    from main import app

    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            suffix = uuid.uuid4().hex[:10]
            nickname = f"verify_{suffix}"
            password = "verify-password-123"

            print("[1/9] unauthenticated upload is rejected")
            resp = await client.post(
                "/api/upload",
                files={"file": ("x.png", make_test_image(), "image/png")},
            )
            if resp.status_code not in (403, 401):
                raise AssertionError(f"unauth upload expected 401/403, got {resp.status_code}: {resp.text}")

            print("[2/9] register creates authenticated session")
            data = await assert_status(
                await client.post(
                    "/api/user/register",
                    json={"nickname": nickname, "password": password, "height": 170, "weight": 60},
                ),
                200,
                "register",
            )
            assert data["success"] is True
            assert data["user"]["nickname"] == nickname
            assert "fashion_token" in client.cookies

            print("[3/9] /api/user/me returns current user")
            me = await assert_status(await client.get("/api/user/me"), 200, "me")
            user_id = me["id"]
            assert me["nickname"] == nickname

            print("[4/9] invalid image upload is rejected")
            bad = await client.post(
                "/api/upload",
                files={"file": ("fake.png", b"not an image", "image/png")},
            )
            await assert_status(bad, 400, "invalid upload")

            print("[5/9] valid upload is accepted and protected asset can be read")
            uploaded = await assert_status(
                await client.post(
                    "/api/upload",
                    files={"file": ("avatar.png", make_test_image(), "image/png")},
                ),
                200,
                "valid upload",
            )
            assert uploaded["id"] > 0
            assert uploaded["filename"].endswith(".jpg")
            asset_resp = await client.get(f"/api/uploads/{uploaded['filename']}")
            if asset_resp.status_code != 200 or not asset_resp.content.startswith(b"\xff\xd8"):
                raise AssertionError("protected uploaded asset was not served as JPEG")

            print("[6/9] conversation session/message endpoints work")
            session = await assert_status(
                await client.post("/api/conversation-sessions", json={"path": "b", "title": "Smoke Test"}),
                200,
                "create conversation session",
            )
            session_id = session["id"]
            sessions = await assert_status(await client.get("/api/conversation-sessions"), 200, "list sessions")
            assert any(s["id"] == session_id for s in sessions["sessions"])
            msg = await assert_status(
                await client.post(
                    f"/api/conversation-sessions/{session_id}/messages",
                    json={"role": "user", "text": "hello", "metadata": {"source": "verify"}},
                ),
                200,
                "create message",
            )
            assert msg["id"] > 0
            messages = await assert_status(
                await client.get(f"/api/conversation-sessions/{session_id}/messages"),
                200,
                "list messages",
            )
            assert any(m["text"] == "hello" for m in messages["messages"])

            print("[7/9] legacy conversation sync accepts clothing_tags")
            synced = await assert_status(
                await client.post(
                    "/api/conversations/sync",
                    json={
                        "entries": [
                            {
                                "role": "user",
                                "text": "sync smoke",
                                "clothing_tags": ["T恤"],
                                "style_tags": ["简约"],
                                "scene_tags": ["通勤"],
                            }
                        ]
                    },
                ),
                200,
                "conversation sync",
            )
            assert synced["synced"] == 1

            print("[8/9] generation job status endpoint enforces ownership and returns queued job")
            job_id = await create_generation_job(user_id, {"text": "manual smoke"}, status="queued")
            job = await get_generation_job(job_id, user_id)
            assert job and job["status"] == "queued"
            job_status = await assert_status(
                await client.get(f"/api/generation-jobs/{job_id}"),
                200,
                "generation job status",
            )
            assert job_status["job_id"] == job_id
            assert job_status["status"] == "queued"

            print("[9/9] optional real AI generation job")
            if os.getenv("RUN_AI_JOB") == "1":
                created = await assert_status(
                    await client.post("/api/generation-jobs", json={"text": "A simple casual outfit"}),
                    200,
                    "create real generation job",
                )
                real_job_id = created["job_id"]
                for _ in range(90):
                    await asyncio.sleep(2)
                    status = await assert_status(
                        await client.get(f"/api/generation-jobs/{real_job_id}"),
                        200,
                        "poll real generation job",
                    )
                    if status["status"] == "succeeded":
                        assert status["result"] and status["result"].get("image_url")
                        break
                    if status["status"] == "failed":
                        raise AssertionError(f"real generation failed: {status.get('error_message')}")
                else:
                    raise AssertionError("real generation did not finish in time")
            else:
                print("      skipped; set RUN_AI_JOB=1 to call OpenAI")

            print("\nAll smoke checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
