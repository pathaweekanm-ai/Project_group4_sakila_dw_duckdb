-- Staging model for the raw `rental` seed (source: raw_data_DVD / Sakila)
select
    rental_id::integer as rental_id,
    rental_date::timestamp as rental_date,
    inventory_id::integer as inventory_id,
    customer_id::integer as customer_id,
    return_date::timestamp as return_date,
    staff_id::integer as staff_id,
    last_update::timestamp as last_update,
    current_timestamp as _loaded_at
from {{ ref('rental') }}