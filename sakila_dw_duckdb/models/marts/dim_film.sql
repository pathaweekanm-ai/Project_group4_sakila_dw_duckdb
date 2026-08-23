-- Dim_Film — 1 row per film, category flattened in (star schema, not snowflake).
-- Confirmed against the loaded data: every film has exactly 1 category, so this
-- join never fans out a film into duplicate rows.

select
    row_number() over (order by f.film_id) as film_key,
    f.film_id,
    f.title,
    cat.name as category,
    f.rating,
    f.length,
    f.rental_duration,
    f.rental_rate,
    f.release_year
from {{ ref('stg_film') }} f
left join {{ ref('stg_film_category') }} fc on f.film_id = fc.film_id
left join {{ ref('stg_category') }} cat on fc.category_id = cat.category_id