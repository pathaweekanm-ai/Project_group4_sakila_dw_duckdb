-- Ad-hoc check (not built as a table/view): does every inventory row belong to
-- a film and store that actually exist? Useful before trusting inventory-utilization
-- numbers for BQ09/BQ10.
select
    inv.inventory_id,
    inv.film_id,
    inv.store_id
from {{ ref('stg_inventory') }} inv
left join {{ ref('stg_film') }} f on inv.film_id = f.film_id
left join {{ ref('stg_store') }} s on inv.store_id = s.store_id
where f.film_id is null
   or s.store_id is null