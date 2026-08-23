{#
  SCD Type 2 snapshot of customer — tracks changes to store_id / address_id / active
  over time (e.g. a customer moves home store, changes address, or is deactivated).
  Uses the timestamp strategy on last_update, which Sakila already maintains per row.
  Meaningful once this pipeline is re-run periodically against a live source; a single
  run against a static CSV export just creates the first snapshot version.
#}
{% snapshot customer_snapshot %}

{{
    config(
        target_schema='snapshots',
        unique_key='customer_id',
        strategy='timestamp',
        updated_at='last_update',
    )
}}

select
    customer_id,
    store_id,
    first_name,
    last_name,
    email,
    address_id,
    active,
    create_date,
    last_update
from {{ ref('stg_customer') }}

{% endsnapshot %}