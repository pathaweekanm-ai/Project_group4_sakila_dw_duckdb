-- Staging model for the raw `payment` seed (source: raw_data_DVD / Sakila)
select
    payment_id::integer as payment_id,
    customer_id::integer as customer_id,
    staff_id::integer as staff_id,
    rental_id::integer as rental_id,
    amount::decimal(5,2) as amount,
    payment_date::timestamp as payment_date,
    last_update::timestamp as last_update,
    current_timestamp as _loaded_at
from {{ ref('payment') }}