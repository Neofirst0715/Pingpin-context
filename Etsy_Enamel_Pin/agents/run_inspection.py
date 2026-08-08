import os
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "..", "..", "dbt_duckdb_project", "seeds", "dev.duckdb")
DB_PATH = os.path.abspath(DB_PATH)

from inspect_report_schema import (
    query_stale_descriptions,
    report_stale_descriptions,
    preview_stale_descriptions,
    inspect_app,
    build_rewrite_node,
)
from report_schema import SkuDescriptionHumaninLoop
from main import app, build_rewrite_initial_state, sanitize_text
from langgraph.types import Command

results = query_stale_descriptions(
    database_path=DB_PATH,
    threshold_days=1
)

reports = report_stale_descriptions(results, 1)
preview_list = preview_stale_descriptions(reports)

# === human_preview_node runs on its own mini graph (inspect_app), separate
# from main.py's A1-A5 workflow, since interrupt() needs a runnable context ===
inspect_config = {"configurable": {"thread_id": "inspect_agent_run"}}
for _ in inspect_app.stream({"preview_list": preview_list}, config=inspect_config, stream_mode="updates"):
    pass

inspect_state = inspect_app.get_state(inspect_config)
interrupt_obj = inspect_state.tasks[0].interrupts[0]
preview = interrupt_obj.value.get("preview", {})

print("\n" + "=" * 50)
print("🔍 STALE DESCRIPTION INSPECTION REPORT")
print("=" * 50)
for item in preview.get("preview_list", []):
    print(f"  {item['sku_sk']}: {item['reason']}")

selected = input("\nWhich SKUs do you want to rewrite? (comma-separated, e.g. S001,S003): ").strip()
selected_list = [s.strip() for s in selected.split(",") if s.strip()]

keywords_input = input("Enter keywords (comma-separated): ").strip()
keywords_list = [k.strip() for k in keywords_input.split(",") if k.strip()]

tone_input = input("Enter tone preference (press Enter for default): ").strip()

resume_payload = {
    "selected_skus": selected_list,
    "keyword_list": keywords_list,
    "tone_preference": tone_input or "professional and friendly"
}
for _ in inspect_app.stream(Command(resume=resume_payload), config=inspect_config, stream_mode="updates"):
    pass

inspect_result = inspect_app.get_state(inspect_config).values
selected_skus = inspect_result.get("selected_skus", [])
human_response = SkuDescriptionHumaninLoop(
    keyword_list=inspect_result.get("keyword_list", []),
    tone_preference=inspect_result.get("tone_preference", "professional and friendly")
)
rewrite_list = build_rewrite_node(reports, human_response, selected_skus)

def run_and_print(input_or_command,config):
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
for rewrite in rewrite_list:
    rewrite_initial_state = build_rewrite_initial_state(rewrite)
    config = {"configurable": {"thread_id": rewrite.sku_sk }}
    state_snapshot = run_and_print(rewrite_initial_state, config)
    while state_snapshot.tasks and any(t.interrupts for t in state_snapshot.tasks):
        interrupt_obj = state_snapshot.tasks[0].interrupts[0]
        payload = interrupt_obj.value
        # === Human-in-the-Loop in A5 Final Delivery Approval ===
        if "preview" in payload:
            preview = payload.get("preview", {})

            if preview.get("source") == "inspect_agent":
                print("\n" + "=" * 50)
                print("🔍 STALE DESCRIPTION INSPECTION REPORT")
                print("=" * 50)

                for item in preview.get("preview_list", []):
                    print(f"  {item['sku_sk']}: {item['reason']}")

                selected = input("\nWhich SKUs do you want to rewrite? (comma-separated, e.g. S001,S003): ").strip()
                selected_list = [s.strip() for s in selected.split(",") if s.strip()]

                keywords_input = input("Enter keywords (comma-separated): ").strip()
                keywords_list = [k.strip() for k in keywords_input.split(",") if k.strip()]

                tone_input = input("Enter tone preference (press Enter for default): ").strip()

                resume_payload = {
                    "selected_skus": selected_list,
                    "keyword_list": keywords_list,
                    "tone_preference": tone_input or "professional and friendly"
                }
            else:
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
