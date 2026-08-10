from typing import TypedDict, Annotated, Sequence
import os
from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, END

class PingPinGoState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_ideas:str
    sku: str
    title: str
    price: str
    category: str
    tone_preference: str
    competitor_data: str        #A2
    keyword_list: list[str]     #A2
    selling_point: list[str]     #A2
    extracted_description: str   #A2
    system_feedback: str
    reasoning: str
    seo_metadata: dict     #A2-A3
    final_title: str       #A3
    final_description: str #A3
    is_compliance: bool    #A1
    rubric_config: dict[str,int]    #A4
    audit_result: dict[str,int]     #A4
    retry_count: int       #A4-A3
    last_edit_source: str  # "agent" | "human"
    human_retry_count: int  # A4 human-intervention loop guard