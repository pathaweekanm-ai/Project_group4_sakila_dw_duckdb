{#
  Reusable macro: number of whole days between two timestamp columns.
  Used across staging/marts instead of repeating DATE_DIFF everywhere, e.g.:
    - rental.return_date - rental.rental_date   -> actual rental duration
    - payment.payment_date - rental.rental_date -> payment lag (BQ15)
#}
{% macro days_between(end_date_column, start_date_column) %}
    date_diff('day', {{ start_date_column }}, {{ end_date_column }})
{% endmacro %}