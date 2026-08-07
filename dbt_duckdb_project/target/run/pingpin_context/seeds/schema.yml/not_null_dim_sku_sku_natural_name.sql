
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select sku_natural_name
from "dev"."main"."dim_sku"
where sku_natural_name is null



  
  
      
    ) dbt_internal_test