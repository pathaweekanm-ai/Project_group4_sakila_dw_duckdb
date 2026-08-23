-- Dim_Customer — 1 row per customer, with city/country flattened in (star schema).

select
    row_number() over (order by c.customer_id) as customer_key,
    c.customer_id,
    c.first_name || ' ' || c.last_name as full_name,
    c.email,
    ci.city,
    co.country,
    c.active as active_flag,
    c.store_id as home_store_id
from {{ ref('stg_customer') }} c
left join {{ ref('stg_address') }} a on c.address_id = a.address_id
left join {{ ref('stg_city') }} ci on a.city_id = ci.city_id
left join {{ ref('stg_country') }} co on ci.country_id = co.country_id