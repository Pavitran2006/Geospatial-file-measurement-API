"""Unit tests for CRS selection and geometry measurement (no HTTP involved)."""
import pytest
from pyproj import CRS
from shapely.geometry import GeometryCollection, MultiPolygon, Point, Polygon

from app.services.crs import utm_crs_for_lonlat
from app.services.measurements import (
    NOT_APPLICABLE,
    OK,
    SKIPPED,
    UNSUPPORTED,
    measure_geometry,
)
from tests.helpers import LINE, POLYGON, POLYGON_2, geodesic_area, geodesic_length

WGS84 = CRS.from_epsg(4326)


@pytest.mark.parametrize(
    "lon, lat, epsg",
    [
        (77.6, 12.97, 32643),  # Bangalore -> UTM 43N
        (-0.1, 51.5, 32630),  # London -> UTM 30N
        (151.2, -33.9, 32756),  # Sydney -> UTM 56S
        (0.0, 90.0, 32661),  # North pole -> UPS North
        (0.0, -90.0, 32761),  # South pole -> UPS South
    ],
)
def test_utm_zone_selection(lon, lat, epsg):
    assert utm_crs_for_lonlat(lon, lat).to_epsg() == epsg


def test_polygon_area_is_in_square_metres_not_degrees():
    result = measure_geometry(POLYGON, WGS84)
    assert result.status == OK
    assert result.measurement_type == "area"
    assert result.unit == "m2"
    assert result.projected_crs == "EPSG:32643"
    # Degrees would give ~0.0001; real area is ~1.2 million m2.
    assert result.value == pytest.approx(geodesic_area(POLYGON), rel=5e-3)


def test_line_length_in_metres():
    result = measure_geometry(LINE, WGS84)
    assert result.status == OK
    assert result.measurement_type == "length"
    assert result.unit == "m"
    assert result.value == pytest.approx(geodesic_length(LINE), rel=5e-3)


def test_multipolygon_area_is_sum_of_parts():
    multi = MultiPolygon([POLYGON, POLYGON_2])
    result = measure_geometry(multi, WGS84)
    expected = geodesic_area(POLYGON) + geodesic_area(POLYGON_2)
    assert result.status == OK
    assert result.value == pytest.approx(expected, rel=5e-3)


def test_z_values_are_ignored():
    poly_3d = Polygon([(77.59, 12.97, 500), (77.60, 12.97, 500), (77.60, 12.98, 500)])
    result = measure_geometry(poly_3d, WGS84)
    assert result.status == OK
    assert result.value > 0


def test_point_has_no_measurement():
    result = measure_geometry(Point(77.6, 12.97), WGS84)
    assert result.status == NOT_APPLICABLE
    assert result.value is None


def test_unsupported_geometry_is_handled_gracefully():
    collection = GeometryCollection([POLYGON, Point(77.6, 12.97)])
    result = measure_geometry(collection, WGS84)
    assert result.status == UNSUPPORTED
    assert result.value is None
    assert "GeometryCollection" in result.note


@pytest.mark.parametrize("geom", [None, Polygon()])
def test_missing_or_empty_geometry_is_skipped(geom):
    result = measure_geometry(geom, WGS84)
    assert result.status == SKIPPED


def test_projected_source_crs_gives_same_area():
    # Same polygon expressed in UTM 43N coordinates must give the same answer.
    from shapely.ops import transform
    from pyproj import Transformer

    utm = CRS.from_epsg(32643)
    to_utm = Transformer.from_crs(WGS84, utm, always_xy=True)
    poly_utm = transform(to_utm.transform, POLYGON)

    in_degrees = measure_geometry(POLYGON, WGS84)
    in_metres = measure_geometry(poly_utm, utm)
    assert in_metres.value == pytest.approx(in_degrees.value, rel=1e-4)
