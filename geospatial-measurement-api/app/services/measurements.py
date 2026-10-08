"""Measure a single geometry: area for polygons, length for lines.

Measurements are never computed in degrees. Every geometry is first
transformed to the UTM zone of its centroid (a projected CRS in metres),
and only then measured with Shapely.
"""
from dataclasses import dataclass

import shapely
from pyproj import CRS, Transformer
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform

from app.services.crs import crs_label, utm_crs_for_lonlat

# Measurement statuses
OK = "OK"
NOT_APPLICABLE = "NOT_APPLICABLE"  # e.g. points: nothing to measure
UNSUPPORTED = "UNSUPPORTED"  # e.g. GeometryCollection
SKIPPED = "SKIPPED"  # missing or empty geometry

_WGS84 = CRS.from_epsg(4326)


@dataclass
class Measurement:
    status: str
    measurement_type: str | None = None  # "area" | "length"
    value: float | None = None
    unit: str | None = None  # "m2" | "m"
    projected_crs: str | None = None
    note: str | None = None


def _centroid_lonlat(geom: BaseGeometry, source_crs: CRS) -> tuple[float, float]:
    """Centroid of the geometry expressed as (lon, lat) in WGS84."""
    c = geom.centroid
    if source_crs.is_geographic:
        # Assumes the source geographic CRS is (close to) WGS84, which is
        # accurate enough to pick a UTM zone.
        return c.x, c.y
    to_wgs84 = Transformer.from_crs(source_crs, _WGS84, always_xy=True)
    lon, lat = to_wgs84.transform(c.x, c.y)
    return lon, lat


def _to_projected(geom: BaseGeometry, source_crs: CRS) -> tuple[BaseGeometry, CRS]:
    lon, lat = _centroid_lonlat(geom, source_crs)
    target = utm_crs_for_lonlat(lon, lat)
    # always_xy=True keeps (x=lon, y=lat) order, matching Shapely coordinates.
    transformer = Transformer.from_crs(source_crs, target, always_xy=True)
    return transform(transformer.transform, geom), target


def measure_geometry(geom: BaseGeometry | None, source_crs: CRS) -> Measurement:
    """Return the measurement for one geometry. Never raises for bad geometry."""
    if geom is None or geom.is_empty:
        return Measurement(status=SKIPPED, note="Geometry is missing or empty.")

    geom_type = geom.geom_type

    if geom_type in ("Point", "MultiPoint"):
        return Measurement(
            status=NOT_APPLICABLE, note="Points have no area or length."
        )

    if geom_type in ("Polygon", "MultiPolygon"):
        kind, unit = "area", "m2"
    elif geom_type in ("LineString", "MultiLineString"):
        kind, unit = "length", "m"
    else:
        return Measurement(
            status=UNSUPPORTED,
            note=f"Measurement is not supported for geometry type {geom_type}.",
        )

    try:
        flat = shapely.force_2d(geom)  # ignore Z values (e.g. KML altitude)
        projected, target = _to_projected(flat, source_crs)
        value = projected.area if kind == "area" else projected.length
    except Exception as exc:  # e.g. coordinates outside the CRS valid range
        return Measurement(
            status=SKIPPED, note=f"Could not transform or measure geometry: {exc}"
        )

    return Measurement(
        status=OK,
        measurement_type=kind,
        value=round(float(value), 4),
        unit=unit,
        projected_crs=crs_label(target),
    )
