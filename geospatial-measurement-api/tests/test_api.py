"""End-to-end API tests using a temporary database."""
import pytest

from tests.helpers import (
    KML_MIXED,
    LINE,
    LINE_2,
    POLYGON,
    POLYGON_2,
    geodesic_area,
    geodesic_length,
    make_shapefile_zip,
)


# ---------- upload + file info ----------

def test_upload_shapefile_zip(upload, tmp_path):
    zip_path = make_shapefile_zip([POLYGON, POLYGON_2], tmp_path, name="plots")
    resp = upload("plots.zip", zip_path.read_bytes())

    assert resp.status_code == 201
    body = resp.json()
    assert body["filename"] == "plots.zip"
    assert body["file_type"] == "shapefile"
    assert body["status"] == "COMPLETED"
    assert body["feature_count"] == 2
    assert body["crs"] == "EPSG:4326"
    assert body["error"] is None


def test_get_file_info(client, upload, tmp_path):
    zip_path = make_shapefile_zip([POLYGON], tmp_path, name="one")
    file_id = upload("one.zip", zip_path.read_bytes()).json()["id"]

    resp = client.get(f"/api/files/{file_id}/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == file_id
    assert body["feature_count"] == 1
    assert body["status"] == "COMPLETED"


def test_upload_kml(upload):
    resp = upload("survey.kml", KML_MIXED.encode())
    assert resp.status_code == 201
    body = resp.json()
    assert body["file_type"] == "kml"
    assert body["feature_count"] == 3
    assert body["crs"] == "EPSG:4326"


# ---------- measurements ----------

def test_polygon_measurements_match_geodesic_reference(client, upload, tmp_path):
    zip_path = make_shapefile_zip([POLYGON, POLYGON_2], tmp_path, name="plots")
    file_id = upload("plots.zip", zip_path.read_bytes()).json()["id"]

    resp = client.get(f"/api/files/{file_id}/measurements/")
    assert resp.status_code == 200
    body = resp.json()

    first, second = body["measurements"]
    assert first["status"] == "OK"
    assert first["geometry_type"] == "Polygon"
    assert first["measurement"]["type"] == "area"
    assert first["measurement"]["unit"] == "m2"
    assert first["measurement"]["projected_crs"] == "EPSG:32643"
    assert first["measurement"]["value"] == pytest.approx(geodesic_area(POLYGON), rel=5e-3)
    assert second["measurement"]["value"] == pytest.approx(
        geodesic_area(POLYGON_2), rel=5e-3
    )

    expected_total = geodesic_area(POLYGON) + geodesic_area(POLYGON_2)
    assert body["summary"]["total_area_m2"] == pytest.approx(expected_total, rel=5e-3)
    assert body["summary"]["measured_features"] == 2
    assert body["summary"]["unmeasured_features"] == 0


def test_line_measurements(client, upload, tmp_path):
    zip_path = make_shapefile_zip([LINE, LINE_2], tmp_path, name="roads")
    file_id = upload("roads.zip", zip_path.read_bytes()).json()["id"]

    body = client.get(f"/api/files/{file_id}/measurements/").json()
    first = body["measurements"][0]
    assert first["geometry_type"] == "LineString"
    assert first["measurement"]["type"] == "length"
    assert first["measurement"]["unit"] == "m"
    assert first["measurement"]["value"] == pytest.approx(geodesic_length(LINE), rel=5e-3)


def test_mixed_kml_measurements_and_point_handling(client, upload):
    file_id = upload("survey.kml", KML_MIXED.encode()).json()["id"]
    body = client.get(f"/api/files/{file_id}/measurements/").json()

    by_type = {m["geometry_type"]: m for m in body["measurements"]}
    assert by_type["Polygon"]["measurement"]["value"] == pytest.approx(
        geodesic_area(POLYGON), rel=5e-3
    )
    assert by_type["LineString"]["measurement"]["value"] == pytest.approx(
        geodesic_length(LINE), rel=5e-3
    )
    # Points: no measurement, and no crash.
    assert by_type["Point"]["status"] == "NOT_APPLICABLE"
    assert by_type["Point"]["measurement"] is None
    assert body["summary"]["measured_features"] == 2
    assert body["summary"]["unmeasured_features"] == 1


def test_projected_input_crs_is_handled(client, upload, tmp_path):
    """A Shapefile already in UTM metres must give the same area as the lon/lat one."""
    zip_path = make_shapefile_zip([POLYGON], tmp_path, name="utm", crs="EPSG:32643")
    resp = upload("utm.zip", zip_path.read_bytes())
    assert resp.status_code == 201
    assert resp.json()["crs"] == "EPSG:32643"

    body = client.get(f"/api/files/{resp.json()['id']}/measurements/").json()
    assert body["measurements"][0]["measurement"]["value"] == pytest.approx(
        geodesic_area(POLYGON), rel=5e-3
    )


def test_measurements_pagination(client, upload, tmp_path):
    zip_path = make_shapefile_zip([POLYGON, POLYGON_2], tmp_path, name="plots")
    file_id = upload("plots.zip", zip_path.read_bytes()).json()["id"]

    body = client.get(f"/api/files/{file_id}/measurements/?limit=1&offset=1").json()
    assert len(body["measurements"]) == 1
    assert body["measurements"][0]["feature_index"] == 1
    # Summary always covers the whole file, not just the page.
    assert body["summary"]["measured_features"] == 2


# ---------- features ----------

def test_features_endpoint_returns_geometry_crs_and_properties(client, upload, tmp_path):
    zip_path = make_shapefile_zip([POLYGON], tmp_path, name="one")
    file_id = upload("one.zip", zip_path.read_bytes()).json()["id"]

    body = client.get(f"/api/files/{file_id}/features/").json()
    feature = body["features"][0]
    assert feature["feature_index"] == 0
    assert feature["geometry_type"] == "Polygon"
    assert feature["geometry"]["type"] == "Polygon"
    assert feature["crs"] == "EPSG:4326"
    assert feature["properties"]["name"] == "feature 0"


# ---------- validation and errors ----------

def test_unsupported_extension_is_rejected(upload):
    resp = upload("notes.txt", b"hello")
    assert resp.status_code == 415


def test_corrupt_zip_marks_file_failed(client, upload):
    resp = upload("broken.zip", b"this is not a zip file")
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["status"] == "FAILED"

    info = client.get(f"/api/files/{detail['id']}/").json()
    assert info["status"] == "FAILED"
    assert info["error"]


def test_zip_without_shapefile_is_rejected(upload, tmp_path):
    import zipfile

    path = tmp_path / "empty.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("readme.txt", "no shapefile here")
    resp = upload("empty.zip", path.read_bytes())
    assert resp.status_code == 422
    assert ".shp" in resp.json()["detail"]["message"]


def test_shapefile_without_crs_is_rejected(upload, tmp_path):
    zip_path = make_shapefile_zip([POLYGON], tmp_path, name="nocrs", drop_prj=True)
    resp = upload("nocrs.zip", zip_path.read_bytes())
    assert resp.status_code == 422
    assert "CRS" in resp.json()["detail"]["message"]


def test_invalid_kml_is_rejected(upload):
    resp = upload("bad.kml", b"<not-really-kml>")
    assert resp.status_code == 422
    assert resp.json()["detail"]["status"] == "FAILED"


def test_unknown_file_id_returns_404(client):
    assert client.get("/api/files/doesnotexist/").status_code == 404
    assert client.get("/api/files/doesnotexist/measurements/").status_code == 404


def test_measurements_of_failed_file_return_409(client, upload):
    file_id = upload("broken.zip", b"nope").json()["detail"]["id"]
    assert client.get(f"/api/files/{file_id}/measurements/").status_code == 409


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_root_ui(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Geospatial File Measurement API" in resp.text


def test_get_sample_shapefile(client):
    resp = client.get("/api/files/sample-shapefile")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"




