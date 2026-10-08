"""FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from app import models  # noqa: F401  (registers tables on Base.metadata)
from app.database import Base, engine
from app.routers import files


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Geospatial File Measurement API",
    description="Upload a zipped Shapefile or a KML file and get area/length measurements.",
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(files.router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse, tags=["ui"])
def root_ui():
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Geospatial File Measurement API</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0b0f19;
      --card-bg: rgba(18, 24, 38, 0.8);
      --border: rgba(255, 255, 255, 0.1);
      --accent: #3b82f6;
      --accent-glow: rgba(59, 130, 246, 0.25);
      --accent-green: #10b981;
      --text: #f3f4f6;
      --text-muted: #9ca3af;
      --font-main: 'Outfit', -apple-system, sans-serif;
      --font-code: 'JetBrains Mono', monospace;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: var(--font-main);
      background-color: var(--bg);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      background-image: 
        radial-gradient(circle at 15% 15%, rgba(59, 130, 246, 0.12) 0%, transparent 45%),
        radial-gradient(circle at 85% 85%, rgba(16, 185, 129, 0.08) 0%, transparent 45%);
    }
    header {
      border-bottom: 1px solid var(--border);
      backdrop-filter: blur(12px);
      background: rgba(11, 15, 25, 0.7);
      position: sticky;
      top: 0;
      z-index: 10;
    }
    .header-container {
      max-width: 1100px;
      margin: 0 auto;
      padding: 1rem 1.5rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .logo-title {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }
    .logo-icon {
      width: 38px;
      height: 38px;
      background: linear-gradient(135deg, #3b82f6, #10b981);
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      box-shadow: 0 0 15px var(--accent-glow);
    }
    h1 { font-size: 1.25rem; font-weight: 600; letter-spacing: -0.01em; }
    .badge {
      font-size: 0.75rem;
      padding: 0.25rem 0.6rem;
      border-radius: 20px;
      background: rgba(16, 185, 129, 0.15);
      color: var(--accent-green);
      border: 1px solid rgba(16, 185, 129, 0.3);
      font-weight: 500;
    }
    .nav-links {
      display: flex;
      gap: 1rem;
    }
    .nav-links a {
      color: var(--text-muted);
      text-decoration: none;
      font-size: 0.9rem;
      font-weight: 500;
      transition: color 0.2s;
      display: flex;
      align-items: center;
      gap: 0.35rem;
    }
    .nav-links a:hover { color: var(--text); }
    main {
      flex: 1;
      max-width: 1100px;
      width: 100%;
      margin: 2rem auto;
      padding: 0 1.5rem;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 2rem;
    }
    @media (max-width: 850px) {
      main { grid-template-columns: 1fr; }
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 1.75rem;
      box-shadow: 0 10px 30px rgba(0,0,0,0.3);
      backdrop-filter: blur(12px);
    }
    .card-title {
      font-size: 1.1rem;
      font-weight: 600;
      margin-bottom: 0.5rem;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .card-desc {
      color: var(--text-muted);
      font-size: 0.875rem;
      margin-bottom: 1.5rem;
      line-height: 1.5;
    }
    .dropzone {
      border: 2px dashed rgba(255, 255, 255, 0.18);
      border-radius: 12px;
      padding: 2.5rem 1.5rem;
      text-align: center;
      cursor: pointer;
      transition: all 0.2s ease;
      background: rgba(255, 255, 255, 0.02);
    }
    .dropzone:hover, .dropzone.dragover {
      border-color: var(--accent);
      background: rgba(59, 130, 246, 0.05);
      box-shadow: 0 0 20px var(--accent-glow);
    }
    .dropzone-icon {
      font-size: 2.5rem;
      margin-bottom: 0.75rem;
      display: block;
    }
    .file-input { display: none; }
    .btn {
      background: linear-gradient(135deg, #3b82f6, #2563eb);
      color: white;
      border: none;
      padding: 0.75rem 1.25rem;
      border-radius: 8px;
      font-weight: 600;
      font-size: 0.9rem;
      cursor: pointer;
      transition: all 0.2s;
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
    }
    .btn:hover { opacity: 0.95; transform: translateY(-1px); }
    .btn-secondary {
      background: rgba(255,255,255,0.08);
      border: 1px solid var(--border);
      color: var(--text);
    }
    .btn-secondary:hover { background: rgba(255,255,255,0.12); }
    .results-container {
      display: flex;
      flex-direction: column;
      gap: 1.25rem;
    }
    .summary-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 0.75rem;
    }
    .stat-box {
      background: rgba(255,255,255,0.03);
      border: 1px solid var(--border);
      padding: 1rem;
      border-radius: 10px;
    }
    .stat-label { font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }
    .stat-value { font-size: 1.25rem; font-weight: 700; margin-top: 0.25rem; color: var(--text); }
    .table-wrapper {
      overflow-x: auto;
      border: 1px solid var(--border);
      border-radius: 10px;
      background: rgba(0,0,0,0.2);
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.85rem;
    }
    th, td {
      padding: 0.75rem 1rem;
      text-align: left;
      border-bottom: 1px solid var(--border);
    }
    th {
      background: rgba(255, 255, 255, 0.04);
      color: var(--text-muted);
      font-weight: 600;
    }
    tr:last-child td { border-bottom: none; }
    .tag {
      font-family: var(--font-code);
      font-size: 0.75rem;
      padding: 0.15rem 0.4rem;
      border-radius: 4px;
      background: rgba(255,255,255,0.08);
    }
    .tag-polygon { background: rgba(59, 130, 246, 0.2); color: #60a5fa; }
    .tag-linestring { background: rgba(16, 185, 129, 0.2); color: #34d399; }
    .loader {
      display: none;
      text-align: center;
      padding: 2rem;
      color: var(--text-muted);
    }
    footer {
      border-top: 1px solid var(--border);
      text-align: center;
      padding: 1.25rem;
      color: var(--text-muted);
      font-size: 0.85rem;
    }
  </style>
</head>
<body>
  <header>
    <div class="header-container">
      <div class="logo-title">
        <div class="logo-icon">GEO</div>
        <div>
          <h1>Geospatial Measurement API</h1>
        </div>
        <span class="badge">Online</span>
      </div>
      <div class="nav-links">
        <a href="/docs" target="_blank">Swagger Docs ↗</a>
        <a href="/redoc" target="_blank">ReDoc ↗</a>
        <a href="/health" target="_blank">Health</a>
      </div>
    </div>
  </header>

  <main>
    <section class="card">
      <h2 class="card-title">🌐 Upload Geospatial File</h2>
      <p class="card-desc">Upload a zipped Shapefile (<code>.zip</code>) or a <code>.kml</code> file. Geometries will be extracted and measured in projected metric units (m² / m).</p>
      
      <div class="dropzone" id="dropzone" onclick="document.getElementById('fileInput').click()">
        <span class="dropzone-icon">📁</span>
        <p style="font-weight: 600; margin-bottom: 0.25rem;">Click to upload or drag & drop</p>
        <p style="font-size: 0.8rem; color: var(--text-muted);">Supports .zip (Shapefile) or .kml files</p>
        <input type="file" id="fileInput" class="file-input" accept=".zip,.kml" onchange="handleFileSelect(event)">
      </div>

      <div style="margin-top: 1rem; padding: 0.85rem; border-radius: 10px; background: rgba(59, 130, 246, 0.06); border: 1px solid rgba(59, 130, 246, 0.2); font-size: 0.8rem; line-height: 1.5; color: var(--text-muted);">
        <strong style="color: #60a5fa; font-weight: 600;">📦 Shapefile ZIP Instructions:</strong> A Shapefile consists of multiple files (<code>.shp</code>, <code>.shx</code>, <code>.dbf</code>, and <code>.prj</code>). Select all of these files together, zip them into a <code>.zip</code> archive, and upload it here.
      </div>

      <div style="margin-top: 1.25rem; display: flex; gap: 0.75rem; flex-wrap: wrap;">
        <button class="btn btn-secondary" onclick="uploadSample()">⚡ Process Sample KML</button>
        <button class="btn btn-secondary" onclick="uploadSampleShapefile()">⚡ Process Sample Shapefile ZIP</button>
      </div>



      <div id="errorBanner" style="display: none; margin-top: 1.25rem; padding: 1rem; border-radius: 10px; background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.3); color: #fca5a5; font-size: 0.875rem;">
        <div style="display: flex; align-items: flex-start; gap: 0.6rem;">
          <span style="font-size: 1.2rem; line-height: 1;">⚠️</span>
          <div>
            <strong style="color: #f87171; display: block; margin-bottom: 0.25rem;" id="errorTitle">Upload Error</strong>
            <span id="errorMessage">Invalid file format.</span>
            <div id="errorHint" style="margin-top: 0.5rem; font-size: 0.8rem; color: #fca5a5; opacity: 0.85;"></div>
          </div>
        </div>
      </div>

      <div id="loader" class="loader">
        <p>Processing geometry & computing UTM measurements...</p>
      </div>
    </section>

    <section class="card">
      <h2 class="card-title">📊 Measurement Results</h2>
      <p class="card-desc">Computed area and length values in projected coordinate systems (WGS84 UTM zones).</p>
      
      <div id="emptyState" style="text-align: center; padding: 3rem 1rem; color: var(--text-muted);">
        <p style="font-size: 2rem; margin-bottom: 0.5rem;">📐</p>
        <p>No file uploaded yet. Upload a file or click one of the sample buttons to view measurements.</p>
      </div>

      <div id="resultsContent" class="results-container" style="display: none;">
        <div class="summary-grid">
          <div class="stat-box">
            <div class="stat-label">Total Area</div>
            <div class="stat-value" id="totalArea">0 m²</div>
          </div>
          <div class="stat-box">
            <div class="stat-label">Total Length</div>
            <div class="stat-value" id="totalLength">0 m</div>
          </div>
          <div class="stat-box">
            <div class="stat-label">Measured Features</div>
            <div class="stat-value" id="measuredCount">0</div>
          </div>
          <div class="stat-box">
            <div class="stat-label">Input CRS</div>
            <div class="stat-value" id="inputCrs" style="font-size: 0.95rem; font-family: var(--font-code);">EPSG:4326</div>
          </div>
        </div>

        <div class="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Index</th>
                <th>Type</th>
                <th>Measurement</th>
                <th>Projected CRS</th>
              </tr>
            </thead>
            <tbody id="measurementsBody">
            </tbody>
          </table>
        </div>
      </div>
    </section>
  </main>

  <footer>
    <p>Geospatial File Measurement API • Powered by FastAPI, GeoPandas & PyProj</p>
  </footer>

  <script>
    const dropzone = document.getElementById('dropzone');

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
      dropzone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
      e.preventDefault();
      e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
      dropzone.addEventListener(eventName, () => dropzone.classList.add('dragover'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
      dropzone.addEventListener(eventName, () => dropzone.classList.remove('dragover'), false);
    });

    dropzone.addEventListener('drop', (e) => {
      const dt = e.dataTransfer;
      const files = dt.files;
      if (files.length) uploadFile(files[0]);
    });

    function handleFileSelect(e) {
      if (e.target.files.length) uploadFile(e.target.files[0]);
    }

    async function uploadFile(file) {
      const formData = new FormData();
      formData.append('file', file);
      processUpload(formData);
    }

    async function uploadSample() {
      const sampleKml = `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Sample Polygon</name>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>77.59,12.97,0 77.60,12.97,0 77.60,12.98,0 77.59,12.98,0 77.59,12.97,0</coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
    <Placemark>
      <name>Sample Line</name>
      <LineString>
        <coordinates>77.59,12.97,0 77.60,12.98,0</coordinates>
      </LineString>
    </Placemark>
    <Placemark>
      <name>Sample Point</name>
      <Point>
        <coordinates>77.595,12.975,0</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>`;
      const blob = new Blob([sampleKml], { type: 'application/vnd.google-earth.kml+xml' });
      const formData = new FormData();
      formData.append('file', blob, 'sample.kml');
      processUpload(formData);
    }

    async function uploadSampleShapefile() {
      try {
        const res = await fetch('/api/files/sample-shapefile');
        if (!res.ok) throw new Error('Could not download sample shapefile');
        const blob = await res.blob();
        const formData = new FormData();
        formData.append('file', blob, 'sample_shapefile.zip');
        processUpload(formData);
      } catch (err) {
        showError('Could not fetch sample shapefile: ' + err.message);
      }
    }




    function showError(msg, hint = '') {
      document.getElementById('errorBanner').style.display = 'block';
      document.getElementById('errorMessage').innerText = msg;
      document.getElementById('errorHint').innerText = hint;
    }

    function clearError() {
      document.getElementById('errorBanner').style.display = 'none';
      document.getElementById('errorMessage').innerText = '';
      document.getElementById('errorHint').innerText = '';
    }

    async function processUpload(formData) {
      clearError();
      document.getElementById('loader').style.display = 'block';
      document.getElementById('emptyState').style.display = 'none';
      document.getElementById('resultsContent').style.display = 'none';

      try {
        const uploadRes = await fetch('/api/files/', { method: 'POST', body: formData });
        const uploadData = await uploadRes.json();
        
        if (!uploadRes.ok) {
          let errorMsg = 'Upload failed.';
          let errorHint = '';

          if (uploadData && uploadData.detail) {
            if (typeof uploadData.detail === 'object' && uploadData.detail.message) {
              errorMsg = uploadData.detail.message;
            } else if (typeof uploadData.detail === 'string') {
              errorMsg = uploadData.detail;
            } else {
              errorMsg = JSON.stringify(uploadData.detail);
            }
          }

          if (errorMsg.includes('.shp')) {
            errorHint = '💡 Tip: A Shapefile ZIP must contain a .shp file along with its companion files (.shx, .dbf, and .prj). Make sure you select all files and zip them directly.';
          } else if (errorMsg.includes('CRS') || errorMsg.includes('.prj')) {
            errorHint = '💡 Tip: Coordinate Reference System missing. Ensure your zipped Shapefile includes the .prj file.';
          }

          showError(errorMsg, errorHint);
          document.getElementById('loader').style.display = 'none';
          document.getElementById('emptyState').style.display = 'block';
          return;
        }

        const fileId = uploadData.id;
        const measureRes = await fetch(`/api/files/${fileId}/measurements/`);
        const measureData = await measureRes.json();

        displayResults(measureData);
      } catch (err) {
        showError('An unexpected network or server error occurred: ' + err.message);
        document.getElementById('emptyState').style.display = 'block';
      } finally {
        document.getElementById('loader').style.display = 'none';
      }
    }

    function displayResults(data) {
      clearError();
      document.getElementById('totalArea').innerText = (data.summary.total_area_m2 || 0).toLocaleString(undefined, {maximumFractionDigits: 2}) + ' m²';
      document.getElementById('totalLength').innerText = (data.summary.total_length_m || 0).toLocaleString(undefined, {maximumFractionDigits: 2}) + ' m';
      document.getElementById('measuredCount').innerText = `${data.summary.measured_features} / ${data.feature_count}`;
      document.getElementById('inputCrs').innerText = data.crs || 'N/A';

      const tbody = document.getElementById('measurementsBody');
      tbody.innerHTML = '';

      data.measurements.forEach(m => {
        const tr = document.createElement('tr');
        
        let typeTagClass = 'tag';
        if (m.geometry_type === 'Polygon') typeTagClass += ' tag-polygon';
        if (m.geometry_type === 'LineString') typeTagClass += ' tag-linestring';

        let measText = 'N/A';
        let crsText = 'N/A';
        if (m.measurement) {
          measText = `${m.measurement.value.toLocaleString(undefined, {maximumFractionDigits: 2})} ${m.measurement.unit}`;
          crsText = m.measurement.projected_crs;
        } else if (m.note) {
          measText = `<span style="color: var(--text-muted); font-size: 0.8rem;">${m.note}</span>`;
        }

        tr.innerHTML = `
          <td>#${m.feature_index}</td>
          <td><span class="${typeTagClass}">${m.geometry_type}</span></td>
          <td>${measText}</td>
          <td style="font-family: var(--font-code); font-size: 0.8rem;">${crsText}</td>
        `;
        tbody.appendChild(tr);
      });

      document.getElementById('resultsContent').style.display = 'flex';
    }
  </script>
</body>
</html>
"""


