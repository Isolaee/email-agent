import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from services.agent import run_agent

router = APIRouter()


class ChatMessage(BaseModel):
    role: str  # user | assistant
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


@router.post("/chat")
async def chat(body: ChatRequest):
    messages = [m.model_dump() for m in body.messages]

    async def stream():
        try:
            async for chunk in run_agent(messages):
                yield chunk
        except Exception as e:
            yield f"data: {json.dumps({'delta': f'Unexpected error: {e}'})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
