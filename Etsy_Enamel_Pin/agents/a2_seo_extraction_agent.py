import os
from typing import TypedDict, Annotated, Sequence, List
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from PingPinGoState import PingPinGoState

load_dotenv()

llm = ChatOpenAI(
    model="qwen-plus",
    base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    api_key=os.environ["DASHSCOPE_API_KEY"],
    temperature=0,
    timeout=30,
    max_retries=2,
)

class CompetitorSignal(BaseModel):
    is_valid: bool = Field(description="False if the input is noise or lacks product attributes.")
    sku: str= Field(description="SKU of the product.")
    title: str = Field(description="Title of the competitor.")
    category: str = Field(description="Category of the product.")
    keywords: List[str] = Field(description = "Clean, deduplicated keywords.")
    selling_point: List[str] = Field(description = "Unique selling points like material or size.")
    description: str = Field(description = "The product description extracted or generated. If missing from input, return 'MISSING_DESCRIPTION'.")
    reasoning: str = Field(description = "Brief note on filtering decisions.")

def seo_extraction_node(state: PingPinGoState) -> dict:
    structured_llm = llm.with_structured_output(CompetitorSignal)
    own_data = state.get("user_ideas", "No own data provided")
    competitor_data = state.get("competitor_data", "No competitor_data provided")
    combined_input = f"""
    Analyze the following product information and extract structured SEO signals.
    
    [User's Own Product Information (High Priority - STRICTLY ADHERE TO THIS)]:
    {own_data}
    
    [Competitor Listing Data (For reference - DO NOT COPY ATTRIBUTES)]:
    {competitor_data}        
    
    Instructions:
    1. PRODUCT TYPE LOCK: The user's own product information defines the core identity.
       - If the input is a standalone hardware device (e.g., MacBook, Computer, Phone), the category MUST be 'Electronics' or 'Hardware'. DO NOT hallucinate that it is an accessory, case, sleeve, or skin.
       - Only extract attributes that are explicitly stated. If the user does not mention a 'sleeve' or 'case', do not add those terms.
       
    2. EXTRACTION LOGIC:
       - Keywords: Extract high-intent search terms based *only* on the provided product name and attributes.
       - Selling Points: Extract only features explicitly mentioned by the user. If the user did not provide a selling point, return an empty list.
       
    3. FACTUAL INTEGRITY:
       - Ignore any competitor attributes that conflict with the User's product type.
       - Maintain high precision. If information is ambiguous, favor literal interpretation.
       - Avoid marketing fluff (e.g., "stunning", "best-in-class") unless it is a core feature described by the user.
       
    4. CATEGORY CLASSIFICATION: 
       - Assign the most appropriate Etsy category (e.g., Electronics, Accessory, Jewelry, Handcrafted, Stationery).
    """

    if own_data == "No own data provided" and competitor_data == "No competitor_data provided":
        return{"seo_metadata": {"is_valid": False, "reasoning": "No input provided"}}
    result = structured_llm.invoke(combined_input)
    return {
        "category": result.category,
        "keyword_list": result.keywords,
        "selling_point": result.selling_point,
        "extracted_description": result.description,
        "seo_metadata":{"reasoning": result.reasoning, "is_valid": result.is_valid},
    }