{#- SCD2 integrity for a dimension with valid_from / valid_to / is_current:
    each natural key has exactly one current version, no version has an empty or negative
    range, and versions of the same key don't overlap. Returns offending keys. -#}
{% test scd2_valid_ranges(model, natural_key) %}
    with versions as (
        select
            {{ natural_key }} as natural_key,
            valid_from,
            valid_to,
            is_current,
            lead(valid_from) over (
                partition by {{ natural_key }} order by valid_from
            ) as next_valid_from
        from {{ model }}
        where {{ natural_key }} is not null
    )

    select natural_key, 'not exactly one current version' as problem
    from versions
    group by natural_key
    having count(*) filter (where is_current) != 1

    union all

    select natural_key, 'valid_from >= valid_to'
    from versions
    where valid_from >= valid_to

    union all

    select natural_key, 'overlaps the next version'
    from versions
    where next_valid_from is not null and valid_to > next_valid_from
{% endtest %}
