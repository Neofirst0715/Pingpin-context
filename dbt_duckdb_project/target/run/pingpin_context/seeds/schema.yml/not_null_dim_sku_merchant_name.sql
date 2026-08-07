
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select merchant_name
from "dev"."main"."dim_sku"
where merchant_name is null



  
  
      
    ) dbt_internal_test