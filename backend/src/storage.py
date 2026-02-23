from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from PIL import Image

from .models import PublicationMetadata

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
MUSIC_DIR = DATA_DIR / "music"
DB_FILE = DATA_DIR / "db.json"


def ensure_data_dirs() -> None:
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not DB_FILE.exists():
        DB_FILE.write_text(json.dumps({"users": [], "playlists": []}, indent=2), encoding="utf-8")


def read_db() -> dict[str, Any]:
    ensure_data_dirs()
    return json.loads(DB_FILE.read_text(encoding="utf-8"))


def write_db(payload: dict[str, Any]) -> None:
    ensure_data_dirs()
    DB_FILE.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def create_publication_root(artist_id: str) -> Path:
    artist_dir = MUSIC_DIR / artist_id
    artist_dir.mkdir(parents=True, exist_ok=True)
    publication_id = str(uuid4())
    publication_dir = artist_dir / publication_id
    (publication_dir / "songs").mkdir(parents=True, exist_ok=True)
    return publication_dir


def normalize_cover(cover_path: Path) -> str:
    img = Image.open(cover_path)
    target = cover_path.with_suffix(".png")
    img.convert("RGB").save(target, format="PNG")
    if target != cover_path:
        cover_path.unlink(missing_ok=True)
    return target.name


def save_publication(
    artist_id: str,
    title: str,
    genre: str,
    description: str,
    cover_tmp: Path,
    songs_tmp: list[Path],
) -> PublicationMetadata:
    publication_dir = create_publication_root(artist_id)
    publication_id = publication_dir.name

    cover_dest = publication_dir / cover_tmp.name
    shutil.move(str(cover_tmp), str(cover_dest))
    cover_file = normalize_cover(cover_dest)

    saved_songs: list[str] = []
    songs_dir = publication_dir / "songs"
    for song_tmp in songs_tmp:
        song_dest = songs_dir / song_tmp.name
        shutil.move(str(song_tmp), str(song_dest))
        saved_songs.append(song_dest.name)

    metadata = PublicationMetadata(
        publication_id=publication_id,
        artist_id=artist_id,
        title=title,
        genre=genre,
        description=description,
        song_files=saved_songs,
        cover_file=cover_file,
        uploaded_at=datetime.utcnow(),
        status="pending",
    )
    (publication_dir / "metadata.json").write_text(metadata.model_dump_json(indent=2), encoding="utf-8")
    return metadata


def list_publications(include_pending: bool = True) -> list[PublicationMetadata]:
    ensure_data_dirs()
    publications: list[PublicationMetadata] = []
    if not MUSIC_DIR.exists():
        return publications

    for artist_dir in MUSIC_DIR.iterdir():
        if not artist_dir.is_dir():
            continue
        for publication_dir in artist_dir.iterdir():
            metadata_path = publication_dir / "metadata.json"
            if not metadata_path.exists():
                continue
            metadata = PublicationMetadata.model_validate_json(metadata_path.read_text(encoding="utf-8"))
            if include_pending or metadata.status == "approved":
                publications.append(metadata)
    publications.sort(key=lambda item: item.uploaded_at, reverse=True)
    return publications


def update_publication_status(publication_id: str, status: str) -> PublicationMetadata | None:
    ensure_data_dirs()
    for artist_dir in MUSIC_DIR.iterdir():
        if not artist_dir.is_dir():
            continue
        publication_dir = artist_dir / publication_id
        metadata_path = publication_dir / "metadata.json"
        if metadata_path.exists():
            metadata = PublicationMetadata.model_validate_json(metadata_path.read_text(encoding="utf-8"))
            metadata.status = status
            metadata_path.write_text(metadata.model_dump_json(indent=2), encoding="utf-8")
            return metadata
    return None
