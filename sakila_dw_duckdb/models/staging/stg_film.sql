-- Staging model for the raw `film` seed (source: raw_data_DVD / Sakila)
select
    film_id::integer as film_id,
    title,
    description,
    release_year::integer as release_year,
    language_id::integer as language_id,
    original_language_id::integer as original_language_id,
    rental_duration::integer as rental_duration,
    rental_rate::decimal(4,2) as rental_rate,
    length::integer as length,
    replacement_cost::decimal(5,2) as replacement_cost,
    rating,
    special_features,
    last_update::timestamp as last_update,
    current_timestamp as _loaded_at
from {{ ref('film') }}