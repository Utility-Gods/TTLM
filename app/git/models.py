from dataclasses import dataclass
from pathlib import Path

@dataclass
class RepositoryInfo:
    name: str
    path: Path
    is_local: bool
    default_branch: str
    last_commit: str
    commit_count: int
    branch_count: int
