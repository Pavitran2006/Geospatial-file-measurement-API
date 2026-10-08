"""HTTP endpoints for uploading geospatial files and reading their results."""
import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES
from app.database import get_db
from app.models import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    Feature,
    UploadedFile,
)
from app.schemas import (
    FeatureMeasurementOut,
    FeatureOut,
    FeaturesOut,
    FileOut,
    MeasurementsOut,
    MeasurementSummary,
    MeasurementValue,
)
from app.services.file_processing import (
    FileProcessingError,
    detect_file_type,
    process_file,
)
from app.services.measurements import OK

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("/sample-shapefile", response_class=FileResponse)
def get_sample_shapefile():
    """Download the sample Shapefile (.zip)."""
    sample_path = Path("samples/sample_shapefile.zip")
    if not sample_path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sample shapefile not found.")
    return FileResponse(
        sample_path,
        media_type="application/zip",
        filename="sample_shapefile.zip",
    )


def _get_file_or_404(db: Session, file_id: str) -> UploadedFile:

    record = db.get(UploadedFile, file_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found.")
    return record


def _get_completed_file(db: Session, file_id: str) -> UploadedFile:
    record = _get_file_or_404(db, file_id)
    if record.status != STATUS_COMPLETED:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"File is not ready (status: {record.status}).",
        )
    return record


def _save_upload(upload: UploadFile, dest: Path) -> None:
    """Stream the upload to disk in chunks, enforcing the size limit."""
    written = 0
    with dest.open("wb") as out:
        while chunk := upload.file.read(1024 * 1024):
            written += len(chunk)
            if written > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
                )
            out.write(chunk)


@router.post("/", response_model=FileOut, status_code=status.HTTP_201_CREATED)
def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a zipped Shapefile (.zip) or a .kml file and process it."""
    filename = Path(file.filename or "").name
    file_type = detect_file_type(filename)
    if file_type is None:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        saved = workdir / f"upload{Path(filename).suffix.lower()}"
        _save_upload(file, saved)

        record = UploadedFile(filename=filename, file_type=file_type)
        db.add(record)
        db.commit()

        try:
            result = process_file(saved, file_type, workdir)
        except FileProcessingError as exc:
            record.status = STATUS_FAILED
            record.error = str(exc)
            db.commit()
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"id": record.id, "status": STATUS_FAILED, "message": str(exc)},
            )
        except Exception:
            logger.exception("Unexpected error while processing file %s", record.id)
            record.status = STATUS_FAILED
            record.error = "Unexpected error while processing the file."
            db.commit()
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"id": record.id, "status": STATUS_FAILED, "message": record.error},
            )

    db.add_all([Feature(file_id=record.id, **f) for f in result.features])
    record.crs = result.crs
    record.feature_count = len(result.features)
    record.status = STATUS_COMPLETED
    db.commit()
    return record


@router.get("/{file_id}/", response_model=FileOut)
def get_file(file_id: str, db: Session = Depends(get_db)):
    """Basic information and processing status of an uploaded file."""
    return _get_file_or_404(db, file_id)


@router.get("/{file_id}/features/", response_model=FeaturesOut)
def get_features(
    file_id: str,
    limit: int = Query(1000, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Geometry, CRS and attributes of each feature."""
    record = _get_completed_file(db, file_id)
    rows = db.scalars(
        select(Feature)
        .where(Feature.file_id == file_id)
        .order_by(Feature.feature_index)
        .limit(limit)
        .offset(offset)
    ).all()
    return FeaturesOut(
        file_id=file_id,
        feature_count=record.feature_count,
        limit=limit,
        offset=offset,
        features=[
            FeatureOut(
                feature_index=r.feature_index,
                geometry_type=r.geometry_type,
                geometry=r.geometry,
                crs=r.crs,
                properties=r.properties,
            )
            for r in rows
        ],
    )


@router.get("/{file_id}/measurements/", response_model=MeasurementsOut)
def get_measurements(
    file_id: str,
    limit: int = Query(1000, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Area (polygons) and length (lines) for every feature in the file."""
    record = _get_completed_file(db, file_id)

    rows = db.scalars(
        select(Feature)
        .where(Feature.file_id == file_id)
        .order_by(Feature.feature_index)
        .limit(limit)
        .offset(offset)
    ).all()

    def total(kind: str) -> float:
        value = db.scalar(
            select(func.coalesce(func.sum(Feature.measurement_value), 0.0)).where(
                Feature.file_id == file_id, Feature.measurement_type == kind
            )
        )
        return round(float(value), 4)

    measured = db.scalar(
        select(func.count()).where(
            Feature.file_id == file_id, Feature.measurement_status == OK
        )
    )

    measurements = [
        FeatureMeasurementOut(
            feature_index=r.feature_index,
            geometry_type=r.geometry_type,
            status=r.measurement_status,
            measurement=(
                MeasurementValue(
                    type=r.measurement_type,
                    value=r.measurement_value,
                    unit=r.measurement_unit,
                    projected_crs=r.projected_crs,
                )
                if r.measurement_status == OK
                else None
            ),
            note=r.note,
        )
        for r in rows
    ]

    return MeasurementsOut(
        file_id=file_id,
        crs=record.crs,
        feature_count=record.feature_count,
        limit=limit,
        offset=offset,
        summary=MeasurementSummary(
            total_area_m2=total("area"),
            total_length_m=total("length"),
            measured_features=measured,
            unmeasured_features=record.feature_count - measured,
        ),
        measurements=measurements,
    )
