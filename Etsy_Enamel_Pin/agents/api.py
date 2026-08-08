from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langgraph.types import Command
from main import app as workflow, build_initial_state

api = FastAPI(title="Pingpin Etsy Listing Agent", version="2.0")

api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ListingRequest(BaseModel):
    sku: str
    user_ideas: str
    competitor_data: str = ""
    tone_preference: str = ""
    product_category: str = ""


class ResumeRequest(BaseModel):
    thread_id: str
    resume_payload: dict


def _pending_interrupt(config: dict):
    """Return the current interrupt payload for this thread, or None if not paused."""
    state = workflow.get_state(config)
    if state.tasks and state.tasks[0].interrupts:
        return state.tasks[0].interrupts[0].value
    return None


def _run_graph(input_or_command, config: dict) -> dict:
    """Drive the graph one leg (until it finishes or hits the next interrupt)."""
    workflow.invoke(input_or_command, config=config)

    interrupt_payload = _pending_interrupt(config)
    if interrupt_payload is not None:
        return {
            "status": "interrupted",
            "thread_id": config["configurable"]["thread_id"],
            "data": interrupt_payload,
        }

    final_state = workflow.get_state(config).values
    return {
        "status": "complete",
        "thread_id": config["configurable"]["thread_id"],
        "result": {
            "final_title": final_state.get("final_title", ""),
            "final_description": final_state.get("final_description", ""),
            "audit_result": final_state.get("audit_result", {}),
            "is_compliance": final_state.get("is_compliance", True),
            "system_feedback": final_state.get("system_feedback", ""),
        },
    }


@api.get("/")
def root():
    return {"status": "running", "service": "Pingpin Agent", "deployed_on": "Alibaba Cloud ECS"}


@api.post("/generate")
def generate_listing(request: ListingRequest):
    """Start (or restart) a run for this sku. thread_id == sku, so the checkpointer
    can tell which conversation a later /resume call belongs to."""
    if not request.sku:
        raise HTTPException(status_code=400, detail="sku is required and is used as the thread_id")

    config = {"configurable": {"thread_id": request.sku}}

    if _pending_interrupt(config) is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Thread '{request.sku}' already has a pending human review. Call /resume instead.",
        )

    initial_state = build_initial_state(
        user_ideas=request.user_ideas,
        sku=request.sku,
        competitor_data=request.competitor_data,
        tone_preference=request.tone_preference,
        product_category=request.product_category,
    )
    return _run_graph(initial_state, config)


@api.post("/resume")
def resume_listing(request: ResumeRequest):
    """Feed a human decision/edit back in and continue the graph from where it paused."""
    config = {"configurable": {"thread_id": request.thread_id}}

    if _pending_interrupt(config) is None:
        raise HTTPException(
            status_code=409,
            detail=f"Thread '{request.thread_id}' has no pending interrupt to resume.",
        )

    return _run_graph(Command(resume=request.resume_payload), config)
