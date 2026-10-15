from typing import Any


# ============================================================
# Supported evaluator schema
# ============================================================

ENTITY_PROPERTIES = {

    "circle": {
        "center_x": "number",
        "center_y": "number",
        "center_z": "number",
        "radius": "number",
        "diameter": "number",
        "area": "number",
        "circumference": "number",
        "layer": "text",
        "linetype": "text",
        "linetype_scale": "number",
        "color": "number",
        "lineweight": "number",
    },

    "line": {
        "start_x": "number",
        "start_y": "number",
        "start_z": "number",
        "end_x": "number",
        "end_y": "number",
        "end_z": "number",
        "length": "number",
        "angle": "number",
        "layer": "text",
        "linetype": "text",
        "linetype_scale": "number",
        "color": "number",
        "lineweight": "number",
    },

    "polyline": {
        "length": "number",
        "area": "number",
        "closed": "bool",
        "vertex_count": "integer",
        "segment_lengths": "number_list",
        "layer": "text",
        "linetype": "text",
        "linetype_scale": "number",
        "color": "number",
        "lineweight": "number",
    },

    "dimension": {
        "measurement": "number",
        "text_override": "text",
        "style_name": "text",
        "layer": "text",
        "linetype": "text",
        "color": "number",
    },

    "hatch": {
        "pattern_name": "text",
        "pattern_scale": "number",
        "pattern_angle": "number",
        "area": "number",
        "associative": "bool",
        "layer": "text",
        "color": "number",
    },

    "text": {
        "text": "text",
        "height": "number",
        "rotation": "number",
        "insertion_x": "number",
        "insertion_y": "number",
        "style_name": "text",
        "layer": "text",
    },

    "block": {
        "name": "text",
        "effective_name": "text",
        "insertion_x": "number",
        "insertion_y": "number",
        "insertion_z": "number",
        "rotation": "number",
        "x_scale": "number",
        "y_scale": "number",
        "z_scale": "number",
        "layer": "text",
    },
}


OPERATORS_BY_TYPE = {

    "number": [
        "equals",
        "greater_than",
        "greater_or_equal",
        "less_than",
        "less_or_equal",
    ],

    "integer": [
        "equals",
        "greater_than",
        "greater_or_equal",
        "less_than",
        "less_or_equal",
    ],

    "text": [
        "equals",
        "contains",
        "starts_with",
        "ends_with",
    ],

    "bool": [
        "equals",
    ],

    "number_list": [
        "contains_number",
    ],
}


RELATIONS = [
    "x_distance",
    "y_distance",
    "distance_2d",
    "same_x",
    "same_y",
]


# ============================================================
# Validation
# ============================================================

def _validate_condition(
    entity_type: str,
    condition: dict[str, Any],
) -> None:

    if (
        entity_type
        not in ENTITY_PROPERTIES
    ):

        raise ValueError(
            "Niet-ondersteund entity type: "
            f"{entity_type}"
        )

    prop = condition.get(
        "property"
    )

    if (
        prop
        not in ENTITY_PROPERTIES[
            entity_type
        ]
    ):

        raise ValueError(
            "Niet-ondersteunde property "
            f"'{prop}' voor entity "
            f"'{entity_type}'."
        )

    datatype = (
        ENTITY_PROPERTIES[
            entity_type
        ][prop]
    )

    operator = (
        condition.get(
            "operator"
        )
    )

    if (
        operator
        not in OPERATORS_BY_TYPE[
            datatype
        ]
    ):

        raise ValueError(
            "Niet-ondersteunde operator "
            f"'{operator}' voor "
            f"property '{prop}'."
        )


def validate_generated_config(
    config: dict[str, Any],
) -> dict[str, Any]:

    if not isinstance(
        config,
        dict,
    ):

        raise ValueError(
            "Configuratie moet een "
            "JSON-object zijn."
        )

    criteria = (
        config.get(
            "criteria"
        )
    )

    if not isinstance(
        criteria,
        list,
    ):

        raise ValueError(
            "Configuratie moet een "
            "lijst 'criteria' bevatten."
        )

    for rule in criteria:

        if not isinstance(
            rule,
            dict,
        ):

            raise ValueError(
                "Elk criterium moet een "
                "JSON-object zijn."
            )

        rule_type = (
            rule.get(
                "type"
            )
        )

        # ------------------------------------
        # Entity
        # ------------------------------------

        if rule_type == "entity":

            entity = (
                rule.get(
                    "entity"
                )
            )

            if (
                entity
                not in ENTITY_PROPERTIES
            ):

                raise ValueError(
                    "Niet-ondersteunde "
                    f"entity: {entity}"
                )

            conditions = (
                rule.get(
                    "conditions",
                    [],
                )
            )

            if not isinstance(
                conditions,
                list,
            ):

                raise ValueError(
                    "Entity conditions "
                    "moet een lijst zijn."
                )

            for condition in conditions:

                _validate_condition(
                    entity,
                    condition,
                )

        # ------------------------------------
        # Relation
        # ------------------------------------

        elif rule_type == "relation":
            if rule.get("relation") not in RELATIONS:
                raise ValueError(f"Niet-ondersteunde relatie: {rule.get('relation')}")
            if "object_a" in rule or "object_b" in rule:
                sources = {"circle": {"center"}, "line": {"start", "end"},
                           "text": {"insertion_point"}, "block": {"insertion_point"}}
                for side in ("object_a", "object_b"):
                    selector = rule.get(side)
                    if not isinstance(selector, dict):
                        raise ValueError(f"{side} moet een object zijn")
                    entity = selector.get("entity")
                    if entity not in sources:
                        raise ValueError(f"{side}: geen ondersteund meetpunt voor {entity}")
                    if selector.get("point_source", next(iter(sources[entity]))) not in sources[entity]:
                        raise ValueError(f"{side}: ongeldig meetpunt")
                    conditions = selector.get("conditions", [])
                    if not isinstance(conditions, list):
                        raise ValueError(f"{side}.conditions moet een lijst zijn")
                    for condition in conditions:
                        if not isinstance(condition, dict):
                            raise ValueError(f"{side}: ongeldige voorwaarde")
                        _validate_condition(entity, condition)
            elif rule.get("entity") not in ENTITY_PROPERTIES:
                raise ValueError("Legacy relatie bevat ongeldig objecttype")

        # ------------------------------------
        # Layout / file
        # ------------------------------------

        elif rule_type in ("layout", "file"):
            pass
        else:
            raise ValueError(f"Niet-ondersteund rule type: {rule_type}")

    return config
