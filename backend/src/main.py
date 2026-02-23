from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt

from .auth import ALGORITHM, SECRET_KEY, create_access_token, hash_password, verify_password
from .models import (
    ApprovalAction,
    Playlist,
    PlaylistAddSong,
    PlaylistCreate,
    SearchResult,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserPublic,
)
from .storage import MUSIC_DIR, ensure_data_dirs, list_publications, read_db, save_publication, update_publication_status, write_db

app = FastAPI(title="Music App API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


ensure_data_dirs()
app.mount("/files", StaticFiles(directory=MUSIC_DIR), name="files")


def require_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.replace("Bearer ", "", 1)
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    user_id = payload.get("sub")
    db = read_db()
    user = next((item for item in db["users"] if item["id"] == user_id), None)
    if user is None:
        raise HTTPException(status_code=401, detail="Unknown user")
    return user




def optional_user(authorization: str | None = Header(default=None)) -> dict | None:
    if not authorization:
        return None
    if not authorization.startswith("Bearer "):
        return None
    token = authorization.replace("Bearer ", "", 1)
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None

    user_id = payload.get("sub")
    db = read_db()
    return next((item for item in db["users"] if item["id"] == user_id), None)


def require_roles(*roles: str):
    def _guard(user: dict = Depends(require_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user

    return _guard


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/register", response_model=TokenResponse)
def register(payload: UserCreate) -> TokenResponse:
    db = read_db()
    if any(user["username"] == payload.username for user in db["users"]):
        raise HTTPException(status_code=400, detail="Username exists")

    user = {
        "id": str(uuid4()),
        "username": payload.username,
        "email": payload.email,
        "password_hash": hash_password(payload.password),
        "role": payload.role,
    }
    db["users"].append(user)
    write_db(db)

    token = create_access_token({"sub": user["id"], "role": user["role"]})
    public = UserPublic(id=user["id"], username=user["username"], email=user["email"], role=user["role"])
    return TokenResponse(access_token=token, user=public)


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: UserLogin) -> TokenResponse:
    db = read_db()
    user = next((item for item in db["users"] if item["username"] == payload.username), None)
    if user is None or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": user["id"], "role": user["role"]})
    public = UserPublic(id=user["id"], username=user["username"], email=user["email"], role=user["role"])
    return TokenResponse(access_token=token, user=public)


@app.get("/me", response_model=UserPublic)
def me(user: dict = Depends(require_user)) -> UserPublic:
    return UserPublic(id=user["id"], username=user["username"], email=user["email"], role=user["role"])


@app.get("/search", response_model=list[SearchResult])
def search(query: str = "") -> list[SearchResult]:
    query_lower = query.strip().lower()
    publications = list_publications(include_pending=False)
    items = [
        SearchResult(
            publication_id=pub.publication_id,
            artist_id=pub.artist_id,
            title=pub.title,
            genre=pub.genre,
            status=pub.status,
        )
        for pub in publications
        if not query_lower
        or query_lower in pub.title.lower()
        or query_lower in pub.genre.lower()
        or query_lower in pub.artist_id.lower()
    ]
    return items


@app.get("/publications")
def publications(user: dict | None = Depends(optional_user)) -> list[dict]:
    include_pending = user is not None and user["role"] in {"staff", "artist"}
    records = list_publications(include_pending=include_pending)
    if user is None:
        records = [record for record in records if record.status == "approved"]
    return [record.model_dump() for record in records]


@app.post("/artist/upload")
async def artist_upload(
    title: str = Form(...),
    genre: str = Form(...),
    description: str = Form(""),
    cover: UploadFile = File(...),
    songs: list[UploadFile] = File(...),
    user: dict = Depends(require_roles("artist")),
) -> dict:
    with NamedTemporaryFile(delete=False, suffix=Path(cover.filename or "cover.png").suffix) as cover_tmp_file:
        shutil.copyfileobj(cover.file, cover_tmp_file)
        cover_tmp = Path(cover_tmp_file.name)

    songs_tmp: list[Path] = []
    for song in songs:
        with NamedTemporaryFile(delete=False, suffix=Path(song.filename or "track").suffix) as song_tmp_file:
            shutil.copyfileobj(song.file, song_tmp_file)
            songs_tmp.append(Path(song_tmp_file.name))

    metadata = save_publication(
        artist_id=user["id"],
        title=title,
        genre=genre,
        description=description,
        cover_tmp=cover_tmp,
        songs_tmp=songs_tmp,
    )
    return metadata.model_dump()


@app.post("/staff/publications/{publication_id}/status")
def staff_approval(
    publication_id: str,
    payload: ApprovalAction,
    user: dict = Depends(require_roles("staff")),
) -> dict:
    _ = user
    metadata = update_publication_status(publication_id, payload.status)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Publication not found")
    return metadata.model_dump()


@app.post("/playlists", response_model=Playlist)
def create_playlist(payload: PlaylistCreate, user: dict = Depends(require_user)) -> Playlist:
    db = read_db()
    playlist = {
        "id": str(uuid4()),
        "owner_id": user["id"],
        "name": payload.name,
        "description": payload.description,
        "song_ids": [],
        "created_at": datetime.utcnow(),
    }
    db["playlists"].append(playlist)
    write_db(db)
    return Playlist.model_validate(playlist)


@app.get("/playlists", response_model=list[Playlist])
def list_user_playlists(user: dict = Depends(require_user)) -> list[Playlist]:
    db = read_db()
    rows = [Playlist.model_validate(item) for item in db["playlists"] if item["owner_id"] == user["id"]]
    rows.sort(key=lambda item: item.created_at, reverse=True)
    return rows


@app.post("/playlists/{playlist_id}/songs", response_model=Playlist)
def add_song_to_playlist(playlist_id: str, payload: PlaylistAddSong, user: dict = Depends(require_user)) -> Playlist:
    db = read_db()
    playlist = next((item for item in db["playlists"] if item["id"] == playlist_id and item["owner_id"] == user["id"]), None)
    if playlist is None:
        raise HTTPException(status_code=404, detail="Playlist not found")

    if payload.publication_id not in playlist["song_ids"]:
        playlist["song_ids"].append(payload.publication_id)
        write_db(db)
    return Playlist.model_validate(playlist)
