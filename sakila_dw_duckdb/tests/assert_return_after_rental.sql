-- Singular test: a rental's return_date must never be before its rental_date
-- (return_date IS NULL is fine — that just means the item hasn't come back yet).
select
    rental_id,
    rental_date,
    return_date
from {{ ref('stg_rental') }}
where return_date is not null
  and return_date < rental_date
