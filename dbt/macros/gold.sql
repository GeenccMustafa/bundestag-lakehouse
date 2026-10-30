{#- Helpers shared by the Gold layer. -#}

{#- Integer date key YYYYMMDD for dim_date; unknown dates map to the -1 member. -#}
{% macro date_key(expr) %}
    coalesce(cast(strftime({{ expr }}, '%Y%m%d') as integer), -1)
{% endmacro %}


{#- Fraktion name from a Drucksache originator ("Fraktion der AfD" -> "AfD",
    "Fraktion BÜNDNIS 90/DIE GRÜNEN" -> "BÜNDNIS 90/DIE GRÜNEN"); NULL for non-Fraktionen.
    Gives the same spelling DIP uses in activity titles and person roles. -#}
{% macro fraktion_from_urheber(expr) %}
    case
        when {{ expr }} like 'Fraktion %' then regexp_replace({{ expr }}, '^Fraktion (der )?', '')
    end
{% endmacro %}


{#- Key of the "unknown" member every dimension carries, so facts never have NULL keys. -#}
{% macro unknown_key() %}'-1'{% endmacro %}
