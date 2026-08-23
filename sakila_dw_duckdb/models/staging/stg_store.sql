-- Staging model for the raw `store` seed (source: raw_data_DVD / Sakila)
select
    store_id::integer as store_id,
    manager_staff_id::integer as manager_staff_id,
    address_id::integer as address_id,
    last_update::timestamp as last_update,
    current_timestamp as _loaded_at
from {{ ref('store') }}