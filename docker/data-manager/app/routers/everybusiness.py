from fastapi import APIRouter
from pydantic import BaseModel

from app.services.everybusiness_service import get_current_content, save_and_parse

router = APIRouter(tags=["everybusiness"])


class EverybusinessRequest(BaseModel):
    content: str


@router.get("/api/everybusiness")
async def get_everybusiness():
    return get_current_content()


@router.post("/api/everybusiness")
async def post_everybusiness(req: EverybusinessRequest):
    return save_and_parse(req.content)
