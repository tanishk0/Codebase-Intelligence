from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db.session import get_db
from app.models.repository import Repository
from app.schemas.repository import RepositoryCreate, RepositoryResponse

from app.services.ingestion.ingest_repository import (
    ingest_repository,
    IngestionError,
)
from app.services.ingestion.file_persistence import save_file_records
from app.models.repository_file import RepositoryFile

router = APIRouter(prefix="/repositories", tags=["Repositories"])

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=RepositoryResponse)
def create_repo(
    payload: RepositoryCreate,
    db: Session = Depends(get_db),
):
    respository = Repository(
        name=payload.name,
        git_url=(payload.git_url),
        default_branch=payload.default_branch
    )

    db.add(respository)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Repository already registered",
        )
    db.refresh(respository)

    return respository


@router.get("/", response_model=list[RepositoryResponse])
def list_repositories(
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return (
        db.query(Repository)
        .order_by(Repository.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

@router.get("/{repository_id}", response_model=RepositoryResponse)
def get_repository(
    repository_id: int,
    db: Session = Depends(get_db),
):
    repository = db.get(Repository, repository_id)

    if repository is None:
        raise HTTPException(
            status_code=404,
            detail="Repository not found",
        )

    return repository

@router.post("/{repository_id}/ingest")
def start_ingestion(
    repository_id: int,
    db: Session = Depends(get_db),
):
    repository = db.get(Repository, repository_id)

    if repository is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    repository.status = "processing"
    db.commit()

    try:
        records = ingest_repository(
            repository.git_url,
            repository.default_branch,
        )
        saved_count = save_file_records(
            db=db,
            repository_id=repository.id,
            records=records,
        )
        repository.status = "completed"
        db.commit()

        return {
            "status": repository.status,
            "files_discovered": len(records),
            "files_saved": saved_count,
        }

    except IngestionError:
        repository.status = "failed"
        db.commit()
        raise HTTPException(
            status_code=422,
            detail="Repository ingestion failed",
        )
    except Exception:
        db.rollback()
        repository = db.get(Repository, repository_id)

        if repository is not None:
            repository.status = "failed"
            db.commit()

        raise


@router.get("/{repository_id}/files")
def list_repository_files(
    repository_id: int,
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    repository = db.get(Repository, repository_id)

    if repository is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    files = (
        db.query(RepositoryFile)
        .filter(RepositoryFile.repository_id == repository_id)
        .order_by(RepositoryFile.file_path)
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        {
            "id": file.id,
            "file_path": file.file_path,
            "extension": file.extension,
            "size_bytes": file.size_bytes,
        }
        for file in files
    ]