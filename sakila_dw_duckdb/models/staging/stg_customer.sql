-- Staging model for the raw `customer` seed (source: raw_data_DVD / Sakila)
select
    customer_id::integer as customer_id,
    store_id::integer as store_id,
    first_name,
    last_name,
    email,
    address_id::integer as address_id,
    active::boolean as active,
    create_date::timestamp as create_date,
    last_update::timestamp as last_update,
    current_timestamp as _loaded_at
from {{ ref('customer') }}