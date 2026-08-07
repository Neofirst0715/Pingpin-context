
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select generated_at
from "dev"."main"."raw_description_updates_seed"
where generated_at is null



  
  
      
    ) dbt_internal_test