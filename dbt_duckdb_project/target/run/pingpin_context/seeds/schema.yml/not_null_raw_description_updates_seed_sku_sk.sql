
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select sku_sk
from "dev"."main"."raw_description_updates_seed"
where sku_sk is null



  
  
      
    ) dbt_internal_test