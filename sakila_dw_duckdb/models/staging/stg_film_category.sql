-- Staging model for the raw `film_category` seed (source: raw_data_DVD / Sakila)
select
    film_id::integer as film_id,
    category_id::integer as category_id,
    last_update::timestamp as last_update,
    current_timestamp as _loaded_at
from {{ ref('film_category') }}