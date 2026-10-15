from __future__ import annotations

import math
from itertools import combinations
from typing import Any

from autocad_inspector import DrawingContext


def _compare(actual, operator: str, expected, tolerance: float = 0.0) -> bool:
    if operator == "equals":
        if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
            return math.isclose(float(actual), float(expected), abs_tol=float(tolerance))
        return str(actual).lower() == str(expected).lower()
    if operator == "greater_than":
        return actual > expected
    if operator == "greater_or_equal":
        return actual >= expected
    if operator == "less_than":
        return actual < expected
    if operator == "less_or_equal":
        return actual <= expected
    if operator == "contains":
        return str(expected).lower() in str(actual).lower()
    if operator == "starts_with":
        return str(actual).lower().startswith(str(expected).lower())
    if operator == "ends_with":
        return str(actual).lower().endswith(str(expected).lower())
    if operator == "contains_number":
        if not isinstance(actual, (list, tuple)):
            return False
        return any(math.isclose(float(x), float(expected), abs_tol=float(tolerance)) for x in actual)
    raise ValueError(f"Onbekende operator: {operator}")


def _count_ok(actual: int, operator: str, expected: int) -> bool:
    if operator == "equals":
        return actual == expected
    if operator == "greater_or_equal":
        return actual >= expected
    if operator == "less_or_equal":
        return actual <= expected
    raise ValueError(f"Onbekende count-operator: {operator}")


def _entity_rule(context: DrawingContext, rule: dict[str, Any]):
    entities = context.entities.get(rule["entity"], [])
    matches = []
    for entity in entities:
        ok = True
        for c in rule.get("conditions", []):
            actual = entity.get(c["property"])
            if not _compare(actual, c["operator"], c.get("value"), c.get("tolerance", 0.0)):
                ok = False
                break
        if ok:
            matches.append(entity)
    passed = _count_ok(len(matches), rule.get("count_operator", "greater_or_equal"), int(rule.get("count", 1)))
    return passed, len(matches), f"{len(matches)} overeenkomstige object(en)"


def _count_rule(context: DrawingContext, rule: dict[str, Any]):
    count = len(context.entities.get(rule["entity"], []))
    passed = _count_ok(count, rule.get("operator", "equals"), int(rule.get("value", 1)))
    return passed, count, f"Aantal: {count}"


def _point(entity: dict[str, Any], source: str):
    if source == "center":
        return entity.get("center_x"), entity.get("center_y")
    if source == "insertion_point":
        return entity.get("insertion_x"), entity.get("insertion_y")
    if source == "start":
        return entity.get("start_x"), entity.get("start_y")
    if source == "end":
        return entity.get("end_x"), entity.get("end_y")
    return None, None


def _matching_entities(context, selector):
    entity_type = selector["entity"]
    matches = []
    for item in context.entities.get(entity_type, []):
        if all(
            c.get("property") in item and item[c["property"]] is not None and _compare(item[c["property"]], c["operator"], c.get("value"), c.get("tolerance", 0.0))
            for c in selector.get("conditions", [])
        ):
            matches.append(item)
    return matches


def _relation_rule(context: DrawingContext, rule: dict[str, Any]):
    # Legacy schema remains supported.
    if "object_a" not in rule or "object_b" not in rule:
        entities = context.entities.get(rule["entity"], [])
        pairs = combinations(entities, 2)
        source_a = source_b = rule.get("point_source", "center")
    else:
        a_selector, b_selector = rule["object_a"], rule["object_b"]
        a_entities = _matching_entities(context, a_selector)
        b_entities = _matching_entities(context, b_selector)
        pairs = ((a, b) for a in a_entities for b in b_entities if a is not b)
        source_a = a_selector.get("point_source", "center")
        source_b = b_selector.get("point_source", "center")

    relation = rule["relation"]
    target = float(rule.get("value", 0.0))
    tol = float(rule.get("tolerance", 0.01))
    for a, b in pairs:
        ax, ay = _point(a, source_a)
        bx, by = _point(b, source_b)
        if None in (ax, ay, bx, by):
            continue
        dx, dy = abs(float(ax) - float(bx)), abs(float(ay) - float(by))
        values = {"x_distance": dx, "y_distance": dy,
                  "distance_2d": math.hypot(dx, dy), "same_x": dx, "same_y": dy}
        if relation not in values:
            raise ValueError(f"Onbekende relatie: {relation}")
        actual = values[relation]
        expected = 0.0 if relation in ("same_x", "same_y") else target
        if math.isclose(actual, expected, rel_tol=0.0, abs_tol=tol):
            return True, actual, f"Passend objectpaar gevonden: {relation} = {actual:g}"
    return False, None, "Geen passend objectpaar gevonden"


def _layout_rule(context: DrawingContext, rule: dict[str, Any]):
    name = rule.get("layout_name", "*")
    layouts = [x for x in context.layouts if name == "*" or str(x.get("name", "")).lower() == str(name).lower()]
    check = rule.get("check", "exists")

    if check == "exists":
        return bool(layouts), len(layouts), f"{len(layouts)} layout(s)"

    if check == "viewport_count":
        count = sum(len(x.get("viewports", [])) for x in layouts)
        passed = _count_ok(count, rule.get("operator", "equals"), int(rule.get("value", 1)))
        return passed, count, f"{count} viewport(s)"

    if check == "viewport_scale":
        target = float(rule.get("value"))
        tol = float(rule.get("tolerance", 1.0))
        values = [vp.get("scale_denominator") for layout in layouts for vp in layout.get("viewports", [])]
        passed = any(v is not None and math.isclose(float(v), target, abs_tol=tol) for v in values)
        return passed, values, f"Schalen: {values}"

    if check == "text_contains":
        needle = str(rule.get("value", "")).lower()
        texts = [str(t.get("text", "")) for layout in layouts for t in layout.get("texts", [])]
        passed = any(needle in t.lower() for t in texts)
        return passed, texts, "Tekst gevonden" if passed else "Tekst niet gevonden"

    raise ValueError(f"Onbekende layout-check: {check}")


def _file_rule(context: DrawingContext, rule: dict[str, Any]):
    extension = str(rule.get("extension", "")).lower()
    files = [f for f in context.files if str(f.get("extension", "")).lower() == extension]
    check = rule.get("check", "exists")
    if check == "exists":
        minimum_count = int(rule.get("minimum_count", 1))
        return len(files) >= minimum_count, len(files), f"{len(files)} bestand(en) met extensie {extension}"
    if check == "minimum_size":
        minimum = int(rule.get("value", 0))
        sizes = [int(f.get("size", 0)) for f in files]
        passed = any(size >= minimum for size in sizes)
        return passed, sizes, f"Bestandsgroottes: {sizes}"
    raise ValueError(f"Onbekende file-check: {check}")


def evaluate_context(context: DrawingContext, config: dict[str, Any]) -> dict[str, Any]:
    results = []
    score = 0.0
    max_score = 0.0

    handlers = {
        "entity": _entity_rule,
        "count": _count_rule,
        "relation": _relation_rule,
        "layout": _layout_rule,
        "file": _file_rule,
    }

    for rule in config.get("criteria", []):
        if not rule.get("enabled", True):
            continue
        max_points = float(rule.get("points", 1.0))
        max_score += max_points
        try:
            passed, actual, details = handlers[rule["type"]](context, rule)
        except Exception as exc:
            passed, actual, details = False, None, f"Evaluatiefout: {exc}"
        points = max_points if passed else 0.0
        score += points
        results.append({
            "id": rule.get("id"),
            "name": rule.get("name", "Naamloos criterium"),
            "passed": passed,
            "points": points,
            "max_points": max_points,
            "actual": actual,
            "details": details,
        })

    percentage = (100.0 * score / max_score) if max_score else 0.0
    return {
        "score": score,
        "max_score": max_score,
        "percentage": percentage,
        "results": results,
    }
