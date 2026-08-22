import os
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from dotenv import load_dotenv


load_dotenv()


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class Settings:
    environment: Environment
    log_level: LogLevel

    supabase_url: str
    supabase_secret_key: str = field(repr=False)

    telegram_bot_token: str | None = field(repr=False)
    telegram_allowed_user_ids: frozenset[int]
    brapi_token: str | None = None
    gemini_api_key: str | None = field(default=None, repr=False)
    gemini_model: str | None = None
    twelve_data_api_key: str | None = field(default=None, repr=False)
    market_quotes_enabled: bool = False
    market_quotes_interval_seconds: int = 300
    market_history_enabled: bool = False
    market_history_interval_seconds: int = 86400
    market_history_lookback_days: int = 30
    market_history_candle_interval: str = "1d"

    automated_pipeline_enabled: bool = False
    automation_enabled: bool = False
    shadow_mode_enabled: bool = False
    production_ready: bool = False
    shadow_policy_version: str | None = None
    shadow_interval_seconds: int = 1800
    shadow_candle_interval: str = "1d"
    shadow_lookback_days: int = 30
    shadow_analysis_period: int = 14
    shadow_forward_horizon_days: int = 5
    shadow_round_trip_cost_bps: Decimal = Decimal("20")
    automated_pipeline_interval_seconds: int = 1800
    automated_pipeline_providers: tuple[str, ...] = ("brapi", "twelve_data")
    automated_pipeline_candle_interval: str = "1d"
    automated_pipeline_lookback_days: int = 30
    automated_pipeline_analysis_period: int = 14
    automated_pipeline_reference_max_age_seconds: int = 345600
    automated_pipeline_prompt_version: str = "gemini-v1"

    opportunity_policy_version: str | None = None
    opportunity_minimum_categories: int = 2
    opportunity_max_ai_weight: Decimal = Decimal("20")
    opportunity_rules_json: str | None = field(default=None, repr=False)

    alert_cooldown_seconds: int = 86400


def get_required_env(name: str) -> str:
    value = os.getenv(name)

    if value is None or not value.strip():
        raise ValueError(f"Variável obrigatória ausente: {name}")

    return value.strip()


def get_optional_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    return value.strip()


def parse_telegram_allowed_user_ids(raw: str | None) -> frozenset[int]:
    if raw is None or not raw.strip():
        return frozenset()

    user_ids: set[int] = set()

    for item in raw.split(","):
        value = item.strip()

        try:
            user_id = int(value)
        except ValueError as exc:
            raise ValueError(
                "TELEGRAM_ALLOWED_USER_IDS contém valor inválido: " f"{value}"
            ) from exc

        if user_id <= 0:
            raise ValueError(
                "TELEGRAM_ALLOWED_USER_IDS deve conter apenas IDs positivos."
            )

        user_ids.add(user_id)

    return frozenset(user_ids)


def _optional_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    if value.strip().lower() in {"1", "true", "yes"}:
        return True
    if value.strip().lower() in {"0", "false", "no"}:
        return False
    raise ValueError(f"{name} deve ser booleano")


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} deve ser inteiro") from exc
    if value <= 0:
        raise ValueError(f"{name} deve ser positivo")
    return value


def _non_negative_decimal(name: str, default: Decimal) -> Decimal:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = Decimal(raw.strip())
    except InvalidOperation as exc:
        raise ValueError(f"{name} deve ser decimal") from exc
    if not value.is_finite() or value < 0:
        raise ValueError(f"{name} deve ser decimal finito não negativo")
    return value


def _csv_values(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    values = tuple(item.strip() for item in raw.split(",") if item.strip())
    if not values:
        raise ValueError(f"{name} deve conter ao menos um valor")
    if len(set(values)) != len(values):
        raise ValueError(f"{name} não pode conter valores duplicados")
    return values


def get_settings() -> Settings:
    environment_raw = os.getenv("APP_ENV", "development").lower()
    log_level_raw = os.getenv("LOG_LEVEL", "INFO").upper()

    try:
        environment = Environment(environment_raw)
    except ValueError as exc:
        raise ValueError(f"APP_ENV inválido: {environment_raw}") from exc

    try:
        log_level = LogLevel(log_level_raw)
    except ValueError as exc:
        raise ValueError(f"LOG_LEVEL inválido: {log_level_raw}") from exc

    supabase_url = get_required_env("SUPABASE_URL")
    supabase_secret_key = get_required_env("SUPABASE_SECRET_KEY")
    # Telegram is required only by the explicitly enabled production-alert
    # pipeline.  Shadow collection must be executable without this credential.
    telegram_bot_token = get_optional_env("TELEGRAM_BOT_TOKEN")
    telegram_allowed_user_ids = parse_telegram_allowed_user_ids(
        os.getenv("TELEGRAM_ALLOWED_USER_IDS", "")
    )

    return Settings(
        environment=environment,
        log_level=log_level,
        supabase_url=supabase_url,
        supabase_secret_key=supabase_secret_key,
        telegram_bot_token=telegram_bot_token,
        telegram_allowed_user_ids=telegram_allowed_user_ids,
        brapi_token=get_optional_env("BRAPI_TOKEN"),
        gemini_api_key=get_optional_env("GEMINI_API_KEY"),
        gemini_model=get_optional_env("GEMINI_MODEL"),
        twelve_data_api_key=get_optional_env("TWELVE_DATA_API_KEY"),
        market_quotes_enabled=_optional_bool("MARKET_QUOTES_ENABLED", False),
        market_quotes_interval_seconds=_positive_int(
            "MARKET_QUOTES_INTERVAL_SECONDS", 300
        ),
        market_history_enabled=_optional_bool("MARKET_HISTORY_ENABLED", False),
        market_history_interval_seconds=_positive_int(
            "MARKET_HISTORY_INTERVAL_SECONDS", 86400
        ),
        market_history_lookback_days=_positive_int(
            "MARKET_HISTORY_LOOKBACK_DAYS", 30
        ),
        market_history_candle_interval=(
            get_optional_env("MARKET_HISTORY_CANDLE_INTERVAL") or "1d"
        ),
        automated_pipeline_enabled=_optional_bool(
            "AUTOMATED_PIPELINE_ENABLED", False
        ),
        automation_enabled=_optional_bool("AUTOMATION_ENABLED", False),
        shadow_mode_enabled=_optional_bool("SHADOW_MODE_ENABLED", False),
        production_ready=_optional_bool("PRODUCTION_READY", False),
        shadow_policy_version=get_optional_env("SHADOW_POLICY_VERSION"),
        shadow_interval_seconds=_positive_int("SHADOW_INTERVAL_SECONDS", 1800),
        shadow_candle_interval=(get_optional_env("SHADOW_CANDLE_INTERVAL") or "1d"),
        shadow_lookback_days=_positive_int("SHADOW_LOOKBACK_DAYS", 30),
        shadow_analysis_period=_positive_int("SHADOW_ANALYSIS_PERIOD", 14),
        shadow_forward_horizon_days=_positive_int("SHADOW_FORWARD_HORIZON_DAYS", 5),
        shadow_round_trip_cost_bps=_non_negative_decimal("SHADOW_ROUND_TRIP_COST_BPS", Decimal("20")),
        automated_pipeline_interval_seconds=_positive_int(
            "AUTOMATED_PIPELINE_INTERVAL_SECONDS", 1800
        ),
        automated_pipeline_providers=_csv_values(
            "AUTOMATED_PIPELINE_PROVIDERS", ("brapi", "twelve_data")
        ),
        automated_pipeline_candle_interval=(
            get_optional_env("AUTOMATED_PIPELINE_CANDLE_INTERVAL") or "1d"
        ),
        automated_pipeline_lookback_days=_positive_int(
            "AUTOMATED_PIPELINE_LOOKBACK_DAYS", 30
        ),
        automated_pipeline_analysis_period=_positive_int(
            "AUTOMATED_PIPELINE_ANALYSIS_PERIOD", 14
        ),
        automated_pipeline_reference_max_age_seconds=_positive_int(
            "AUTOMATED_PIPELINE_REFERENCE_MAX_AGE_SECONDS", 345600
        ),
        automated_pipeline_prompt_version=(
            get_optional_env("AUTOMATED_PIPELINE_PROMPT_VERSION") or "gemini-v1"
        ),
        opportunity_policy_version=get_optional_env("OPPORTUNITY_POLICY_VERSION"),
        opportunity_minimum_categories=_positive_int(
            "OPPORTUNITY_MINIMUM_CATEGORIES", 2
        ),
        opportunity_max_ai_weight=_non_negative_decimal(
            "OPPORTUNITY_MAX_AI_WEIGHT", Decimal("20")
        ),
        opportunity_rules_json=get_optional_env("OPPORTUNITY_RULES_JSON"),
        alert_cooldown_seconds=_positive_int("ALERT_COOLDOWN_SECONDS", 86400),
    )
