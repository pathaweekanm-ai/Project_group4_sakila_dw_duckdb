-- Staging model for the raw `country` seed (source: raw_data_DVD / Sakila)
select
    country_id::integer as country_id,
    country,
    last_update::timestamp as last_update,
    current_timestamp as _loaded_at
from {{ ref('country') }}