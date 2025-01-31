import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Union

from git import Repo

from .exceptions import RepositoryValidationError
from .models import RepositoryInfo

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


class GitManager:
    def __init__(self, workspace_dir: Union[str, Path] = None):
        """
        Initialize GitManager with a persistent workspace directory for repositories.


        Args:
            workspace_dir: Directory to store repositories. Creates 'repositories' subdirectory.
        """
        base_dir = Path(workspace_dir) if workspace_dir else Path.home() / ".ttlm"
        self.repos_dir = base_dir / "repositories"
        self.repos_dir.mkdir(parents=True, exist_ok=True)

        self.repo = None
        self.repo_info = None

        self.logger = logging.getLogger("GitManager")
        self.logger.setLevel(logging.INFO)
        self.logger.info(
            f"GitManager initialized with repos directory: {self.repos_dir}"
        )

    def is_git_url(self, repo_source: str) -> bool:
        git_url_patterns = [
            r"^git@[a-zA-Z0-9.-]+:[a-zA-Z0-9/._-]+\.git$",  # SSH URL
            r"^https?://[a-zA-Z0-9.-]+/[a-zA-Z0-9/._-]+\.git$",  # HTTPS URL
            r"^file://[a-zA-Z0-9/._-]+\.git$",  # Local Git URL
        ]
        is_url = any(re.match(pattern, repo_source) for pattern in git_url_patterns)
        self.logger.debug(f"URL check for {repo_source}: {is_url}")
        return is_url

    def get_repo_name(self, repo_source: str) -> str:
        """Extract repository name from source."""
        if self.is_git_url(repo_source):
            name = repo_source.split("/")[-1].replace(".git", "")
        else:
            name = Path(repo_source).name
        self.logger.debug(f"Extracted repo name: {name} from source: {repo_source}")
        return name

    async def initialize_repository(self, repo_source: str) -> RepositoryInfo:
        """
        Initialize or update a repository. For remote repos, maintains a persistent clone.
        For local repos, uses the original location.
        """
        try:
            self.logger.info(f"Starting repository initialization from: {repo_source}")
            repo_name = self.get_repo_name(repo_source)
            is_local = not self.is_git_url(repo_source)
            self.logger.info(f"Resolved name: {repo_name}, is_local: {is_local}")           
            if is_local:
                repo_path = Path(repo_source).resolve()
                if not repo_path.exists():
                    raise RepositoryValidationError(f"Local path does not exist: {repo_source}")
                    
                # Create symlink in workspace
                workspace_path = self.repos_dir / repo_path.name
                if not workspace_path.exists():
                    self.logger.info(f"Creating symlink at: {workspace_path}")
                    os.symlink(repo_path, workspace_path)
                
                self.repo = Repo(repo_path)
            else:
                self.logger.info(f"Cloning new repository to: {repo_path}")
                try:
                    self.repo = Repo.clone_from(repo_source, repo_path)
                    self.logger.info(f"Clone completed successfully")
                except Exception as e:
                    self.logger.error(f"Clone failed: {str(e)}")
                    raise

            if self.repo.bare:
                raise RepositoryValidationError("Invalid repository: bare repository")

            # Get repository information using Git internals
            default_branch = self.repo.active_branch.name
            head_commit = self.repo.head.commit

            self.repo_info = RepositoryInfo(
                name=repo_name,
                path=repo_path,
                is_local=is_local,
                default_branch=default_branch,
                last_commit=head_commit.hexsha,
                commit_count=sum(1 for _ in self.repo.iter_commits()),
                branch_count=len([b for b in self.repo.branches]),
            )

            self.logger.info(f"Repository initialized successfully: {repo_name}")
            self.logger.debug(f"Repository details: {self.repo_info}")
            return self.repo_info

        except Exception as e:
            error_msg = f"Failed to initialize repository: {str(e)}"
            self.logger.error(error_msg)
            raise RepositoryValidationError(error_msg)

    async def get_file_tree(self, commit_hash: Optional[str] = None) -> List[Dict]:
        """
        Get the repository file tree structure at a specific commit.
        If no commit_hash is provided, uses HEAD.
        """
        if not self.repo:
            raise RepositoryValidationError("Repository not initialized")

        self.logger.info(f"Getting file tree for commit: {commit_hash or 'HEAD'}")
        commit = self.repo.commit(commit_hash) if commit_hash else self.repo.head.commit

        files = []
        for item in commit.tree.traverse():
            # Skip if it's a tree (directory)
            if item.type != "blob":
                continue

            files.append(
                {
                    "path": item.path,
                    "size": item.size,
                    "mode": item.mode,
                    "hash": item.hexsha,
                }
            )

        self.logger.info(f"Found {len(files)} files in tree")
        return sorted(files, key=lambda x: x["path"])

    async def get_file_content(
        self, file_path: str, commit_hash: Optional[str] = None
    ) -> str:
        """Get file content at specific commit."""
        if not self.repo:
            raise RepositoryValidationError("Repository not initialized")

        commit = commit_hash or "HEAD"
        self.logger.info(f"Fetching content for {file_path} at {commit}")
        return self.repo.git.show(f"{commit}:{file_path}")

    async def get_file_history(self, file_path: str) -> List[Dict]:
        """Get commit history for specific file."""
        if not self.repo:
            raise RepositoryValidationError("Repository not initialized")

        self.logger.info(f"Getting commit history for: {file_path}")
        history = [
            {
                "hash": commit.hexsha,
                "author": commit.author.name,
                "date": commit.authored_datetime.isoformat(),
                "message": commit.message.strip(),
            }
            for commit in self.repo.iter_commits(paths=file_path)
        ]

        self.logger.info(f"Found {len(history)} commits for {file_path}")
        return history

    async def switch_branch(self, branch_name: str):
        """Switch to a different branch."""
        if not self.repo:
            raise RepositoryValidationError("Repository not initialized")

        self.logger.info(f"Switching to branch: {branch_name}")
        self.repo.git.checkout(branch_name)
        # Update repo_info with new HEAD
        self.repo_info.last_commit = self.repo.head.commit.hexsha
        self.logger.info(f"Successfully switched to {branch_name}")
