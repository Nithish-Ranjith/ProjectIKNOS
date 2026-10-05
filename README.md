# IKNOS — IKNOS Land Survey Platform

> **Drone-powered land boundary verification and dispute resolution for Andhra Pradesh**

IKNOS is a full-stack, AI-assisted land survey platform that helps settlement officers and drone surveyors detect, verify, and resolve cadastral boundary disputes using drone photogrammetry, U-Net AI boundary detection, and PostGIS spatial analysis.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        IKNOS Platform                           │
├─────────────────┬───────────────────────┬───────────────────────┤
│   React Web App │   FastAPI Backend      │   Supabase (Postgres) │
│   (Vite + TS)   │   (Python 3.14)       │   + PostGIS           │
├─────────────────┴───────────────────────┴───────────────────────┤
│  Mapbox GL    │  U-Net Boundary AI  │  OpenDroneMap (ODM)       │
│  Sentinel-2   │  PostGIS Spatial    │  WeasyPrint PDF Reports   │
└───────────────────────────────────────────────────────────────-─┘
```

## Roles

| Role | Description |
|------|-------------|
| **Admin** | Settlement Officer — reviews AI-flagged cases, makes decisions |
| **Surveyor (Drone)** | Conducts drone missions, reviews QC, triggers processing |
| **User (Landowner)** | Views parcel status, files grievances, tracks progress |

## Mission Pipeline (Surveyor Flow)

```
Parcel Load → Boundary Review → Plan Mission → Fly → Capture & QC → Process → Report
```

1. **Parcel** — Load cadastral boundary, review U-Net AI detection, approve or adjust
2. **Plan** — Auto-generate lawnmower flight plan, review waypoints and altitude profile
3. **Fly** — Live telemetry display, block-by-block coverage tracking
4. **Capture & QC** — Review 92-frame photo evidence grid, check QC score (≥80% required)
5. **Process** — 6-stage photogrammetry pipeline (SfM → Dense → Ortho → Index)
6. **Report** — Download PDF report with spatial discrepancy analysis and audit trail

---

## Tech Stack

### Frontend (`/webapp`)
- **Vite + React + TypeScript**
- **Mapbox GL JS** — satellite imagery, boundary layers, live drone marker
- **Supabase JS** — authentication, realtime
- **WeasyPrint** — PDF report generation (server-side)

### Backend (`/backend`)
- **FastAPI** (Python 3.14)
- **SQLAlchemy + PostGIS** — spatial queries via `psycopg2`
- **Jinja2 + WeasyPrint** — PDF report templates
- **Supabase PostgreSQL** — hosted database (Mumbai region)

---

## Getting Started

### Prerequisites
- Node.js 20+
- Python 3.11+
- A Supabase project with PostGIS enabled
- A Mapbox account (free tier works)

### 1. Clone
```bash
git clone https://github.com/YOUR_USERNAME/ProjectIKNOS.git
cd ProjectIKNOS
```

### 2. Backend Setup
```bash
cd backend
python3 -m venv ../venv
source ../venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Supabase DATABASE_URL and JWT_SECRET

uvicorn app.main:app --reload --port 8000
```

### 3. Frontend Setup
```bash
cd webapp
cp .env.example .env
# Edit .env with your Supabase URL, anon key, and Mapbox token

npm install
npm run dev
```

### 4. Demo Login
| Email | Password | Role |
|-------|----------|------|
| `admin@demo.com` | `password123` | Admin (Settlement Officer) |
| `drone1@demo.com` | `password123` | Surveyor (Drone Operator) |
| `user@demo.com` | `password123` | User (Landowner) |

---

## Key Features

- ✅ **AI Boundary Detection** — U-Net model detects parcel boundaries from drone imagery
- ✅ **Real PostGIS Spatial Analysis** — ST_Hausdorff, ST_Intersection, ST_Difference
- ✅ **Live Mission Control** — Telemetry HUD, block tracking, simulated drone flight
- ✅ **QC Grid** — 92-frame photo evidence review with pass/fail scoring
- ✅ **Processing Pipeline** — SfM → Dense → Orthorectification simulation with live logs
- ✅ **PDF Report Generation** — WeasyPrint-rendered reports with spatial evidence
- ✅ **Interactive Layer Toggles** — Show/hide cadastral, AI boundary, flight plan, coverage layers
- ✅ **Role-based Dashboards** — Admin, Surveyor, and User views

---

## Database Schema (Supabase / PostgreSQL + PostGIS)

Key tables: `users`, `parcels` (with PostGIS `geom`), `cases`, `missions`, `mission_images`, `discrepancy_metrics`, `audit_log`, `field_verifications`

---

## Project Structure

```
ProjectIKNOS/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── main.py         # All API routes
│   │   ├── models.py       # SQLAlchemy models
│   │   ├── schemas.py      # Pydantic schemas
│   │   ├── auth.py         # JWT + demo auth
│   │   ├── spatial_service.py  # PostGIS spatial analysis
│   │   └── templates/      # Jinja2 HTML for PDF reports
│   └── requirements.txt
├── webapp/                  # React frontend
│   ├── src/
│   │   ├── pages/          # Admin, Surveyor, User pages
│   │   ├── components/     # MapboxMap, Mission components
│   │   ├── services/api.ts # All backend API calls
│   │   └── types/          # TypeScript types
│   └── package.json
└── README.md
```

---

## License

MIT — see [LICENSE](LICENSE)
