-- Staging model for the raw `address` seed (source: raw_data_DVD / Sakila)
select
    address_id::integer as address_id,
    address,
    address2,
    district,
    city_id::integer as city_id,
    postal_code,
    phone,
    last_update::timestamp as last_update,
    current_timestamp as _loaded_at
from {{ ref('address') }}