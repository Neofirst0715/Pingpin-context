import os
import re
from typing import TypedDict, Annotated, Sequence, List
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from PingPinGoState import PingPinGoState
from audit_config import MIN_WORD_COUNT, MAX_WORD_COUNT

load_dotenv()

llm = ChatOpenAI(
    model="qwen-plus",
    base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    api_key=os.environ["DASHSCOPE_API_KEY"],
    temperature=0,
    timeout=30,
    max_retries=2,
)

def construct_draft_prompt(state: PingPinGoState) -> str:
    keywords = state["keyword_list"]
    tone = state.get("tone_preference", "professional and friendly")
    selling_point = state.get("selling_point")
    description = state.get("extracted_description")
    rubric = state.get("rubric_config", {})
    prompt = f"""
    You are an expert Etsy listing copywriter. Your goal is to create high-converting, SEO-optimized listing copy.

    ### Task Parameters:
    - Tone: {tone}
    - Keywords to include: {keywords}
    - Unique Selling Points: {selling_point}
    - Reference Description: {description}
    - Constraints/Rubric: {rubric}

    ### Output Format:
    Please separate your output clearly using these tags:
    <title> [Write your title here] </title>
    <description> [Write your description here] </description>
    Your primary goal is to write a high-converting listing.

    1. TONE MANDATE: 
       The user requested the tone to be: {state.get('tone_preference', 'Professional yet engaging')}.
       YOU MUST strictly adhere to this tone. If the user asked for 'funny', be witty. If 'very cool', be edgy and minimalist. 
       Do not revert to generic 'Etsy-style' fluff if it contradicts the requested tone.
    
    2. PRODUCT DATA:
       Keywords: {state.get('keyword_list')}
       Selling Points: {state.get('selling_point')}
    
    3. OUTPUT FORMAT:
       Return the title and description wrapped in XML tags.
    """

    current_retry = state.get("retry_count", 0)
    if current_retry > 0:
        prev_title = state.get("final_title", "")
        feedback = state.get("system_feedback", "")
        prompt += f"""
    ### Revision Required (attempt {current_retry}):
    Your previous title was: "{prev_title}"
    It was rejected for this reason: {feedback}
    Please revise the listing to fix that issue. The description MUST be between {MIN_WORD_COUNT} and {MAX_WORD_COUNT} words.
    """
    return prompt

def listing_draft_node(state: PingPinGoState) -> dict:
    """Agent 3: Draft Listing node
    Generates and parses the listing in XML format using the enhanced prompt."""
    prompt = construct_draft_prompt(state)
    response = llm.invoke(prompt)

    content = response.content if hasattr(response, "content") else str(response)
    # Small local models occasionally mangle the opening angle bracket (e.g. "description> instead
    # of <description>), so tolerate any single leading character before the tag name.
    title_match = re.search(r"[^a-zA-Z]title>(.*?)(?:</title>|$)", content, re.DOTALL)
    desc_match = re.search(r"[^a-zA-Z]description>(.*?)(?:</description>|$)", content, re.DOTALL)

    final_title = title_match.group(1).strip().strip("\"'") if title_match else "Draft Title Failed"
    final_description = desc_match.group(1).strip().strip("\"'") if desc_match else "Draft Description Failed"
    return {
        "final_title": final_title,
        "final_description": final_description,
        "last_edit_source": "agent",
    }