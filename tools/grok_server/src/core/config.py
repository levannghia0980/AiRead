import os
import yaml
from pathlib import Path
from typing import Dict, Any

class ConfigManager:
    """
    Manages loading and retrieving application & selector configurations.
    """
    def __init__(self, config_path: str = None, selectors_path: str = None):
        base_dir = Path(__file__).resolve().parent.parent
        if not config_path or config_path == "config/config.yaml":
            self.config_path = base_dir / "config" / "config.yaml"
        else:
            self.config_path = Path(config_path)

        if not selectors_path or selectors_path == "config/selectors.yaml":
            self.selectors_path = base_dir / "config" / "selectors.yaml"
        else:
            self.selectors_path = Path(selectors_path)

        self.config: Dict[str, Any] = {}
        self.selectors: Dict[str, Any] = {}
        self.load_all()

    def load_all(self):
        """Loads both configuration YAML files."""
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f) or {}
        else:
            self.config = self._default_config()

        if self.selectors_path.exists():
            with open(self.selectors_path, "r", encoding="utf-8") as f:
                self.selectors = yaml.safe_load(f) or {}
        else:
            self.selectors = {}

    def get(self, key: str, default: Any = None) -> Any:
        """Fetch nested configuration using dot-notation (e.g., 'browser.headless')."""
        keys = key.split(".")
        val = self.config
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val

    def get_selectors(self, provider: str = "grok") -> Dict[str, list]:
        """Fetch DOM selectors for a given provider."""
        return self.selectors.get(provider, {})

    @staticmethod
    def _default_config() -> Dict[str, Any]:
        return {
            "browser": {
                "headless": False,
                "user_data_dir": "user_data/edge_profile",
                "remote_debug_port": 9222,
                "viewport": {"width": 1280, "height": 900},
                "slow_mo": 50
            },
            "engine": {
                "base_url": "https://grok.com",
                "heartbeat_interval": 30,
                "watchdog_interval": 5,
                "session_check_interval": 30,
                "max_retries": 4,
                "response_timeout": 120,
                "stability_wait_seconds": 3.0
            },
            "database": {
                "path": "data/grok_engine.db"
            },
            "logging": {
                "log_dir": "logs",
                "rotation": "10 MB",
                "retention": "30 days",
                "level": "INFO"
            }
        }
