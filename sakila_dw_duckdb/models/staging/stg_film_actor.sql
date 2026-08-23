-- Staging model for the raw `film_actor` seed (source: raw_data_DVD / Sakila)
select
    actor_id::integer as actor_id,
    film_id::integer as film_id,
    last_update::timestamp as last_update,
    current_timestamp as _loaded_at
from {{ ref('film_actor') }}