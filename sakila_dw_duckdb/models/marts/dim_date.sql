-- Dim_Date — role-playing dimension, joined 3x from Fact_Rental
-- (rental_date_key / return_date_key / payment_date_key).
-- Range padded slightly around the real data span (2005-05-24 to 2006-02-14).
-- date_key = -1 is a placeholder row for nullable FKs (not-yet-returned / not-yet-paid rentals)
-- so Fact_Rental never needs a NULL foreign key — standard Kimball practice.

with calendar as (
    select full_date
    from generate_series(date '2005-05-01', date '2006-02-28', interval 1 day) as t(full_date)
),

dates as (
    select
        cast(strftime(full_date, '%Y%m%d') as integer) as date_key,
        full_date,
        strftime(full_date, '%A') as day_of_week_name,
        strftime(full_date, '%w') in ('0', '6') as is_weekend,
        cast(strftime(full_date, '%W') as integer) as week_of_year,
        cast(strftime(full_date, '%m') as integer) as month,
        strftime(full_date, '%B') as month_name,
        cast(ceil(cast(strftime(full_date, '%m') as integer) / 3.0) as integer) as quarter,
        cast(strftime(full_date, '%Y') as integer) as year
    from calendar
),

unknown as (
    select
        -1 as date_key,
        cast(null as date) as full_date,
        'N/A' as day_of_week_name,
        cast(null as boolean) as is_weekend,
        cast(null as integer) as week_of_year,
        cast(null as integer) as month,
        'N/A' as month_name,
        cast(null as integer) as quarter,
        cast(null as integer) as year
)

select * from dates
union all
select * from unknown