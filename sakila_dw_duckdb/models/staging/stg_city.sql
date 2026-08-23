-- Staging model for the raw `city` seed (source: raw_data_DVD / Sakila)
select
    city_id::integer as city_id,
    city,
    country_id::integer as country_id,
    last_update::timestamp as last_update,
    current_timestamp as _loaded_at
from {{ ref('city') }}