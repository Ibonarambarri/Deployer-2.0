"""Project configuration model."""

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, Optional


@dataclass
class ProjectConfig:
    """Configuration settings for a project."""
    
    # Logs settings
    realtime_logs: bool = False
    logs_poll_interval: float = 0.5  # seconds
    max_logs_display: int = 200
    
    # Environment settings
    auto_create_venv: bool = False
    auto_install_requirements: bool = False
    
    # Execution settings
    auto_restart_on_failure: bool = False
    restart_delay: int = 5  # seconds
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProjectConfig':
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    def save_to_file(self, file_path: Path) -> None:
        """Save configuration to file."""
        try:
            with open(file_path, 'w') as f:
                json.dump(self.to_dict(), f, indent=2)
        except Exception as e:
            raise RuntimeError(f"Failed to save config: {e}")
    
    @classmethod
    def load_from_file(cls, file_path: Path) -> 'ProjectConfig':
        """Load configuration from file."""
        try:
            if file_path.exists():
                with open(file_path, 'r') as f:
                    data = json.load(f)
                return cls.from_dict(data)
            else:
                # Return default config if file doesn't exist
                return cls()
        except Exception as e:
            # Return default config if loading fails
            return cls()
    
    def get_config_file_path(self, project_path: Path) -> Path:
        """Get the configuration file path for a project."""
        return project_path / '.deployer_config.json'