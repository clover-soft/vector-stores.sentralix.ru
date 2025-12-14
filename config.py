import os


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


class Config:
    def __init__(self) -> None:
        self.allow_hosts: list[str] = _parse_csv(os.getenv("ALLOW_HOSTS"))

        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")
        self.log_format: str = os.getenv(
            "LOG_FORMAT",
            "[%(asctime)s][%(name)s][%(levelname)s][%(request_id)s] %(message)s",
        )
        self.log_file: str | None = os.getenv("LOG_FILE")
        self.log_to_console: bool = _parse_bool(os.getenv("LOG_TO_CONSOLE"), default=True)

        self.running_in_container: bool = _parse_bool(
            os.getenv("RUNNING_IN_CONTAINER"),
            default=False,
        )

        self.database_uri: str | None = os.getenv("DATABASE_URI")

        self.files_root: str = os.getenv("FILES_ROOT", "/files")

        self.yc_folder_id: str | None = os.getenv("YC_FOLDER_ID")
        self.yc_sa_key_json_b64: str | None = os.getenv("YC_SA_KEY_JSON_B64")


_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config
