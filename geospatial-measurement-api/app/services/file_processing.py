"""Read an uploaded Shapefile (.zip) or KML and turn it into feature records."""
import json
import os
import zipfile
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio

from app.config import MAX_UNZIPPED_BYTES
from app.services.crs import crs_label
from app.services.measurements import measure_geometry

SHAPEFILE = "shapefile"
KML = "kml"


class FileProcessingError(Exception):
    """The file is unreadable or invalid. The message is safe to show to clients."""


@dataclass
class ProcessedFile:
    crs: str
    features: list[dict]  # keyword arguments for the Feature model


def detect_file_type(filename: str) -> str | None:
    ext = Path(filename).suffix.lower()
    return {".zip": SHAPEFILE, ".kml": KML}.get(ext)


def _extract_zip_safely(zip_path: Path, dest: Path) -> None:
    """Extract a zip, rejecting path traversal and zip bombs."""
    dest_root = dest.resolve()
    try:
        with zipfile.ZipFile(zip_path) as zf:
            total = 0
            for info in zf.infolist():
                if info.is_dir():
                    continue
                target = (dest / info.filename).resolve()
                if os.path.commonpath([dest_root, target]) != str(dest_root):
                    raise FileProcessingError("Zip contains an unsafe file path.")
                total += info.file_size
                if total > MAX_UNZIPPED_BYTES:
                    raise FileProcessingError("Zip contents are too large.")
            zf.extractall(dest)
    except zipfile.BadZipFile:
        raise FileProcessingError("The uploaded file is not a valid zip archive.")


def _read_shapefile_zip(zip_path: Path, workdir: Path) -> gpd.GeoDataFrame:
    extract_dir = workdir / "extracted"
    extract_dir.mkdir()
    _extract_zip_safely(zip_path, extract_dir)

    shp_files = [
        p
        for p in extract_dir.rglob("*")
        if p.suffix.lower() == ".shp" and "__MACOSX" not in p.parts and not p.name.startswith("._")
    ]
    if not shp_files:
        kml_files = [
            p
            for p in extract_dir.rglob("*")
            if p.suffix.lower() == ".kml" and "__MACOSX" not in p.parts and not p.name.startswith("._")
        ]
        if kml_files:
            return _read_kml(kml_files[0])
        raise FileProcessingError(
            "The zip archive does not contain a .shp file. "
            "Please ensure your zip contains a Shapefile (.shp, .shx, .dbf, .prj) or a .kml file."
        )
    if len(shp_files) > 1:
        raise FileProcessingError(
            "The zip archive must contain max 1 Shapefile, "
            f"found {len(shp_files)}."
        )
    try:
        return gpd.read_file(shp_files[0])
    except Exception as exc:
        raise FileProcessingError(f"Could not read the Shapefile: {exc}")


def _read_kml(kml_path: Path) -> gpd.GeoDataFrame:
    """Read every layer (KML folder/document) and combine them."""
    try:
        layers = pyogrio.list_layers(kml_path)
        frames = []
        for layer_name in layers[:, 0]:
            frame = gpd.read_file(kml_path, layer=layer_name)
            if len(frame):
                frames.append(frame)
    except Exception as exc:
        raise FileProcessingError(f"Could not read the KML file: {exc}")

    if not frames:
        raise FileProcessingError("The KML file contains no features.")
    combined = pd.concat(frames, ignore_index=True)
    return gpd.GeoDataFrame(combined, geometry="geometry", crs=frames[0].crs)


def process_file(path: Path, file_type: str, workdir: Path) -> ProcessedFile:
    """Read the file, extract every feature and measure it."""
    gdf = _read_shapefile_zip(path, workdir) if file_type == SHAPEFILE else _read_kml(path)



    if gdf.crs is None:
        raise FileProcessingError(
            "The file has no coordinate reference system (CRS). "
            "For Shapefiles, make sure the .prj file is included in the zip."
        )
    if len(gdf) == 0:
        raise FileProcessingError("The file contains no features.")

    gdf = gdf.reset_index(drop=True)
    label = crs_label(gdf.crs)

    # GeoPandas gives us JSON-safe geometry + properties (NaN -> null, dates -> str).
    geojson_features = json.loads(gdf.to_json(drop_id=True, default=str))["features"]

    features = []
    for index, (geom, gj) in enumerate(zip(gdf.geometry, geojson_features)):
        result = measure_geometry(geom, gdf.crs)
        features.append(
            {
                "feature_index": index,
                "geometry_type": geom.geom_type if geom is not None else None,
                "geometry": gj.get("geometry"),
                "crs": label,
                "properties": gj.get("properties") or {},
                "measurement_status": result.status,
                "measurement_type": result.measurement_type,
                "measurement_value": result.value,
                "measurement_unit": result.unit,
                "projected_crs": result.projected_crs,
                "note": result.note,
            }
        )
    return ProcessedFile(crs=label, features=features)
