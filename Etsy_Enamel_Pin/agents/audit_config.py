MIN_WORD_COUNT = 100
MAX_WORD_COUNT = 150

BANNED_WORDS = [
    "guaranteed",
    "fda approved",
    "medical claim",
    "best seller",
    "authentic",
]

USE_CASE_SIGNALS = [
    "perfect gift for",
    "perfect for",
    "idea for",
    "use in",
    "for a birthday",
    "for the holiday",
    "ideal gift for",
    "perfect as",
    "gift pin"
]
A2_EXTRACTION_VERSION = "a2_extra_v1"
A2_EXTRACTION_PROMPT = """
    Analyze the following product information and extract structured SEO signals.
    [User's Own Product Information (High Priority - Please prioritize this data)]:
    {own_data}
    [Competitor Listing Data (For reference)]:
    {competitor_data}
    Instructions:
    1. Extract keywords and selling points based on the provided information.
    2. If a section is empty or contains no relevant data, ignore it.
    3. Maintain high precision and avoid marketing fluff.
    """

A2_EXTRACTION_VERSION_2 = "a2_extra_v2"
A2_EXTRACTION_PROMPT_2 = """
    Analyze the following product information and extract structured SEO signals.

[User's Own Product Information (High Priority - STRICTLY ADHERE TO THIS)]:
{own_data}

[Competitor Listing Data (For reference - DO NOT COPY ATTRIBUTES)]:
{competitor_data}

Instructions:
1. PRODUCT TYPE LOCK: The user's own product information defines the core product. 
   - If the input is a standalone electronic device (e.g., MacBook, Computer, Phone), DO NOT hallucinate or assume it is an accessory, case, sleeve, or skin. 
   - Extract attributes only as they appear in the provided data.
2. EXTRACTION LOGIC: 
   - Keywords: Extract high-intent search terms based *only* on the provided product name and attributes.
   - Selling Points: Extract only features explicitly mentioned by the user. If the user did not provide a selling point, return an empty list [].
3. FACTUAL INTEGRITY: 
   - Ignore any competitor attributes (e.g., if competitor sells a sleeve and you are selling a computer, ignore the sleeve-related terms).
   - Maintain high precision. If information is ambiguous, favor literal interpretation over industry-typical assumptions.
4. NO FLUFF: Avoid adding marketing adjectives (e.g., "stunning", "best-in-class",
    """

A3_DRAFT_VERSION = "a2_extra_v1"
A3_DRAFT_PROMPT = """
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
    """

A3_DRAFT_VERSION_2 = "a2_extra_v2"
A3_DRAFT_PROMPT_2 = """
    You are an expert Etsy listing copywriter. Your goal is to create high-converting, SEO-optimized listing copy.
    
    ### Task Parameters:
    - Tone: {tone}
    - Keywords to include: {keywords}
    - Unique Selling Points: {selling_point}
    - Product Identity: {state.get('user_ideas')} 
    - Constraints/Rubric: {rubric}
    
    ### Core Rules:
    1. TRUTH & IDENTITY: You are writing a listing for the product exactly as described in "Product Identity". 
       - If the user is selling a computer, sell a computer. DO NOT turn it into a sleeve, case, or accessory. 
       - If the product info is minimal, focus on the specs/identity provided rather than guessing the product type.
    
    2. TONE MANDATE: 
       The requested tone is: {state.get('tone_preference', 'Professional yet engaging')}.
       - STICK TO THIS TONE: If 'funny', be witty. If 'very cool', be edgy and minimalist. 
       - AVOID GENERIC FLUFF: Stop using common Etsy phrases like "handcrafted with love" or "perfect for gifting" unless it is actually true or requested. Keep the language tied to the user's defined tone.
    
    3. SEO & STRUCTURE:
       - Include keywords naturally.
       - Use the "Product Identity" as the anchor for all descriptive text.
    
    ### Output Format:
    Return your response ONLY in the following format:
    <title> [Write your title here] </title>
    <description> [Write your description here] </description>
    """

A4_PROMPT_VERSION =  "a4_soft_v1"
A4_PROMPT_PROMPT = """ You are an Etsy copy quality reviewer.
The draft below has ALREADY passed all hard rules (word count, keywords, banned terms, use-case). Score ONLY the subjective quality dimensions.
    Seller's intended tone: {tone}
    Title: {draft_title}
    Description: {draft_desc}

    score each dimension: 0-5:
    - 5 = excellent, fully meets the standard
    - 3 = acceptable but with 1-2 noticeable issues
    - 1 = clearly falls short
    For 'feedback_points', give specific, actionable revision notes. Any dimension scoring below 3 MUST have a feedback point explaining exactly what to fix."""


KEYWORD_COVERAGE_THRESHOLD = 0.8