-- Dim_Store — 1 row per store, with the manager's name and store address flattened in.

select
    row_number() over (order by s.store_id) as store_key,
    s.store_id,
    a.address,
    ci.city,
    co.country,
    mgr.first_name || ' ' || mgr.last_name as manager_name
from {{ ref('stg_store') }} s
left join {{ ref('stg_staff') }} mgr on s.manager_staff_id = mgr.staff_id
left join {{ ref('stg_address') }} a on s.address_id = a.address_id
left join {{ ref('stg_city') }} ci on a.city_id = ci.city_id
left join {{ ref('stg_country') }} co on ci.country_id = co.country_id