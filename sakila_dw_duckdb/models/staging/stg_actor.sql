-- Staging model for the raw `actor` seed (source: raw_data_DVD / Sakila)
select
    actor_id::integer as actor_id,
    first_name,
    last_name,
    last_update::timestamp as last_update,
    current_timestamp as _loaded_at
from {{ ref('actor') }}