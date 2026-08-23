-- Bridge_Film_Actor — factless bridge for the film <-> actor many-to-many relationship.
-- Needed because a film can have many actors, so actor can't join directly onto Fact_Rental.

select
    df.film_key,
    da.actor_key
from {{ ref('stg_film_actor') }} fa
inner join {{ ref('dim_film') }} df on fa.film_id = df.film_id
inner join {{ ref('dim_actor') }} da on fa.actor_id = da.actor_id