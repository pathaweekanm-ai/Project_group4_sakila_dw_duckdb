-- Staging model for the raw `inventory` seed (source: raw_data_DVD / Sakila)
select
    inventory_id::integer as inventory_id,
    film_id::integer as film_id,
    store_id::integer as store_id,
    last_update::timestamp as last_update,
    current_timestamp as _loaded_at
from {{ ref('inventory') }}