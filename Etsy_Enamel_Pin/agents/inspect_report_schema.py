import os

from report_schema import (
    SkuDescriptionHumaninLoop,
    SkuInspectFacts,
    SkuInspectInference,
    SkuDescriptionInspectReport,
    SkuDescriptionRewrite,
)
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langgraph.types import interrupt, Command
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
import duckdb


async def connect_to_datahub_mcp():
    gms_url = os.environ.get("DATAHUB_GMS_URL")
    gms_token = os.environ.get("DATAHUB_GMS_TOKEN")
    if gms_url is None or gms_token is None:
        raise ValueError("Lack DATAHUB_GMS_URL or DATAHUB_GMS_TOKEN environment variables, please set them")
    server_params = StdioServerParameters(
        command = "uvx",
        args = ["mcp-server-datahub@latest"],
        env = {"DATAHUB_GMS_URL": gms_url, "DATAHUB_GMS_TOKEN": gms_token}
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return session

async def query_dataset_info(session, dataset_urn):
    result = await session.call_tool("get entities", dataset_urn)
    return result

#search local duckdb repository
def query_stale_descriptions (database_path, threshold_days):
    con = duckdb.connect(database_path)
    results = con.execute(
                """
                SELECT sku_sk, description_text, dbt_valid_from,
                        CURRENT_DATE - dbt_valid_from AS days_since_last_update
                FROM snapshot.description_history
                WHERE dbt_valid_to IS NULL
                AND dbt_valid_from < CURRENT_TIMESTAMP - INTERVAL (?)DAY""", [threshold_days]
                ).fetchall()
    return results

def report_stale_descriptions(results, threshold_days):
    reports = []
    for row in results:
        facts = SkuInspectFacts(
            sku_sk = row[0],
            current_description = row[1],
            last_update_date = row[2],
            days_since_update = row[3].days
        )
        inference = SkuInspectInference(
            need_refresh= True,
            reason = f"Descriptions have not yet been updated for {facts.days_since_update} days"
        )
        report = SkuDescriptionInspectReport(
            facts = facts,
            inference = inference
        )
        reports.append(report)
    return reports

def preview_stale_descriptions(reports):
    preview_list = []
    for report in reports:
        preview_item = {
            "sku_sk": report.facts.sku_sk,
            "reason": report.inference.reason
        }
        preview_list.append(preview_item)
    return preview_list

def human_preview_node(state: dict) -> dict:
    preview_data = {
        "preview_list": state["preview_list"],
        "source": "inspect_agent"
    }
    human_decision = interrupt({"preview": preview_data})
    return {
        "selected_skus": human_decision.get("selected_skus", []),
        "keyword_list": human_decision.get("keyword_list", []),
        "tone_preference": human_decision.get("tone_preference", "professional and friendly"),
    }

# Standalone, single-node graph: interrupt() only works inside a compiled
# graph's runnable context, and this inspection flow deliberately stays out
# of main.py's A1-A5 workflow, so it gets its own minimal graph.
inspect_workflow = StateGraph(dict)
inspect_workflow.add_node("human_preview_node", human_preview_node)
inspect_workflow.set_entry_point("human_preview_node")
inspect_workflow.add_edge("human_preview_node", END)
inspect_app = inspect_workflow.compile(checkpointer=MemorySaver())

def build_rewrite_node(reports, human_response,selected_skus):
    rewrite_list = []
    for row in reports:
        if row.facts.sku_sk in selected_skus:
            rewrite = SkuDescriptionRewrite(
                sku_sk = row.facts.sku_sk,
                description = row.facts.current_description,
                keywords = human_response.keyword_list,
                tone = human_response.tone_preference
            )
            rewrite_list.append(rewrite)
    return rewrite_list
