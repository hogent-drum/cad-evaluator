from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import comtypes
from pyautocad import Autocad

COM_CALL_REJECTED = -2147418111


@dataclass
class DrawingContext:
    dwg_path: str
    entities: dict[str, list[dict[str, Any]]] = field(default_factory=lambda: {
        "circle": [],
        "line": [],
        "polyline": [],
        "dimension": [],
        "hatch": [],
        "text": [],
        "block": [],
        "other": [],
    })
    layouts: list[dict[str, Any]] = field(default_factory=list)
    files: list[dict[str, Any]] = field(default_factory=list)


def com_retry(func, retries: int = 20, delay: float = 0.2):
    last_error = None
    for _ in range(retries):
        try:
            return func()
        except comtypes.COMError as exc:
            last_error = exc
            if getattr(exc, "hresult", None) == COM_CALL_REJECTED:
                time.sleep(delay)
                continue
            raise
    raise RuntimeError("AutoCAD bleef COM-aanroepen weigeren.") from last_error


def _safe(obj: Any, name: str, default=None):
    try:
        return getattr(obj, name)
    except Exception:
        return default


def _tuple(value):
    if value is None:
        return None
    try:
        return tuple(value)
    except Exception:
        return value


def _polyline_segment_lengths(entity) -> list[float]:
    coords = list(_safe(entity, "Coordinates", []))
    if len(coords) < 4:
        return []
    points = list(zip(coords[0::2], coords[1::2]))
    lengths = [math.dist(a, b) for a, b in zip(points, points[1:])]
    if _safe(entity, "Closed", False) and len(points) > 1:
        lengths.append(math.dist(points[-1], points[0]))
    return lengths


def _entity_to_dict(entity) -> dict[str, Any] | None:
    object_name = _safe(entity, "ObjectName")
    if not object_name:
        return None

    data = {
        "object_name": object_name,
        "handle": _safe(entity, "Handle"),
        "layer": _safe(entity, "Layer"),
        "linetype": _safe(entity, "Linetype"),
        "linetype_scale": _safe(entity, "LinetypeScale"),
        "color": _safe(entity, "Color"),
        "lineweight": _safe(entity, "Lineweight"),
    }

    if object_name == "AcDbCircle":
        center = _tuple(_safe(entity, "Center"))
        radius = _safe(entity, "Radius")
        data.update({
            "type": "circle",
            "center": center,
            "center_x": center[0] if center else None,
            "center_y": center[1] if center else None,
            "center_z": center[2] if center and len(center) > 2 else 0.0,
            "radius": radius,
            "diameter": 2 * radius if radius is not None else None,
            "area": _safe(entity, "Area"),
            "circumference": _safe(entity, "Circumference"),
        })
        return data

    if object_name == "AcDbLine":
        start = _tuple(_safe(entity, "StartPoint"))
        end = _tuple(_safe(entity, "EndPoint"))
        data.update({
            "type": "line",
            "start": start,
            "end": end,
            "start_x": start[0] if start else None,
            "start_y": start[1] if start else None,
            "start_z": start[2] if start and len(start) > 2 else 0.0,
            "end_x": end[0] if end else None,
            "end_y": end[1] if end else None,
            "end_z": end[2] if end and len(end) > 2 else 0.0,
            "length": _safe(entity, "Length"),
            "angle": _safe(entity, "Angle"),
        })
        return data

    if object_name == "AcDbPolyline":
        coords = list(_safe(entity, "Coordinates", []))
        points = list(zip(coords[0::2], coords[1::2]))
        data.update({
            "type": "polyline",
            "coordinates": coords,
            "points": points,
            "closed": bool(_safe(entity, "Closed", False)),
            "length": _safe(entity, "Length"),
            "area": _safe(entity, "Area"),
            "segment_lengths": _polyline_segment_lengths(entity),
            "vertex_count": len(points),
        })
        return data

    if object_name.endswith("Dimension"):
        data.update({
            "type": "dimension",
            "measurement": _safe(entity, "Measurement"),
            "text_override": _safe(entity, "TextOverride"),
            "text_position": _tuple(_safe(entity, "TextPosition")),
            "style_name": _safe(entity, "StyleName"),
        })
        return data

    if object_name == "AcDbHatch":
        data.update({
            "type": "hatch",
            "pattern_name": _safe(entity, "PatternName"),
            "pattern_scale": _safe(entity, "PatternScale"),
            "pattern_angle": _safe(entity, "PatternAngle"),
            "area": _safe(entity, "Area"),
            "associative": _safe(entity, "AssociativeHatch"),
        })
        return data

    if object_name in ("AcDbText", "AcDbMText"):
        text = _safe(entity, "TextString")
        if text is None:
            text = _safe(entity, "Contents")
        insertion = _tuple(_safe(entity, "InsertionPoint"))
        data.update({
            "type": "text",
            "text": text,
            "height": _safe(entity, "Height"),
            "rotation": _safe(entity, "Rotation"),
            "insertion_x": insertion[0] if insertion else None,
            "insertion_y": insertion[1] if insertion else None,
            "style_name": _safe(entity, "StyleName"),
        })
        return data

    if object_name == "AcDbBlockReference":
        insertion = _tuple(_safe(entity, "InsertionPoint"))
        data.update({
            "type": "block",
            "name": _safe(entity, "Name"),
            "effective_name": _safe(entity, "EffectiveName"),
            "insertion_point": insertion,
            "insertion_x": insertion[0] if insertion else None,
            "insertion_y": insertion[1] if insertion else None,
            "insertion_z": insertion[2] if insertion and len(insertion) > 2 else 0.0,
            "rotation": _safe(entity, "Rotation"),
            "x_scale": _safe(entity, "XScaleFactor"),
            "y_scale": _safe(entity, "YScaleFactor"),
            "z_scale": _safe(entity, "ZScaleFactor"),
        })
        return data

    data["type"] = "other"
    return data


def _inspect_layout(layout) -> dict[str, Any]:
    info = {
        "name": _safe(layout, "Name"),
        "viewports": [],
        "texts": [],
    }
    block = com_retry(lambda: layout.Block)

    for entity in block:
        object_name = _safe(entity, "ObjectName")
        if object_name == "AcDbViewport":
            custom_scale = _safe(entity, "CustomScale")
            denom = None
            if custom_scale not in (None, 0):
                try:
                    denom = 1.0 / float(custom_scale)
                except Exception:
                    pass
            info["viewports"].append({
                "number": _safe(entity, "Number"),
                "custom_scale": custom_scale,
                "scale_denominator": denom,
                "width": _safe(entity, "Width"),
                "height": _safe(entity, "Height"),
                "display_locked": _safe(entity, "DisplayLocked"),
            })
        elif object_name in ("AcDbText", "AcDbMText"):
            text = _safe(entity, "TextString")
            if text is None:
                text = _safe(entity, "Contents")
            info["texts"].append({
                "text": text,
                "layer": _safe(entity, "Layer"),
                "height": _safe(entity, "Height"),
                "style_name": _safe(entity, "StyleName"),
            })
    return info


def _inspect_files(dwg_path: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in Path(dwg_path).parent.iterdir():
        try:
            if item.is_file():
                results.append({
                    "name": item.name,
                    "path": str(item),
                    "extension": item.suffix.lower(),
                    "size": item.stat().st_size,
                })
        except Exception:
            pass
    return results


def inspect_dwg(dwg_path: str, visible: bool = True, readonly: bool = True) -> DrawingContext:
    """Inspecteer één DWG. ModelSpace wordt altijd expliciet verwerkt."""
    comtypes.CoInitialize()
    doc = None
    try:
        dwg_path = str(Path(dwg_path).resolve())
        acad = Autocad(create_if_not_exists=True)
        try:
            acad.app.Visible = visible
        except Exception:
            pass

        doc = com_retry(lambda: acad.app.Documents.Open(dwg_path, True) if readonly else acad.app.Documents.Open(dwg_path))
        modelspace = com_retry(lambda: doc.ModelSpace)
        context = DrawingContext(dwg_path=dwg_path)

        for entity in modelspace:
            try:
                data = _entity_to_dict(entity)
                if data:
                    context.entities.setdefault(data["type"], []).append(data)
            except Exception as exc:
                print(f"Waarschuwing bij object {_safe(entity, 'ObjectName', 'Unknown')}: {exc}")

        for layout in com_retry(lambda: doc.Layouts):
            try:
                context.layouts.append(_inspect_layout(layout))
            except Exception as exc:
                print(f"Waarschuwing bij layout {_safe(layout, 'Name', 'Unknown')}: {exc}")

        context.files = _inspect_files(dwg_path)
        return context

    finally:
        if doc is not None:
            try:
                com_retry(lambda: doc.Close(False), retries=10)
            except Exception:
                pass
        comtypes.CoUninitialize()
