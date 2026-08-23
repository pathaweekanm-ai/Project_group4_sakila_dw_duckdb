-- Staging model for the raw `category` seed (source: raw_data_DVD / Sakila)
select
    category_id::integer as category_id,
    name,
    last_update::timestamp as last_update,
    current_timestamp as _loaded_at
from {{ ref('category') }}