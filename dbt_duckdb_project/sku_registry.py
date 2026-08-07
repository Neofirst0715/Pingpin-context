import duckdb
from datetime import datetime

def get_or_create_sku_id(con, merchant_name:str, sku_natural_name: str, category: str) -> str:
    existing = con.execute(
        "SELECT sku_sk FROM dim_sku WHERE merchant_name = ? AND sku_natural_name = ?",
        [merchant_name, sku_natural_name]
    ).fetchone()
    if existing:
        return existing[0]
    new_sku = f"SK{con.execute('SELECT COUNT(*) FROM dim_sku').fetchone()[0] + 1:03d}"
    con.execute(
        "INSERT INTO dim_sku(sku_sk, merchant_name, sku_natural_name, category, create_time) VALUES (?, ?, ?, ?,CURRENT_TIMESTAMP)",
        [new_sku, merchant_name, sku_natural_name, category]
    )
    return new_sku
con = duckdb.connect("dev.duckdb")
if __name__ == '__main__':
    print("Test1: Repeating of the same sku in the same merchant")
    s1 = get_or_create_sku_id(con,"Pingpin", "Gold Deer Enamel Pin", "Brooch&Pin")
    s2 =  get_or_create_sku_id(con,"Pingpin", "Gold Deer Enamel Pin", "Brooch&Pin")
    print(f"{s1 == s2}")
    print("Test2: Repeating of the same sku in the different merchants")
    s3 = get_or_create_sku_id(con,"Pingpin1", "Gold Deer Enamel Pin", "Brooch&Pin")
    print(f"{s1 != s3}")
    print("Test3: Add new sku")
    s4 = get_or_create_sku_id(con, "Pingpin", "Unicorn", "Brooch&Pin")

