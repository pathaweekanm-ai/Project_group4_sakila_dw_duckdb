-- Dim_Staff — 1 row per staff member.

select
    row_number() over (order by staff_id) as staff_key,
    staff_id,
    first_name || ' ' || last_name as full_name,
    store_id
from {{ ref('stg_staff') }}