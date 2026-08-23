-- Fact_Rental — grain: 1 row = 1 rental transaction (rental.rental_id).
-- Confirmed against the loaded data: every rental has exactly 0 or 1 payment
-- (no fan-out), so the left join to payment is safe without an aggregation step.
-- date_key = -1 (the Dim_Date placeholder row) stands in for nullable return/payment dates
-- so no foreign key here is ever NULL.

select
    r.rental_id,
    r.inventory_id,

    cast(strftime(r.rental_date, '%Y%m%d') as integer) as rental_date_key,
    coalesce(cast(strftime(r.return_date, '%Y%m%d') as integer), -1) as return_date_key,
    coalesce(cast(strftime(p.payment_date, '%Y%m%d') as integer), -1) as payment_date_key,

    dc.customer_key,
    df.film_key,
    ds.store_key,
    dst.staff_key,

    1 as rental_count,
    coalesce(p.amount, 0) as payment_amount,
    {{ days_between('r.return_date', 'r.rental_date') }} as rental_duration_actual_days,
    {{ days_between('r.return_date', 'r.rental_date') }} - df.rental_duration as days_late,
    {{ days_between('p.payment_date', 'r.rental_date') }} as payment_lag_days,
    (r.return_date is not null) as is_returned

from {{ ref('stg_rental') }} r
left join {{ ref('stg_payment') }} p on r.rental_id = p.rental_id
inner join {{ ref('stg_inventory') }} inv on r.inventory_id = inv.inventory_id
inner join {{ ref('dim_film') }} df on inv.film_id = df.film_id
inner join {{ ref('dim_store') }} ds on inv.store_id = ds.store_id
inner join {{ ref('dim_customer') }} dc on r.customer_id = dc.customer_id
inner join {{ ref('dim_staff') }} dst on r.staff_id = dst.staff_id