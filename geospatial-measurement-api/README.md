# Geospatial File Measurement API

A FastAPI backend that accepts a **zipped Shapefile** or a **KML** file, extracts every feature, and returns **area** (polygons) and **length** (lines). Measurements are always computed in a projected CRS in metres, never in degrees.

## Setup

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

- API: http://127.0.0.1:8000
- Interactive docs (Swagger UI): http://127.0.0.1:8000/docs

The SQLite database (`geo_api.db`) is created automatically on first start. To use another database set `DATABASE_URL` (e.g. a PostgreSQL URL).

With Docker:

```bash
docker build -t geo-api .
docker run -p 8000:8000 geo-api
```

## Run tests

```bash
pytest
```

Tests build their own Shapefiles/KML on the fly and use a temporary database. Expected measurements are checked against an independent geodesic calculation (`pyproj.Geod`).

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./geo_api.db` | SQLAlchemy database URL |
| `MAX_UPLOAD_MB` | `50` | Maximum upload size |
| `MAX_UNZIPPED_MB` | `200` | Maximum total size of files inside an uploaded zip |

## API

### `POST /api/files/` – upload and process a file

Accepts `.zip` (containing one Shapefile, with its `.shp`, `.shx`, `.dbf` and `.prj`) or `.kml`, as multipart form field `file`.

```bash
curl -X POST http://127.0.0.1:8000/api/files/ -F "file=@samples/sample.kml"
```

`201 Created`:

```json
{
  "id": "5f0c1c9a2d4b4e0e9c7a1f3b6d8e2a10",
  "filename": "sample.kml",
  "file_type": "kml",
  "status": "COMPLETED",
  "crs": "EPSG:4326",
  "feature_count": 3,
  "error": null,
  "created_at": "2026-10-08T06:10:00Z"
}
```

Errors:

| Status | When |
|---|---|
| `415` | Extension is not `.zip` or `.kml` |
| `413` | File is larger than `MAX_UPLOAD_MB` |
| `422` | File is unreadable or invalid (corrupt zip, no `.shp`, missing CRS, no features). The file is stored with status `FAILED`; the body contains its `id` and a message |

### `GET /api/files/{id}/` – file information

```bash
curl http://127.0.0.1:8000/api/files/<id>/
```

Returns the same object as above (`status` is `COMPLETED` or `FAILED`). `404` if the id is unknown.

### `GET /api/files/{id}/measurements/` – measurements

```bash
curl http://127.0.0.1:8000/api/files/<id>/measurements/
```

```json
{
  "file_id": "5f0c1c9a2d4b4e0e9c7a1f3b6d8e2a10",
  "crs": "EPSG:4326",
  "feature_count": 3,
  "limit": 1000,
  "offset": 0,
  "summary": {
    "total_area_m2": 1197560.1,
    "total_length_m": 1085.4,
    "measured_features": 2,
    "unmeasured_features": 1
  },
  "measurements": [
    {
      "feature_index": 0,
      "geometry_type": "Polygon",
      "status": "OK",
      "measurement": {"type": "area", "value": 1197560.1, "unit": "m2", "projected_crs": "EPSG:32643"},
      "note": null
    },
    {
      "feature_index": 1,
      "geometry_type": "LineString",
      "status": "OK",
      "measurement": {"type": "length", "value": 1085.4, "unit": "m", "projected_crs": "EPSG:32643"},
      "note": null
    },
    {
      "feature_index": 2,
      "geometry_type": "Point",
      "status": "NOT_APPLICABLE",
      "measurement": null,
      "note": "Points have no area or length."
    }
  ]
}
```

(Numbers above are illustrative.) Per-feature `status` is one of `OK`, `NOT_APPLICABLE` (points), `UNSUPPORTED` (e.g. GeometryCollection), `SKIPPED` (empty/missing geometry or a failed transform). Supports `?limit=` (1–10000) and `?offset=`. The `summary` always covers the whole file. Returns `409` if the file is not `COMPLETED`.

### `GET /api/files/{id}/features/` – features

Returns, for every feature: `feature_index`, `geometry_type`, `geometry` (GeoJSON), `crs`, and `properties`. Supports `limit` / `offset`.

## Architecture

```
app/
  main.py                    FastAPI app, startup (creates tables)
  config.py                  Settings from environment variables
  database.py                SQLAlchemy engine / session
  models.py                  UploadedFile (1) -> Feature (many)
  schemas.py                 Pydantic response models
  routers/files.py           HTTP layer only: validation, status codes, DB reads/writes
  services/
    file_processing.py       Read Shapefile/KML into features
    measurements.py          Measure one geometry
    crs.py                   CRS labelling and UTM zone selection
tests/                       API tests and unit tests
```

The router contains no geospatial logic. The services contain no HTTP logic, so they can be unit-tested directly.

### File-processing flow

1. Validate the extension (`.zip` / `.kml`) and stream the upload to a temp directory, enforcing the size limit.
2. Create an `UploadedFile` row with status `PROCESSING`.
3. **Shapefile:** extract the zip safely (rejects path traversal and oversized archives), require exactly one `.shp`, read it with GeoPandas.
   **KML:** read every layer (KML folders/documents) and combine them.
4. Reject files with no CRS or no features.
5. For each feature, build a record: index, geometry type, GeoJSON geometry, CRS, properties, and measurement.
6. Save all features, set the file to `COMPLETED` (or `FAILED` with an error message on any problem).

### Measurement flow

For each geometry:
- Empty or missing geometry → `SKIPPED`.
- Point / MultiPoint → `NOT_APPLICABLE`.
- Polygon / MultiPolygon → area. LineString / MultiLineString → length.
- Anything else (e.g. GeometryCollection) → `UNSUPPORTED`, no crash.
- Z values are dropped before measuring.

### CRS handling

1. The file's CRS is read from the `.prj` (Shapefile) or the KML (always WGS84 / EPSG:4326 by specification).
2. The geometry's centroid is converted to longitude/latitude.
3. The matching **WGS84 UTM zone** is chosen (EPSG:326xx north, 327xx south; UPS beyond 84°N / 80°S).
4. The geometry is transformed to that zone (`pyproj`, `always_xy=True` so coordinate order stays lon/lat) and measured with Shapely, giving square metres / metres.

This is applied even if the source file is already projected, because a source projection in metres is not necessarily suitable for measuring (Web Mercator, EPSG:3857, distorts area badly).

## Design decisions

- **FastAPI over Django.** The task is a small API with no admin or auth needs; FastAPI gives typed request/response models and automatic OpenAPI docs with little code.
- **Synchronous processing.** Files are parsed during the upload request and the endpoint returns the final status. This keeps the API simple and the result immediately available. For very large files a job queue (Celery/RQ) with a `PROCESSING` → `COMPLETED` flow is the natural next step; the `status` field and model already support it.
- **UTM zone per feature instead of one CRS per file.** Files can span several zones; choosing per feature keeps each measurement in its best local projection. *Alternatives considered:* one CRS per file (simpler, but wrong for wide-area files); an equal-area CRS such as EPSG:6933 (exact areas, but lengths are distorted); geodesic calculation on the ellipsoid (`pyproj.Geod`, most accurate, but the task asks for projected measurements). The tests use the geodesic method as an independent reference.
- **Measurements stored at upload time.** They are computed once and stored, so `GET` requests are fast database reads.
- **Shapefile zip must contain exactly one `.shp`.** Keeps behaviour unambiguous; multiple shapefiles in one zip return a clear error.
- **Unreadable files are stored as `FAILED`** with an error message, so a client can look the file up later by id.
- **SQLite by default, any SQLAlchemy database via `DATABASE_URL`.** Zero setup locally; the models use portable types (JSON column).
- **Safety.** Upload size limit, zip path-traversal check, uncompressed size limit, and no unexpected exceptions leaking to clients.

## Limitations

- A polygon that spans more than one UTM zone is measured in the zone of its centroid, so very large polygons have larger error.
- The source geographic CRS is assumed to be (close to) WGS84 when choosing the UTM zone.
- KML styling, network links and ground overlays are ignored; only geometry and attributes are read.

## Learnings

- Shapefile and KML differ in important ways: a Shapefile holds a single geometry type and relies on a separate `.prj` for its CRS, while KML always uses lon/lat but can mix geometry types and has multiple layers.
- Measuring in degrees is wrong because the size of a degree changes with latitude; projecting first, and checking the result against an independent geodesic calculation, is what makes the numbers trustworthy.
- Axis order matters: EPSG:4326 is officially lat/lon, but GIS libraries store lon/lat. `always_xy=True` avoids silently swapped coordinates.
- Keeping geospatial logic out of the HTTP layer made it easy to unit-test.

## Future scope

- Background processing with a job queue and progress reporting for large files.
- Support for more formats (GeoJSON, GeoPackage, KMZ).
- Geodesic or equal-area measurement as a selectable method; per-polygon handling of multi-zone geometries.
- Perimeter and bounding box in the response; unit conversion (hectares, km², feet, acres).
- Authentication, per-user files, file deletion/retention, and object storage for the original uploads.
- Alembic migrations, PostgreSQL + PostGIS for spatial queries, and CI (GitHub Actions) running the tests.
