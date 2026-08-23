-- Singular test: a payment amount must never be negative.
-- dbt fails this test if the query below returns any row.
select
    payment_id,
    amount
from {{ ref('stg_payment') }}
where amount < 0

