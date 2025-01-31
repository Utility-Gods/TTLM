from git import Repo 
from pathlib import Path
from typing import List, Dict,  Union
from datetime import datetime
import tempfile
import shutil
import logging
import os
import re
import logging



from .models import RepositoryInfo
from .exceptions import RepositoryValidationError


class GitManager:
    def __init__(self, workspace_dir: Union[str, Path] = None):
        """
        Initialize GitManager with a workspace directory for storing repositories.
        
        Args:
            workspace_dir: Directory to store cloned repositories. If None, uses system temp directory.
        """
        self.workspace_dir = Path(workspace_dir) if workspace_dir else Path(tempfile.gettempdir()) / "ttlm_workspace"
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.repo = None
        self.repo_info = None
        
        # Configure logging
        self.logger = logging.getLogger("GitManager")
        self.logger.setLevel(logging.INFO)

    def is_git_url(self, repo_source: str) -> bool:
        """
        Check if the provided source is a Git URL.
        
        Args:
            repo_source: Repository source (URL or path)
            
        Returns:
            bool: True if source is a Git URL
        """
        git_url_patterns = [
            r'^git@[a-zA-Z0-9.-]+:[a-zA-Z0-9/._-]+\.git$',  # SSH URL
            r'^https?://[a-zA-Z0-9.-]+/[a-zA-Z0-9/._-]+\.git$',  # HTTPS URL
            r'^file://[a-zA-Z0-9/._-]+\.git$'  # Local Git URL
        ]
        
        return any(re.match(pattern, repo_source) for pattern in git_url_patterns)

    def get_repo_name(self, repo_source: str) -> str:
        """
        Extract repository name from source.
        
        Args:
            repo_source: Repository source (URL or path)
            
        Returns:
            str: Repository name
        """
        if self.is_git_url(repo_source):
            # Extract name from URL (e.g., 'repo.git' -> 'repo')
            return repo_source.split('/')[-1].replace('.git', '')
        else:
            # Use the last directory name from the path
            return Path(repo_source).name

    async def initialize_repository(self, repo_source: str) -> RepositoryInfo:
        """
        Initialize a repository from either a local path or remote URL.
        
        Args:
            repo_source: Local path or Git URL of the repository
            
        Returns:
            RepositoryInfo: Information about the initialized repository
            
        Raises:
            RepositoryValidationError: If repository initialization fails
        """
        try:
            repo_name = self.get_repo_name(repo_source)
            is_local = not self.is_git_url(repo_source)
            
            if is_local:
                # For local repositories, use the path directly
                repo_path = Path(repo_source)
                if not repo_path.exists():
                    raise RepositoryValidationError(f"Local path does not exist: {repo_source}")
                self.repo = Repo(repo_path)
            else:
                # For remote repositories, clone into workspace
                repo_path = self.workspace_dir / repo_name
                if repo_path.exists():
                    # If repository already exists, pull latest changes
                    self.repo = Repo(repo_path)
                    self.logger.info(f"Pulling latest changes for {repo_name}")
                    self.repo.remotes.origin.pull()
                else:
                    # Clone new repository
                    self.logger.info(f"Cloning repository: {repo_source}")
                    self.repo = Repo.clone_from(repo_source, repo_path)

            # Validate repository
            if not self.repo.bare:
                # Get repository information
                default_branch = self.repo.active_branch.name
                last_commit = self.repo.head.commit.hexsha
                commit_count = sum(1 for _ in self.repo.iter_commits())
                branch_count = len([b for b in self.repo.branches])

                self.repo_info = RepositoryInfo(
                    name=repo_name,
                    path=repo_path,
                    is_local=is_local,
                    default_branch=default_branch,
                    last_commit=last_commit,
                    commit_count=commit_count,
                    branch_count=branch_count
                )
                
                self.logger.info(f"Successfully initialized repository: {repo_name}")
                return self.repo_info
            else:
                raise RepositoryValidationError("Invalid repository: bare repository")

        except Exception as e:
            error_msg = f"Failed to initialize repository: {str(e)}"
            self.logger.error(error_msg)
            raise RepositoryValidationError(error_msg)

    async def get_file_tree(self) -> List[Dict]:
        """
        Get the repository file tree structure.
        
        Returns:
            List[Dict]: List of files with their paths and metadata
        """
        if not self.repo:
            raise RepositoryValidationError("Repository not initialized")

        files = []
        for root, _, filenames in os.walk(self.repo_info.path):
            rel_root = Path(root).relative_to(self.repo_info.path)
            for filename in filenames:
                # Skip .git directory
                if '.git' in str(rel_root):
                    continue
                    
                file_path = rel_root / filename
                files.append({
                    'path': str(file_path),
                    'size': os.path.getsize(self.repo_info.path / file_path),
                    'last_modified': datetime.fromtimestamp(
                        os.path.getmtime(self.repo_info.path / file_path)
                    ).isoformat()
                })
        
        return sorted(files, key=lambda x: x['path'])

    async def cleanup(self):
        """Clean up temporary files for remote repositories"""
        if self.repo and not self.repo_info.is_local:
            try:
                self.repo.close()
                shutil.rmtree(self.repo_info.path)
                self.logger.info(f"Cleaned up repository: {self.repo_info.name}")
            except Exception as e:
                self.logger.error(f"Error cleaning up repository: {str(e)}")
