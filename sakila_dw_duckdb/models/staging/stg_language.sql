select
    language_id::integer as language_id,
    name,
    last_update::timestamp as last_update,
    current_timestamp as _loaded_at
from {{ ref('language') }}