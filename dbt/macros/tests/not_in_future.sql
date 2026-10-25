{#- Fails for rows where a timestamp/date lies in the future (beyond a small tolerance
    for clock skew between DIP and us). -#}
{% test not_in_future(model, column_name, tolerance_hours=1) %}
    select {{ column_name }}
    from {{ model }}
    where {{ column_name }} > now() + interval ({{ tolerance_hours }}) hour
{% endtest %}
