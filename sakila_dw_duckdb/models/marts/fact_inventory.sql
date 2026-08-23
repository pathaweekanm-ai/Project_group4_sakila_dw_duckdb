-- Fact_Inventory — grain: 1 row = 1 film x 1 store (different grain from Fact_Rental,
-- which is why this is a separate fact table). Answers BQ09 (utilization) / BQ10 (stock shortage).

with inv_counts as (
    select
        df.film_key,
        ds.store_key,
        count(*) as inventory_count
    from {{ ref('stg_inventory') }} inv
    inner join {{ ref('dim_film') }} df on inv.film_id = df.film_id
    inner join {{ ref('dim_store') }} ds on inv.store_id = ds.store_id
    group by 1, 2
),

rental_counts as (
    select
        film_key,
        store_key,
        count(*) as rental_count_to_date
    from {{ ref('fact_rental') }}
    group by 1, 2
)

select
    ic.film_key,
    ic.store_key,
    ic.inventory_count,
    coalesce(rc.rental_count_to_date, 0) as rental_count_to_date,
    round(coalesce(rc.rental_count_to_date, 0)::decimal / nullif(ic.inventory_count, 0), 2) as utilization_ratio
from inv_counts ic
left join rental_counts rc on ic.film_key = rc.film_key and ic.store_key = rc.store_key