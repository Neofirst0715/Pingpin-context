from pydantic import BaseModel
from typing import Literal, List
from datetime import datetime

class SkuInspectFacts(BaseModel):
    sku_sk: str
    current_description: str
    last_update_date: datetime
    days_since_update: int

class SkuInspectInference(BaseModel):
    need_refresh: bool
    reason: str
    basis: Literal["rule-derived"] = "rule-derived"
    # Tracks whether this recommendation came from a hardcoded rule (now) or a future ML model
class SkuDescriptionInspectReport(BaseModel):
    facts: SkuInspectFacts
    inference: SkuInspectInference

class SkuDescriptionHumaninLoop(BaseModel):
    keyword_list: List[str]
    tone_preference: str

class SkuDescriptionRewrite(BaseModel):
    sku_sk: str
    description: str
    keywords: List[str]
    tone: str
