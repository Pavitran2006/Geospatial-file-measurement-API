"""Shared test data and helpers."""
import zipfile
from pathlib import Path

import geopandas as gpd
from pyproj import Geod
from shapely.geometry import LineString, Polygon

# A ~1.1 km x ~1.1 km square and a ~1.1 km line near Bangalore (EPSG:4326, lon/lat).
POLYGON = Polygon([(77.59, 12.97), (77.60, 12.97), (77.60, 12.98), (77.59, 12.98)])
POLYGON_2 = Polygon([(77.61, 12.97), (77.62, 12.97), (77.62, 12.98), (77.61, 12.98)])
LINE = LineString([(77.59, 12.97), (77.60, 12.97)])
LINE_2 = LineString([(77.59, 12.97), (77.59, 12.98)])

_GEOD = Geod(ellps="WGS84")


def geodesic_area(poly) -> float:
    """Reference area (m2) computed on the ellipsoid, independent of our UTM approach."""
    return abs(_GEOD.geometry_area_perimeter(poly)[0])


def geodesic_length(line) -> float:
    """Reference length (m) computed on the ellipsoid."""
    return _GEOD.geometry_length(line)


KML_MIXED = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Survey</name>
    <Placemark>
      <name>Plot A</name>
      <Polygon><outerBoundaryIs><LinearRing><coordinates>
        77.59,12.97,0 77.60,12.97,0 77.60,12.98,0 77.59,12.98,0 77.59,12.97,0
      </coordinates></LinearRing></outerBoundaryIs></Polygon>
    </Placemark>
    <Placemark>
      <name>Road</name>
      <LineString><coordinates>77.59,12.97,0 77.60,12.97,0</coordinates></LineString>
    </Placemark>
    <Placemark>
      <name>Tree</name>
      <Point><coordinates>77.595,12.975,0</coordinates></Point>
    </Placemark>
  </Document>
</kml>
"""


def make_shapefile_zip(
    geometries, tmp_path: Path, name: str = "layer", crs: str = "EPSG:4326",
    drop_prj: bool = False,
) -> Path:
    """Write geometries to a Shapefile and zip it. All geometries must share one type
    (a Shapefile limitation). Geometries are given in EPSG:4326 and reprojected to `crs`."""
    gdf = gpd.GeoDataFrame(
        {"name": [f"feature {i}" for i in range(len(geometries))]},
        geometry=list(geometries),
        crs="EPSG:4326",
    ).to_crs(crs)

    folder = tmp_path / name
    folder.mkdir()
    gdf.to_file(folder / f"{name}.shp")

    zip_path = tmp_path / f"{name}.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for f in folder.iterdir():
            if drop_prj and f.suffix == ".prj":
                continue
            zf.write(f, arcname=f.name)
    return zip_path
