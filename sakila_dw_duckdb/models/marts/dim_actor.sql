-- Dim_Actor — 1 row per actor. No hierarchy levels above this — flat dimension.

select
    row_number() over (order by actor_id) as actor_key,
    actor_id,
    first_name,
    last_name
from {{ ref('stg_actor') }