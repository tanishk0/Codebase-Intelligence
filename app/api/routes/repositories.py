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

