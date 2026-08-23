-- Staging model for the raw `staff` seed (source: raw_data_DVD / Sakila)
select
    staff_id::integer as staff_id,
    first_name,
    last_name,
    address_id::integer as address_id,
    email,
    store_id::integer as store_id,
    active::boolean as active,
    username,
    last_update::timestamp as last_update,
    current_timestamp as _loaded_at
from {{ ref('staff') }}