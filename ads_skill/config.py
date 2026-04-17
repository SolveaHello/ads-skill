import os
import json
from pathlib import Path

# Load .env from project root if present (no hard dependency on python-dotenv)
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    with open(_env_file) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip())


def _require(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise RuntimeError(
            f"Missing required config: {key}\n"
            f"Add it to .env in the project root or set the environment variable.\n"
            f"See .env.example for the full template."
        )
    return val


CONFIG_DIR = Path.home() / ".ads-skill"
TOKEN_FILE = CONFIG_DIR / "tokens.json"

CLIENT_ID = _require("ADS_CLIENT_ID")
CLIENT_SECRET = _require("ADS_CLIENT_SECRET")
DEVELOPER_TOKEN = _require("ADS_DEVELOPER_TOKEN")
REDIRECT_URI = os.environ.get("ADS_REDIRECT_URI", "http://localhost:8086/callback")
SCOPES = ["https://www.googleapis.com/auth/adwords"]


def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_tokens() -> dict | None:
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE) as f:
            return json.load(f)
    return None


def save_tokens(tokens: dict) -> None:
    ensure_config_dir()
    with open(TOKEN_FILE, "w") as f:
        json.dump(tokens, f, indent=2)
    os.chmod(TOKEN_FILE, 0o600)


def clear_tokens() -> list[str]:
    removed = []
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
        removed.append(str(TOKEN_FILE))
    return removed
