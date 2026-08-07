

    insert into "dev"."main"."raw_description_updates" ("sku_sk", "description_text", "generated_at", "source")
    (
        select "sku_sk", "description_text", "generated_at", "source"
        from "raw_description_updates__dbt_tmp20260806101626931223"
    )
  