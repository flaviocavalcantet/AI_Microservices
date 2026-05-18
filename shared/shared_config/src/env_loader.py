# Environment file loader utilities

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)


class DotEnvLoader:
    """Load environment variables from .env files
    
    Supports:
    - .env (local, takes priority)
    - .env.{environment} (environment-specific)
    - Environment variables (highest priority)
    
    Cross-platform compatible (Windows and Unix).
    """
    
    @staticmethod
    def load(
        env_name: Optional[str] = None,
        search_paths: Optional[list] = None,
        verbose: bool = False
    ) -> None:
        """Load environment variables from .env files
        
        Args:
            env_name: Environment name (development, staging, production).
                      If None, uses FLASK_ENV or defaults to development.
            search_paths: Directories to search for .env files.
                          Defaults to [project_root, current_dir]
            verbose: If True, log what files are loaded
        
        Example:
            >>> from shared.shared_config.src.env_loader import DotEnvLoader
            >>> DotEnvLoader.load()  # Loads .env and .env.development
            >>> DotEnvLoader.load("production")  # Loads .env.production
        """
        
        if env_name is None:
            env_name = os.getenv("FLASK_ENV", "development")
        
        # Search paths
        if search_paths is None:
            search_paths = [
                Path.cwd(),  # Current directory
                Path.cwd().parent,  # Parent directory
                Path(__file__).parent.parent.parent.parent,  # Project root
            ]
        
        # Files to try loading (in order of priority)
        env_files = [
            f".env",  # Local .env (highest priority)
            f".env.{env_name}",  # Environment-specific
        ]
        
        loaded_files = []
        
        for env_file in env_files:
            for search_path in search_paths:
                env_path = search_path / env_file
                
                if env_path.exists():
                    try:
                        load_dotenv(str(env_path))
                        loaded_files.append(str(env_path))
                        if verbose:
                            logger.info(f"Loaded environment from: {env_path}")
                        break  # Found this file, move to next
                    except Exception as e:
                        if verbose:
                            logger.warning(f"Failed to load {env_path}: {e}")
        
        if verbose:
            if loaded_files:
                logger.info(f"Environment loaded from {len(loaded_files)} file(s)")
            else:
                logger.debug("No .env files found, using system environment variables")


def load_env(
    env_name: Optional[str] = None,
    verbose: bool = False
) -> None:
    """Convenience function to load environment
    
    Args:
        env_name: Environment name (development, staging, production)
        verbose: If True, log loading information
    
    Example:
        >>> from shared.shared_config.src.env_loader import load_env
        >>> load_env()
    """
    DotEnvLoader.load(env_name=env_name, verbose=verbose)
