from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage, HumanMessage
from PingPinGoState import PingPinGoState
from a1_compliance_agent import compliance_node
from a2_seo_extraction_agent import seo_extraction_node
from a3_listing_draft import listing_draft_node
from a4_audit_node import audit_node, human_intervention_node
from a5_final_delivery_node import final_delivery_node, human_delivery_approval_node, sanitize_text
import dashscope
from report_schema import SkuDescriptionRewrite
from raw_writer import write_raw_description_node
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

checkpointer = MemorySaver()

def should_proceed_after_compliance(state) -> str:
    if state.get("is_compliance", False):
        return "proceed"
    return "end"
def should_continue_after_audit(state) -> str:
    if state.get("system_feedback") == "Passed":
        return "complete"
    if state.get("last_edit_source") == "human":
        return "human_intervention"
    if state.get("retry_count", 0) < 2:
        return "revise"
    return "human_intervention"
def should_continue_after_final_delivery(state) -> str:
    if state.get("final_approval") == "approved":
        return "end"
    return "revise"


workflow = StateGraph(PingPinGoState)
workflow.add_node("compliance_check", compliance_node)
workflow.add_node("seo_extraction", seo_extraction_node)
workflow.add_node("listing_draft", listing_draft_node)
workflow.add_node("audit", audit_node)
workflow.add_node("delivery", final_delivery_node)
workflow.add_node("human_intervention", human_intervention_node)
workflow.add_node("final_delivery_approval", human_delivery_approval_node)
workflow.set_entry_point("compliance_check")
workflow.add_conditional_edges(
    "compliance_check",
    should_proceed_after_compliance,
    {
        "proceed": "seo_extraction",
        "end": END
    }
)
workflow.add_edge("seo_extraction", "listing_draft")
workflow.add_edge("listing_draft", "audit")
workflow.add_conditional_edges(
    "audit",
    should_continue_after_audit,
    {
        "complete": "delivery",
        "revise": "listing_draft",
        "human_intervention": "human_intervention"
    }
)
workflow.add_edge("human_intervention", "audit")
workflow.add_edge("delivery", "final_delivery_approval")
workflow.add_node("write_raw_description", write_raw_description_node)
workflow.add_conditional_edges(
    "final_delivery_approval",
    should_continue_after_final_delivery,
    {
        "revise": "listing_draft",
        "end": "write_raw_description"
    }
)
workflow.add_edge("write_raw_description", END)

app = workflow.compile(checkpointer=checkpointer)

def build_initial_state(
    user_ideas: str,
    sku: str,
    competitor_data: str = "",
    tone_preference: str = "",
    product_category: str = "",
) -> dict:
    return {
        "messages": [HumanMessage(content=user_ideas)],
        "sku": sku,
        "user_ideas": user_ideas,
        "competitor_data": competitor_data,
        "product_category": product_category,
        "tone_preference": tone_preference,
        "retry_count": 0,
    }

def build_rewrite_initial_state(rewrite: SkuDescriptionRewrite) -> dict:
    return {
        "messages": [HumanMessage(content=rewrite.description)],
        "sku": rewrite.sku_sk,
        "user_ideas": rewrite.description,
        "competitor_data": "",
        "product_category": "",
        "tone_preference": rewrite.tone,
        "retry_count": 0,
        "keyword_list": rewrite.keywords
    }

if __name__ == "__main__":
    print("=== Pingpin Etsy Listing Agent ===\n")
    user_ideas = sanitize_text(
        input("Please enter your product concept/idea (e.g., a cute cat enamel pin for daily wear): ").strip())
    sku = sanitize_text(input("Please enter the SKU number (e.g., ENAMEL-CAT-001): ").strip())
    competitor_data = sanitize_text(input("Please enter competitor reference text (press Enter to skip): ").strip())
    tone_preference = sanitize_text(
        input("Please enter your preferred listing tone (press Enter for auto-detection): ").strip())
    product_type = sanitize_text(
        input("Please confirm product type (e.g., Hardware, Accessory, Handcrafted): ").strip())
    initial_state = build_initial_state(
        user_ideas=user_ideas,
        sku=sku,
        competitor_data=competitor_data,
        tone_preference=tone_preference,
        product_category=product_type,
    )

    config = {"configurable": {"thread_id": sku or "default-thread"}}

    print("\n=== Final State ===")

    def run_and_print(input_or_command):
        for step in app.stream(input_or_command, config=config, stream_mode="updates"):
            for node_name, node_output in step.items():
                if node_name == "__interrupt__":
                    continue  # Interrupt info is handled separately
                print(f"--- Node: {node_name} ---")
                if not node_output:
                    print("  (no state update)\n")
                    continue
                for key, value in node_output.items():
                    if key == "messages":
                        continue
                    print(f"  {key}: {value}")
                print()
        return app.get_state(config)

    state_snapshot = run_and_print(initial_state)

    while state_snapshot.tasks and any(t.interrupts for t in state_snapshot.tasks):
        interrupt_obj = state_snapshot.tasks[0].interrupts[0]
        payload = interrupt_obj.value
        # === Human-in-the-Loop in A5 Final Delivery Approval ===
        if "preview" in payload:
            print("\n" + "=" * 50)
            print("🔍 FINAL LISTING PREVIEW")
            print("=" * 50)

            preview = payload.get("preview", {})
            print(f"Title: {preview.get('title')}")
            print(f"Description:\n{preview.get('description')}")

            decision = input("\nAre you satisfied with the result? (y/n): ").strip().lower()

            if decision == 'y':
                resume_payload = {"final_approval": "approved"}
            else:
                feedback = input("What are you dissatisfied with, or how would you like it changed?: ")
                resume_payload = {
                    "final_approval": "revise",
                    "system_feedback": sanitize_text(f"Final Delivery rejected by user. Feedback: {feedback}")
                }
        else:
            # === Human-in-the-Loop in A4 Audit ====
            print("\n" + "=" * 50)
            print("⚠️  Human-in-the-Loop: Audit Failed")
            print("=" * 50)
            print(f"\nReason for Rejection:\n  {payload.get('reason', '')}")
            print(f"\nCurrent Title:\n  {payload.get('current_title', '')}")
            print(f"\nCurrent Description:\n  {payload.get('current_description', '')}")

            print("\nPlease provide corrected content (press Enter to keep existing values):")
            new_title = input("Corrected Title: ").strip()
            new_description = input("Corrected Description: ").strip()

            resume_payload = {
                "final_title": sanitize_text(new_title or payload.get("current_title", "")),
                "final_description": sanitize_text(new_description or payload.get("current_description", "")),
            }
        state_snapshot = None
        print(f"\nResuming graph execution...")
        for step in app.stream(Command(resume=resume_payload), config=config, stream_mode="updates"):
            for node_name, node_output in step.items():
                if node_name == "__interrupt__":
                    continue
                print(f"--- Node: {node_name} completed ---")
        state_snapshot = app.get_state(config)
