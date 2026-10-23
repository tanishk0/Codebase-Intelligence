from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from sqlalchemy import delete
from app.models.repository_file import RepositoryFile


def save_file_records(
    db: Session,
    repository_id: int,
    records: list[dict],
) -> int:
    if not records:
        return 0

    rows = [
        {
            "repository_id": repository_id,
            "file_path": record["file_path"],
            "content": record["content"],
            "extension": record["extension"],
            "size_bytes": record["size_bytes"],
        }
        for record in records
    ]

    statement = insert(RepositoryFile).values(rows)

    statement = statement.on_conflict_do_update(
        constraint="uq_repo_file_path",
        set_={
            "content": statement.excluded.content,
            "extension": statement.excluded.extension,
            "size_bytes": statement.excluded.size_bytes,
            "indexed_at": statement.excluded.indexed_at,
        },
    )

    db.execute(statement)
    current_paths = [record["file_path"] for record in records]

    stale_files = delete(RepositoryFile).where(
        RepositoryFile.repository_id == repository_id,
        RepositoryFile.file_path.notin_(current_paths),
    )

    db.execute(stale_files)
    db.commit()

    return len(records)