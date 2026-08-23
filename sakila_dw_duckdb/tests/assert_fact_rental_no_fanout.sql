-- Tests that fact_rental has no row fanout after staging/dimension joins.
-- Fails (returns a row) if the counts differ.

with staging_count as (
    select count(*) as cnt from {{ ref('stg_rental') }}
),

fact_count as (
    select count(*) as cnt from {{ ref('fact_rental') }}
)

select
    s.cnt as staging_cnt,
    f.cnt as fact_cnt
from staging_count s
cross join fact_count f
where s.cnt != f.cnt