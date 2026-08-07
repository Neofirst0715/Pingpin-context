
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  





with validation_errors as (

    select
        merchant_name, sku_natural_name
    from "dev"."main"."dim_sku"
    group by merchant_name, sku_natural_name
    having count(*) > 1

)

select *
from validation_errors



  
  
      
    ) dbt_internal_test