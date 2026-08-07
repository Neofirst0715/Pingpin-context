
    
    

select
    sku_sk as unique_field,
    count(*) as n_records

from "dev"."main"."dim_sku"
where sku_sk is not null
group by sku_sk
having count(*) > 1


