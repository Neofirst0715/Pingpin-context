{% snapshot description_history %}
{{ config(
   target_schema = 'snapshot',
   unique_key = 'sku_sk',
   strategy = 'check',
   check_cols = ['description_text']
)}}
select sku_sk, description_text, generated_at
from{{ ref('raw_description_updates') }}
{% endsnapshot %}