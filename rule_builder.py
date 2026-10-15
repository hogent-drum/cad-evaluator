import uuid
from copy import deepcopy
from typing import Any

import pandas as pd
import streamlit as st

from criteria_generator import (ENTITY_PROPERTIES, OPERATORS_BY_TYPE, RELATIONS)


# ============================================================
# Constants
# ============================================================

RULE_TYPES = {
    "Objecteigenschap": "entity",
    "Relatie tussen objecten": "relation",
    "Layout": "layout",
    "Bestand": "file",
}

RULE_TYPE_LABELS = {
    value: label
    for label, value in RULE_TYPES.items()
}

ENTITY_LABELS = {
    "circle": "Circle",
    "line": "Line",
    "polyline": "Polyline",
    "dimension": "Dimension",
    "hatch": "Hatch",
    "text": "Text",
    "block": "Block reference",
}

COUNT_OPERATORS = {
    "Minstens": "greater_or_equal",
    "Exact": "equals",
    "Maximum": "less_or_equal",
}

COUNT_OPERATOR_LABELS = {
    value: label
    for label, value in COUNT_OPERATORS.items()
}

RELATION_LABELS = {
    "x_distance": "X-afstand",
    "y_distance": "Y-afstand",
    "distance_2d": "2D-afstand",
    "same_x": "Zelfde X",
    "same_y": "Zelfde Y",
}

PROPERTY_LABELS = {
    # Circle
    "center_x": "Middelpunt X",
    "center_y": "Middelpunt Y",
    "center_z": "Middelpunt Z",
    "radius": "Radius",
    "diameter": "Diameter",
    "area": "Oppervlakte",
    "circumference": "Omtrek",

    # Line
    "start_x": "Start X",
    "start_y": "Start Y",
    "start_z": "Start Z",
    "end_x": "Eind X",
    "end_y": "Eind Y",
    "end_z": "Eind Z",
    "length": "Lengte",
    "angle": "Hoek",

    # Polyline
    "closed": "Gesloten",
    "vertex_count": "Aantal vertices",
    "segment_lengths": "Segmentlengtes",

    # Dimension
    "measurement": "Maatwaarde",
    "text_override": "Tekst override",

    # Hatch
    "pattern_name": "Arceerpatroon",
    "pattern_scale": "Arceerschaal",
    "pattern_angle": "Arceerhoek",
    "associative": "Associatief",

    # Text
    "text": "Tekst",
    "height": "Teksthoogte",
    "rotation": "Rotatie",
    "insertion_x": "Insertie X",
    "insertion_y": "Insertie Y",

    # Block
    "name": "Blocknaam",
    "effective_name": "Effectieve blocknaam",
    "insertion_z": "Insertie Z",
    "x_scale": "X schaal",
    "y_scale": "Y schaal",
    "z_scale": "Z schaal",

    # Generic
    "layer": "Layer",
    "linetype": "Linetype",
    "linetype_scale": "Linetype scale",
    "color": "Kleur",
    "lineweight": "Lineweight",
    "style_name": "Style",
}


# ============================================================
# Helpers
# ============================================================

def _new_rule_id() -> str:
    return f"rule_{uuid.uuid4().hex[:8]}"


def _unique_rule_id(config: dict[str, Any]) -> str:
    existing = {
        rule.get("id")
        for rule in config.get("criteria", [])
        if isinstance(rule, dict)
    }

    while True:
        candidate = _new_rule_id()

        if candidate not in existing:
            return candidate


def _default_rule(
    config: dict[str, Any],
    rule_type: str = "entity",
) -> dict[str, Any]:

    base = {
        "id": _unique_rule_id(config),
        "name": "Nieuw criterium",
        "type": rule_type,
        "enabled": True,
        "points": 1.0,
    }

    if rule_type == "entity":
        base.update(
            {
                "entity": "circle",
                "conditions": [
                    {
                        "property": "radius",
                        "operator": "equals",
                        "value": 0.0,
                        "tolerance": 0.01,
                    }
                ],
                "count_operator": "greater_or_equal",
                "count": 1,
            }
        )

    elif rule_type == "relation":
        base.update(
            {
                "object_a": {"entity": "circle", "point_source": "center", "conditions": []},
                "object_b": {"entity": "circle", "point_source": "center", "conditions": []},
                "relation": "x_distance",
                "value": 0.0,
                "tolerance": 0.01,
            }
        )

    elif rule_type == "layout":
        base.update(
            {
                "conditions": {
                    "viewport_scale": 20.0,
                    "viewport_scale_tolerance": 1.0,
                }
            }
        )

    elif rule_type == "file":
        base.update(
            {
                "extension": ".pdf",
                "minimum_count": 1,
                "minimum_size": 0,
            }
        )

    return base


def _property_label(prop: str) -> str:
    return PROPERTY_LABELS.get(
        prop,
        prop,
    )


def _property_options(
    entity: str,
) -> list[str]:

    return list(
        ENTITY_PROPERTIES.get(
            entity,
            {},
        ).keys()
    )


def _operators_for_property(
    entity: str,
    prop: str,
) -> list[str]:

    datatype = (
        ENTITY_PROPERTIES
        .get(entity, {})
        .get(prop)
    )

    return OPERATORS_BY_TYPE.get(
        datatype,
        ["equals"],
    )


def _coerce_value(
    entity: str,
    prop: str,
    value: Any,
) -> Any:
    """
    Convert the textual value from st.data_editor back to the
    datatype expected by the evaluator.

    The value column is deliberately stored as STRING in the
    DataFrame. This avoids Streamlit's ColumnDataKind.FLOAT /
    TextColumn conflict.
    """

    datatype = (
        ENTITY_PROPERTIES
        .get(entity, {})
        .get(prop, "text")
    )

    if value is None:
        return None

    value = str(value).strip()

    if datatype == "text":
        return value

    if datatype == "number":
        return float(
            value.replace(",", ".")
        )

    if datatype == "integer":
        return int(
            float(
                value.replace(",", ".")
            )
        )

    if datatype == "bool":
        return value.lower() in {
            "true",
            "1",
            "yes",
            "ja",
            "waar",
        }

    if datatype == "number_list":
        # contains_number uses a single target number.
        return float(
            value.replace(",", ".")
        )

    return value


def _value_to_text(
    value: Any,
) -> str:

    if value is None:
        return ""

    if isinstance(value, bool):
        return (
            "true"
            if value
            else "false"
        )

    return str(value)


def _safe_index(
    options: list[Any],
    value: Any,
    default: int = 0,
) -> int:

    try:
        return options.index(
            value
        )
    except ValueError:
        return default


# ============================================================
# Rule list
# ============================================================

def _render_rule_overview(
    config: dict[str, Any],
) -> None:

    criteria = config.get(
        "criteria",
        [],
    )

    if not criteria:
        st.info(
            "Er zijn nog geen criteria."
        )
        return

    total_points = sum(
        float(
            rule.get(
                "points",
                0,
            )
        )
        for rule in criteria
        if rule.get(
            "enabled",
            True,
        )
    )

    st.caption(
        f"{len(criteria)} criteria — "
        f"{total_points:g} punten actief"
    )

    for index, rule in enumerate(
        criteria
    ):

        enabled = rule.get(
            "enabled",
            True,
        )

        symbol = (
            "✅"
            if enabled
            else "⏸️"
        )

        rule_type = (
            RULE_TYPE_LABELS.get(
                rule.get("type"),
                rule.get("type", "?"),
            )
        )

        cols = st.columns(
            [0.7, 5, 1, 1, 1, 1, 1]
        )

        with cols[0]:
            st.write(
                f"{symbol} {index + 1}"
            )

        with cols[1]:
            st.write(
                f"**{rule.get('name', 'Naamloos')}**  \n"
                f"{rule_type} · "
                f"{rule.get('points', 1):g} pt"
            )

        with cols[2]:

            if st.button(
                "Bewerk",
                key=f"edit_{rule.get('id')}_{index}",
                width='stretch',
            ):
                st.session_state["rule_editor_index"] = index
                st.session_state.pop("rule_editor_draft", None)
                st.rerun()

        with cols[3]:

            if st.button(
                "Dupliceer",
                key=f"duplicate_{rule.get('id')}_{index}",
                width='stretch',
            ):

                duplicate = deepcopy(
                    rule
                )

                duplicate["id"] = (
                    _unique_rule_id(
                        config
                    )
                )

                duplicate["name"] = (
                    f"{duplicate.get('name', 'Criterium')} kopie"
                )

                criteria.insert(
                    index + 1,
                    duplicate,
                )

                st.rerun()

        with cols[4]:
            if st.button(
                "↑",
                key=f"up_{rule.get('id')}_{index}",
                disabled=index == 0,
                width='stretch',
            ):

                criteria[
                    index - 1
                ], criteria[
                    index
                ] = (
                    criteria[index],
                    criteria[index - 1],
                )

                st.rerun()

        with cols[5]:

            if st.button(
                "↓",
                key=f"down_{rule.get('id')}_{index}",
                disabled=(index == len(criteria) - 1),
                width='stretch',
            ):

                criteria[
                    index + 1
                ], criteria[
                    index
                ] = (
                    criteria[index],
                    criteria[index + 1],
                )

                st.rerun()

        with cols[6]:

            if st.button(
                "🗑",
                key=f"delete_{rule.get('id')}_{index}",
                width='stretch',
            ):

                criteria.pop(
                    index
                )

                current = st.session_state.get(
                    "rule_editor_index"
                )

                if current == index:
                    st.session_state[
                        "rule_editor_index"
                    ] = None

                st.rerun()


# ============================================================
# Common fields
# ============================================================

def _render_common_fields(
    rule: dict[str, Any],
    key_prefix: str,
) -> None:

    rule["name"] = st.text_input(
        "Naam criterium",
        value=rule.get(
            "name",
            "",
        ),
        key=f"{key_prefix}_name",
    )

    col_enabled, col_points = (
        st.columns(2)
    )

    with col_enabled:

        rule["enabled"] = (
            st.toggle(
                "Actief",
                value=rule.get(
                    "enabled",
                    True,
                ),
                key=f"{key_prefix}_enabled",
            )
        )

    with col_points:

        rule["points"] = float(
            st.number_input(
                "Punten",
                min_value=0.0,
                value=float(
                    rule.get(
                        "points",
                        1.0,
                    )
                ),
                step=0.5,
                key=f"{key_prefix}_points",
            )
        )


# ============================================================
# Entity editor
# ============================================================

def _render_entity_editor(
    rule: dict[str, Any],
    key_prefix: str,
) -> dict[str, Any]:

    entities = list(
        ENTITY_PROPERTIES.keys()
    )

    current_entity = rule.get(
        "entity",
        "circle",
    )

    entity = st.selectbox(
        "Objecttype",
        options=entities,
        index=_safe_index(
            entities,
            current_entity,
        ),
        format_func=lambda value: (
            ENTITY_LABELS.get(
                value,
                value,
            )
        ),
        key=f"{key_prefix}_entity",
    )

    # Changing entity invalidates incompatible old conditions.
    if entity != current_entity:

        rule["entity"] = entity

        first_property = (
            _property_options(
                entity
            )[0]
        )

        st.session_state.pop(f"{key_prefix}_conditions", None)
        rule["conditions"] = [
            {
                "property":
                    first_property,

                "operator":
                    _operators_for_property(
                        entity,
                        first_property,
                    )[0],

                "value":
                    "",

                "tolerance":
                    0.01,
            }
        ]

    rule["entity"] = entity

    conditions = rule.get(
        "conditions",
        [],
    )

    property_options = (
        _property_options(
            entity
        )
    )

    rows = []

    for condition in conditions:

        prop = condition.get(
            "property"
        )

        if prop not in property_options:

            prop = (
                property_options[0]
            )

        operator_options = (
            _operators_for_property(
                entity,
                prop,
            )
        )

        operator = condition.get(
            "operator",
            operator_options[0],
        )

        if operator not in (
            operator_options
        ):

            operator = (
                operator_options[0]
            )

        rows.append(
            {
                "property":
                    prop,

                "operator":
                    operator,

                # IMPORTANT:
                # explicitly convert to text.
                "value":
                    _value_to_text(
                        condition.get(
                            "value"
                        )
                    ),

                "tolerance":
                    float(condition.get("tolerance", 0.0) or 0.0),
            }
        )

    if not rows:

        first_property = (
            property_options[0]
        )

        rows.append(
            {
                "property":
                    first_property,

                "operator":
                    _operators_for_property(
                        entity,
                        first_property,
                    )[0],

                "value":
                    "",

                "tolerance":
                    0.01,
            }
        )

    df = pd.DataFrame(
        rows
    )

    # Critical Streamlit fix:
    # don't allow pandas to infer FLOAT for the mixed value column.
    df["property"] = (
        df["property"]
        .astype("string")
    )

    df["operator"] = (
        df["operator"]
        .astype("string")
    )

    df["value"] = (
        df["value"]
        .fillna("")
        .astype("string")
    )

    df["tolerance"] = (
        pd.to_numeric(
            df["tolerance"],
            errors="coerce",
        )
        .fillna(0.0)
        .astype(float)
    )

    st.markdown(
        "**Voorwaarden voor hetzelfde object**"
    )

    edited = st.data_editor(
        df,
        num_rows="dynamic",
        width='stretch',
        hide_index=True,
        key=f"{key_prefix}_conditions",
        column_config={
            "property":
                st.column_config.SelectboxColumn(
                    "Eigenschap",
                    options=property_options,
                    required=True,
                ),

            "operator":
                st.column_config.SelectboxColumn(
                    "Operator",
                    options=sorted(
                        {
                            operator
                            for prop in property_options
                            for operator
                            in _operators_for_property(
                                entity,
                                prop,
                            )
                        }
                    ),
                    required=True,
                ),

            "value":
                st.column_config.TextColumn(
                    "Waarde",
                    required=True,
                ),

            "tolerance":
                st.column_config.NumberColumn(
                    "Tolerantie",
                    min_value=0.0,
                    step=0.01,
                    format="%.6f",
                ),
        },
    )

    parsed_conditions = []

    for _, row in (edited.iterrows()):
        prop = str(row.get("property", "")).strip()

        if (not prop or prop not in property_options):
            continue

        valid_operators = (_operators_for_property(entity, prop))

        operator = str(row.get("operator", "")).strip()

        if (operator not in valid_operators):
            # If property changed in the table, an old operator
            # can temporarily remain. Normalize it here.
            operator = (
                valid_operators[0]
            )

        raw_value = row.get(
            "value",
            "",
        )

        try:

            value = _coerce_value(
                entity,
                prop,
                raw_value,
            )

        except Exception:

            value = raw_value

        tolerance = row.get(
            "tolerance",
            0.0,
        )

        try:
            tolerance = float(
                tolerance
            )
        except Exception:
            tolerance = 0.0

        parsed_conditions.append(
            {
                "property":
                    prop,

                "operator":
                    operator,

                "value":
                    value,

                "tolerance":
                    tolerance,
            }
        )

    rule["conditions"] = (
        parsed_conditions
    )

    st.markdown(
        "**Aantal objecten dat aan alle voorwaarden moet voldoen**"
    )

    col_operator, col_count = (
        st.columns(2)
    )

    with col_operator:

        operator_values = list(
            COUNT_OPERATORS.values()
        )

        count_operator = (
            st.selectbox(
                "Aantal",
                options=operator_values,
                index=_safe_index(
                    operator_values,
                    rule.get(
                        "count_operator",
                        "greater_or_equal",
                    ),
                ),
                format_func=lambda value: (
                    COUNT_OPERATOR_LABELS.get(
                        value,
                        value,
                    )
                ),
                key=f"{key_prefix}_count_operator",
            )
        )

        rule["count_operator"] = (
            count_operator
        )

    with col_count:

        rule["count"] = int(
            st.number_input(
                "Waarde",
                min_value=0,
                value=int(
                    rule.get(
                        "count",
                        1,
                    )
                ),
                step=1,
                key=f"{key_prefix}_count",
            )
        )

    return rule


# ============================================================
# Relation editor
# ============================================================

RELATION_POINT_SOURCES = {
    "circle": {"center": "Middelpunt"},
    "line": {"start": "Beginpunt", "end": "Eindpunt"},
    "text": {"insertion_point": "Insertiepunt"},
    "block": {"insertion_point": "Insertiepunt"},
}


def _render_relation_selector(rule, side, key_prefix):
    selector = rule.setdefault(side, {"entity": "circle", "point_source": "center", "conditions": []})
    prefix = f"{key_prefix}_{side}"
    st.markdown(f"**Object {'A' if side == 'object_a' else 'B'}**")
    types = list(RELATION_POINT_SOURCES)
    old_type = selector.get("entity", "circle")
    entity = st.selectbox("Objecttype", types, index=_safe_index(types, old_type),
                          format_func=lambda v: ENTITY_LABELS.get(v, v), key=f"{prefix}_entity")
    if entity != old_type:
        selector["conditions"] = []
        selector["entity"] = entity
        selector["point_source"] = next(iter(RELATION_POINT_SOURCES[entity]))
        for key in list(st.session_state):
            if key.startswith(f"{prefix}_condition_") or key == f"{prefix}_point":
                del st.session_state[key]
    selector["entity"] = entity
    sources = RELATION_POINT_SOURCES[entity]
    selector["point_source"] = st.selectbox("Meetpunt", list(sources), index=_safe_index(list(sources), selector.get("point_source")), format_func=lambda v: sources[v], key=f"{prefix}_point")
    conditions = selector.setdefault("conditions", [])
    for idx, condition in enumerate(conditions):
        st.caption(f"Voorwaarde {idx + 1}")
        cols = st.columns([3, 2, 2, 2, 1])
        props = _property_options(entity)
        with cols[0]:
            prop = st.selectbox("Eigenschap", props, index=_safe_index(props, condition.get("property")),
                                format_func=_property_label, key=f"{prefix}_condition_{idx}_property")
        operators = _operators_for_property(entity, prop)
        with cols[1]:
            operator = st.selectbox("Operator", operators, index=_safe_index(operators, condition.get("operator")),
                                    key=f"{prefix}_condition_{idx}_operator")
        with cols[2]:
            raw = st.text_input("Waarde", value=_value_to_text(condition.get("value", "")),
                                key=f"{prefix}_condition_{idx}_value")
        with cols[3]:
            tol = st.number_input("Tolerantie", min_value=0.0, value=float(condition.get("tolerance", 0.01)),
                                  key=f"{prefix}_condition_{idx}_tolerance", format="%.6f")
        with cols[4]:
            remove = st.button("×", key=f"{prefix}_condition_{idx}_remove")
        if remove:
            conditions.pop(idx)
            for key in list(st.session_state):
                if key.startswith(f"{prefix}_condition_"):
                    del st.session_state[key]
            st.rerun()
        condition.update(property=prop, operator=operator, value=raw, tolerance=tol)
        try:
            condition["value"] = _coerce_value(entity, prop, raw)
        except (ValueError, TypeError):
            pass
    if st.button("+ Voorwaarde", key=f"{prefix}_add"):
        prop = _property_options(entity)[0]
        conditions.append({"property": prop, "operator": _operators_for_property(entity, prop)[0],
                           "value": "", "tolerance": 0.01})
        st.rerun()


def _render_relation_editor(rule: dict[str, Any], key_prefix: str) -> dict[str, Any]:
    # Convert old relation criteria to the new two-selector schema.
    if "object_a" not in rule or "object_b" not in rule:
        entity = rule.get("entity", "circle")
        if entity not in RELATION_POINT_SOURCES:
            entity = "circle"
        source = rule.get("point_source", next(iter(RELATION_POINT_SOURCES[entity])))
        if source not in RELATION_POINT_SOURCES[entity]:
            source = next(iter(RELATION_POINT_SOURCES[entity]))
        rule["object_a"] = {"entity": entity, "point_source": source, "conditions": []}
        rule["object_b"] = {"entity": entity, "point_source": source, "conditions": []}
        rule.pop("entity", None)
        rule.pop("point_source", None)
    col_a, col_b = st.columns(2)
    with col_a:
        _render_relation_selector(rule, "object_a", key_prefix)
    with col_b:
        _render_relation_selector(rule, "object_b", key_prefix)
    relations = list(RELATIONS)
    rule["relation"] = st.selectbox("Relatie", relations, index=_safe_index(relations, rule.get("relation", "x_distance")), format_func=lambda v: RELATION_LABELS.get(v, v), key=f"{key_prefix}_relation")
    c1, c2 = st.columns(2)
    with c1:
        if rule["relation"] not in ("same_x", "same_y"):
            rule["value"] = st.number_input("Doelwaarde", value=float(rule.get("value", 0.0)), key=f"{key_prefix}_relation_value")
        else:
            rule.pop("value", None)
    with c2:
        rule["tolerance"] = st.number_input("Tolerantie", min_value=0.0,
                                            value=float(rule.get("tolerance", 0.01)),
                                            key=f"{key_prefix}_relation_tolerance", format="%.6f")
    return rule


# ============================================================
# Layout editor
# ============================================================

def _render_layout_editor(
    rule: dict[str, Any],
    key_prefix: str,
) -> dict[str, Any]:

    conditions = deepcopy(
        rule.get(
            "conditions",
            {},
        )
    )

    st.caption(
        "Activeer alleen de layoutvoorwaarden "
        "die voor dit criterium relevant zijn."
    )

    # --------------------------------------------------------
    # Layout name
    # --------------------------------------------------------

    use_layout_name = st.checkbox(
        "Controleer layoutnaam",
        value=("layout_name" in conditions),
        key=f"{key_prefix}_use_layout_name",
    )

    if use_layout_name:

        conditions["layout_name"] = (
            st.text_input(
                "Layoutnaam",
                value=str(
                    conditions.get(
                        "layout_name",
                        "Layout1",
                    )
                ),
                key=f"{key_prefix}_layout_name",
            )
        )

    else:

        conditions.pop(
            "layout_name",
            None,
        )

    # --------------------------------------------------------
    # Minimum viewports
    # --------------------------------------------------------

    use_min_viewports = st.checkbox(
        "Minimum aantal viewports",
        value=(
            "minimum_viewports"
            in conditions
        ),
        key=f"{key_prefix}_use_min_viewports",
    )

    if use_min_viewports:

        conditions["minimum_viewports"] = int(
            st.number_input(
                "Minimum viewports",
                min_value=0,
                value=int(
                    conditions.get(
                        "minimum_viewports",
                        1,
                    )
                ),
                step=1,
                key=f"{key_prefix}_min_viewports",
            )
        )

    else:

        conditions.pop(
            "minimum_viewports",
            None,
        )

    # --------------------------------------------------------
    # Maximum viewports
    # --------------------------------------------------------

    use_max_viewports = st.checkbox(
        "Maximum aantal viewports",
        value=("maximum_viewports" in conditions),
        key=f"{key_prefix}_use_max_viewports",
    )
    if use_max_viewports:
        conditions["maximum_viewports"] = int(
            st.number_input(
                "Maximum viewports",
                min_value=0,
                value=int(conditions.get("maximum_viewports", 1)),
                step=1,
                key=f"{key_prefix}_max_viewports",
            )
        )

    else:
        conditions.pop("maximum_viewports", None)

    # --------------------------------------------------------
    # Scale
    # --------------------------------------------------------

    use_scale = st.checkbox(
        "Controleer viewportschaal",
        value=("viewport_scale" in conditions),
        key=f"{key_prefix}_use_scale",
    )

    if use_scale:
        col_scale, col_tol = (st.columns(2))
        with col_scale:
            conditions["viewport_scale"] = float(
                st.number_input(
                    "Schaal 1 :",
                    min_value=0.0,
                    value=float(conditions.get("viewport_scale", 20.0)),
                    step=1.0,
                    key=f"{key_prefix}_viewport_scale",
                )
            )

        with col_tol:
            conditions["viewport_scale_tolerance"] = float(
                st.number_input(
                    "Schaaltolerantie",
                    min_value=0.0,
                    value=float(conditions.get("viewport_scale_tolerance", 1.0)),
                    step=0.1,
                    key=f"{key_prefix}_viewport_scale_tol",
                )
            )
    else:
        conditions.pop("viewport_scale", None)
        conditions.pop("viewport_scale_tolerance", None)

    # --------------------------------------------------------
    # Text
    # --------------------------------------------------------

    use_text = st.checkbox(
        "Controleer tekst in layout",
        value=("text_contains" in conditions),
        key=f"{key_prefix}_use_text",
    )

    if use_text:
        conditions["text_contains"] = (
            st.text_input(
                "Layouttekst bevat",
                value=str(conditions.get("text_contains", "")),
                key=f"{key_prefix}_layout_text",
            )
        )
    else:
        conditions.pop("text_contains", None)

    rule["conditions"] = (conditions)

    return rule


# ============================================================
# File editor
# ============================================================

def _render_file_editor(rule: dict[str, Any], key_prefix: str) -> dict[str, Any]:

    rule["extension"] = (
        st.text_input(
            "Bestandsextensie",
            value=rule.get("extension", ".pdf"),
            placeholder=".pdf",
            key=f"{key_prefix}_extension",
        )
        .strip()
        .lower()
    )

    if (rule["extension"] and not rule["extension"].startswith(".")):
        rule["extension"] = ("." + rule["extension"])

    col_count, col_size = (st.columns(2))
    with col_count:
        rule["minimum_count"] = int(
            st.number_input(
                "Minimum aantal bestanden",
                min_value=0,
                value=int(rule.get("minimum_count", 1)),
                step=1,
                key=f"{key_prefix}_minimum_count",
            )
        )

    with col_size:
        rule["minimum_size"] = int(
            st.number_input(
                "Minimale bestandsgrootte (bytes)",
                min_value=0,
                value=int(rule.get("minimum_size", 0)),
                step=100,
                key=f"{key_prefix}_minimum_size",
            )
        )

    return rule


# ============================================================
# Rule editor
# ============================================================

def _render_rule_editor(config: dict[str, Any], rule_index: int | None) -> dict[str, Any]:
    is_new = (rule_index is None)

    # Keep a persistent draft across Streamlit reruns.
    if "rule_editor_draft" not in st.session_state:
        if is_new:
            st.session_state["rule_editor_draft"] = _default_rule(config, "entity")
        else:
            criteria = config.get("criteria", [])
            if not (0 <= rule_index < len(criteria)):
                st.session_state["rule_editor_index"] = None
                return config
            st.session_state["rule_editor_draft"] = deepcopy(criteria[rule_index])

    rule = st.session_state["rule_editor_draft"]
    st.subheader("Nieuw criterium" if is_new else "Criterium bewerken")
    key_prefix = f"rule_editor_{rule['id']}"

    # --------------------------------------------------------
    # Rule type
    # --------------------------------------------------------

    rule_type_values = list(RULE_TYPE_LABELS.keys())
    old_type = rule.get("type", "entity")

    selected_type = st.selectbox(
        "Type criterium",
        options=rule_type_values,
        index=_safe_index(
            rule_type_values,
            old_type,
        ),
        format_func=lambda value: (RULE_TYPE_LABELS.get(value, value)),
        key=f"{key_prefix}_type",
    )

    # Reinitialize type-specific data if type changed.
    if selected_type != old_type:
        base = _default_rule(config, selected_type)
        base["id"] = rule.get("id", base["id"])
        base["name"] = rule.get("name", base["name"])
        base["points"] = rule.get("points", 1.0)
        base["enabled"] = rule.get("enabled", True)

        rule = base
        st.session_state["rule_editor_draft"] = rule
        for key in list(st.session_state):
            if key.startswith(key_prefix + "_") and key != key_prefix + "_type":
                del st.session_state[key]

    rule["type"] = (selected_type)

    # --------------------------------------------------------
    # Common
    # --------------------------------------------------------

    _render_common_fields(rule, key_prefix)

    st.divider()

    # --------------------------------------------------------
    # Type-specific
    # --------------------------------------------------------

    if selected_type == "entity":
        rule = _render_entity_editor(rule, key_prefix)

    elif selected_type == "relation":
        rule = _render_relation_editor(rule, key_prefix)

    elif selected_type == "layout":
        rule = _render_layout_editor(rule, key_prefix)
    elif selected_type == "file":
        rule = _render_file_editor(rule, key_prefix)

    st.session_state["rule_editor_draft"] = rule

    # --------------------------------------------------------
    # Buttons
    # --------------------------------------------------------

    st.divider()

    col_save, col_cancel = (
        st.columns(2)
    )

    with col_save:

        save_clicked = st.button(
            (
                "Criterium toevoegen"
                if is_new
                else "Wijzigingen opslaan"
            ),
            type="primary",
            width='stretch',
            key=f"{key_prefix}_save",
        )

    with col_cancel:
        cancel_clicked = st.button("Annuleren", width='stretch', key=f"{key_prefix}_cancel")

    if cancel_clicked:
        st.session_state["rule_editor_index"] = None
        st.session_state["rule_editor_new"] = False
        st.session_state.pop("rule_editor_draft", None)
        st.rerun()

    if save_clicked:
        error = None
        if not rule.get("name", "",).strip():
            error = ("Geef het criterium een naam.")
        elif (selected_type == "entity" and not rule.get("conditions")):
            error = ("Voeg minstens één objectvoorwaarde toe.")

        elif (selected_type == "layout" and not rule.get("conditions")):
            error = ("Selecteer minstens één layoutvoorwaarde.")
        elif (selected_type == "file" and not rule.get("extension")):
            error = ("Geef een bestandsextensie op.")

        if not error and selected_type == "relation":
            try:
                from criteria_generator import validate_generated_config
                validate_generated_config({"criteria": [rule]})
                for side in ("object_a", "object_b"):
                    for condition in rule[side]["conditions"]:
                        _coerce_value(rule[side]["entity"], condition["property"], condition.get("value"))
            except (ValueError, TypeError, KeyError) as exc:
                error = str(exc)

        if error:
            st.error(f"Criterium kan nog niet worden opgeslagen: {error}")

        else:
            if is_new:
                config.setdefault("criteria", []).append(rule)
            else:
                config["criteria"][rule_index] = (rule)

            st.session_state["rule_editor_index"] = None
            st.session_state["rule_editor_new"] = False
            st.session_state.pop("rule_editor_draft", None)
            st.rerun()

    return config


# ============================================================
# Public function
# ============================================================

def render_rule_builder(
    config: dict[str, Any],
) -> dict[str, Any]:
    """
    Render the complete Streamlit rule builder.

    Parameters
    ----------
    config:
        Current evaluator JSON configuration.

    Returns
    -------
    dict
        Potentially modified configuration.

    Notes
    -----
    The configuration is kept as a normal Python dictionary so
    it can directly be exported to JSON afterwards.
    """

    if "criteria" not in config:
        config["criteria"] = []

    if (
        "rule_editor_index"
        not in st.session_state
    ):
        st.session_state[
            "rule_editor_index"
        ] = None

    if ("rule_editor_new" not in st.session_state):
        st.session_state["rule_editor_new"] = False

    # --------------------------------------------------------
    # Overview
    # --------------------------------------------------------

    if (not st.session_state["rule_editor_new"] and st.session_state["rule_editor_index"] is None):
        _render_rule_overview(config)

        st.divider()
        if st.button("➕ Criterium toevoegen", type="primary", width='stretch'):
            st.session_state["rule_editor_new"] = True
            st.session_state.pop("rule_editor_draft", None)
            st.rerun()

    # --------------------------------------------------------
    # New rule
    # --------------------------------------------------------

    if st.session_state["rule_editor_new"]:
        config = _render_rule_editor(config, None)

    # --------------------------------------------------------
    # Existing rule
    # --------------------------------------------------------

    elif (st.session_state["rule_editor_index"] is not None):
        config = _render_rule_editor(config, int(st.session_state["rule_editor_index"]))

    return config
