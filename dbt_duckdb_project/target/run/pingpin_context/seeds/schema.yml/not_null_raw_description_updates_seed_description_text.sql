
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select description_text
from "dev"."main"."raw_description_updates_seed"
where description_text is null



  
  
      
    ) dbt_internal_test