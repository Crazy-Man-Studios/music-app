# Full-Stack Music App

A starter full-blown music platform with:

- **React frontend** with sidebar navigation, account management, search, playlists, artist upload, and staff review UI.
- **Python FastAPI backend** for auth, playlist endpoints, artist uploads, and moderation.
- **Filesystem-backed publication storage** in the requested layout:

```text
backend/data/music/{artist_id}/{publication_id}/
  cover.png
  metadata.json
  songs/{uploaded song files}
```

Uploaded cover files are normalized to PNG using Pillow while songs are retained in uploaded format.

## Project Structure

```text
backend/
  src/
    main.py
    auth.py
    models.py
    storage.py
  data/
    music/
frontend/
  src/
```

## Run backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000
```

## Run frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend expects backend on `http://127.0.0.1:8000`.

## Roles

- `listener`: browse music + playlists
- `artist`: listener permissions + upload releases
- `staff`: listener permissions + approve/reject artist publications
