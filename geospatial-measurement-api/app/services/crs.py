"""CRS helpers: label a CRS and pick a projected CRS suitable for measuring."""
from pyproj import CRS


def crs_label(crs: CRS) -> str:
    """Short human-readable label, e.g. 'EPSG:4326'. Falls back to the CRS name."""
    epsg = crs.to_epsg()
    return f"EPSG:{epsg}" if epsg else crs.name


def utm_crs_for_lonlat(lon: float, lat: float) -> CRS:
    """Return the WGS84 UTM zone CRS that contains the given longitude/latitude.

    UTM zones are 6 degrees wide, so distortion inside a zone is small
    (well under 0.1% for lengths and areas near the central meridian).
    Beyond 84N / 80S UTM is not defined, so we use the Universal Polar
    Stereographic CRSs there.
    """
    if lat >= 84:
        return CRS.from_epsg(32661)  # WGS84 / UPS North
    if lat <= -80:
        return CRS.from_epsg(32761)  # WGS84 / UPS South

    lon = ((lon + 180) % 360) - 180  # normalise to [-180, 180)
    zone = int((lon + 180) // 6) + 1
    zone = min(max(zone, 1), 60)
    base = 32600 if lat >= 0 else 32700  # 326xx = north, 327xx = south
    return CRS.from_epsg(base + zone)
