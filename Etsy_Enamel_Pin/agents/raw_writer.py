import os
import duckdb

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "dbt_duckdb_project", "seeds", "dev.duckdb"))

def get_or_create_sku_id(db_con, merchant_name, sku_natural_name, category):
    existing = db_con.execute(
        "SELECT sku_sk FROM dim_sku WHERE merchant_name = ? AND sku_natural_name = ?",
        [merchant_name, sku_natural_name]
    ).fetchone()
    if existing:
        return existing[0]
    new_sku = f"SK{db_con.execute('SELECT COUNT(*) FROM dim_sku').fetchone()[0] + 1:03d}"
    db_con.execute(
        "INSERT INTO dim_sku(sku_sk, merchant_name, sku_natural_name, category, create_time) VALUES (?, ?, ?, ?,CURRENT_TIMESTAMP)",
        [new_sku, merchant_name, sku_natural_name, category]
    )
    return new_sku

def write_raw_description_node(state) -> dict:
    db_con = duckdb.connect(DB_PATH)
    sku_value = state["sku"]
    category = state.get("category", "")
    final_desc = f"{state.get('final_title', '')} {state.get('final_description', '')}"
    existing = db_con.execute(
        "SELECT sku_sk FROM dim_sku WHERE sku_sk = ?", [sku_value]
    ).fetchone()
    if existing:
        sku_sk = existing[0]
    else:
        sku_sk = get_or_create_sku_id(db_con, "Pingpin", sku_value, category)
    db_con.execute(
        "INSERT INTO raw_description_updates (sku_sk, description_text, generated_at, source) VALUES (?, ?, CURRENT_TIMESTAMP, 'pingpin_a5')",
        [sku_sk, final_desc]
    )
    db_con.close()
    print(f"Writing {final_desc} to {sku_sk}")
    return state
