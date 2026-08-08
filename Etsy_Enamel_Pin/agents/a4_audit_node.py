import json
import os
from typing import TypedDict, List, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from audit_config import BANNED_WORDS, USE_CASE_SIGNALS, MIN_WORD_COUNT, MAX_WORD_COUNT
from PingPinGoState import PingPinGoState
from langchain_openai import ChatOpenAI
from langgraph.types import interrupt

load_dotenv()

llm = ChatOpenAI(
    model="qwen-plus",
    base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    api_key=os.environ["DASHSCOPE_API_KEY"],
    temperature=0,
    timeout=30,
    max_retries=2,
)

class AuditResult(BaseModel):
    score: int = Field(description="Total soft-quality score out of 20")
    tone_match: int = Field(description="0-5, tone matches seller's intended style")
    selling_points: int = Field(description="0-5, selling points are concrete and prominent")
    naturalness: int = Field(description="0-5, reads naturally, not keyword-stuffed")
    differentiation: int = Field(description="0-5, distinct from generic competitor copy")
    feedback_points: List[str] = Field(description="Specific, actionable revision notes")

def check_hard_rules(state:PingPinGoState) -> tuple[bool,str]:
    """
        Perform deterministic hard rule validation.
        Returns: (is_passed, violation_reason)
        """
    desc_draft = state.get("final_description", "")
    title = state.get("final_title", "")

    desc_word_count = len(desc_draft.split())
    if not MIN_WORD_COUNT <= desc_word_count <= MAX_WORD_COUNT:
        return False, f"Word count invalid: {desc_word_count} words found, required {MIN_WORD_COUNT}-{MAX_WORD_COUNT}."
    combined_text = (desc_draft + " " + title).lower()
    for word in BANNED_WORDS:
        if word in combined_text:
            return False, f"Prohibited term detected: '{word}'."
    found_scenario = False
    for word in USE_CASE_SIGNALS:
        if word in desc_draft.lower():
            found_scenario = True
            break
    if not found_scenario:
        return False, "Missing use-case description (e.g., 'gift for', 'perfect for')."
    return True, "Passed "

def human_intervention_node(state:PingPinGoState) -> dict:
    """
    Pause execution to await human manual correction.

    This node serves as the Human-in-the-Loop gate. Once external input is provided,
    the graph will resume and transition back to the Audit Node (Agent 4)
    for re-validation of hard/soft constraints.
    """
    human_edit = interrupt({
        "reason": state.get("system_feedback", ""),
        "current_title": state.get("final_title", ""),
        "current_description": state.get("final_description", ""),
    })
    return {
        "final_title": human_edit.get("final_title", ""),
        "final_description": human_edit.get("final_description", ""),
        "retry_count": 0,
        "system_feedback": "Human-edited,pending re-audit" ,
        "last_edit_source": "human",
    }

def audit_node(state:PingPinGoState) ->dict:
    is_passed, reason = check_hard_rules(state)
    if not is_passed:
        return {
            "system_feedback": f"Hard Gate Violation: {reason}",
            "retry_count": state.get("retry_count", 0) + 1
        }
    structured_llm = llm.with_structured_output(AuditResult)
    draft_title = state.get("final_title", "")
    draft_desc = state.get("final_description", "")
    tone = state.get("tone_preference", "")

    prompt_for_soft_scoring = f"""You are an Etsy copy quality reviewer. The draft below has ALREADY passed all hard rules (word count, keywords, banned terms, use-case). Score ONLY the subjective quality dimensions.
    Seller's intended tone: {tone}
    Title: {draft_title}
    Description: {draft_desc}
    
    score each dimension: 0-5:
    - 5 = excellent, fully meets the standard
    - 3 = acceptable but with 1-2 noticeable issues
    - 1 = clearly falls short
    For 'feedback_points', give specific, actionable revision notes. Any dimension scoring below 3 MUST have a feedback point explaining exactly what to fix."""

    result = structured_llm.invoke(prompt_for_soft_scoring)
    SOFT_THRESHOLD = 12
    # Don't trust the model's self-reported aggregate "score" - it's frequently
    # inconsistent with the four sub-scores it just produced. Compute it ourselves.
    total_score = result.tone_match + result.selling_points + result.naturalness + result.differentiation
    audit_result = result.model_dump()
    audit_result["score"] = total_score
    if total_score < SOFT_THRESHOLD:
        return{
            "audit_result": audit_result,
            "system_feedback": "Soft quality below threshold: " + "; ".join(result.feedback_points),
            "retry_count": state.get("retry_count", 0) + 1
        }
    return {
        "audit_result": audit_result,
        "system_feedback": "Passed"
    }