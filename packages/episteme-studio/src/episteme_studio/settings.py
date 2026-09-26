"""Central configuration settings for GLP Studio.

Per SPEC §3, StudioSettings is the ONLY module permitted to read os.environ.
All environment variables are scoped under the EPISTEME_STUDIO_ prefix.
"""

from __future__ import annotations

import os
from pathlib import Path
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_dotenv_files() -> None:
    """Find and load candidate .env files from pipeline, root, and example directories."""
    repo_root = Path(__file__).resolve().parents[4]
    candidates = [
        Path.cwd() / "pipeline" / ".env",
        Path.cwd() / ".env",
        Path.cwd() / "examples" / ".env",
        repo_root / "pipeline" / ".env",
        repo_root / ".env",
        repo_root / "examples" / ".env",
    ]
    for parent in Path.cwd().parents:
        candidates.append(parent / "pipeline" / ".env")
        candidates.append(parent / ".env")
        candidates.append(parent / "examples" / ".env")

    for cand in candidates:
        if cand.is_file():
            try:
                from dotenv import load_dotenv

                load_dotenv(dotenv_path=cand, override=False)
            except Exception:
                pass


_load_dotenv_files()


def load_all_dotenv() -> None:
    """Reload or load all candidate .env files."""
    _load_dotenv_files()


def _resolve_repo_root() -> Path:
    """Find repository root containing .git, AGENTS.md, or pyproject.toml."""
    try:
        cwd = Path.cwd()
        for candidate in [cwd, *cwd.parents]:
            if (candidate / ".git").exists() or (candidate / "AGENTS.md").exists():
                return candidate
    except Exception:
        pass
    return Path.cwd()


def _resolve_default_dir(name: str) -> Path:
    """Resolve a default pipeline directory by inspecting repo root, cwd and parent directories.

    Parameters
    ----------
    name : str
        Directory name to locate, e.g. '.pipeline_runs' or '.pipeline_artifacts'.

    Returns
    -------
    Path
        Resolved directory path if found in repository root, cwd, or an ancestor;
        otherwise fallback relative path `Path(name)`.
    """
    try:
        repo_root = _resolve_repo_root()
        root_target = repo_root / name
        if root_target.is_dir():
            return root_target

        cwd = Path.cwd()
        for candidate in [cwd, *cwd.parents]:
            target = candidate / name
            if target.is_dir():
                return target
    except Exception:
        pass
    return Path(name)


def _resolve_extra_dirs(name: str) -> list[Path]:
    """Find secondary directories of the given name across packages to ensure no runs are missed."""
    extra: list[Path] = []
    try:
        repo_root = _resolve_repo_root()
        primary = _resolve_default_dir(name).resolve()
        candidates = [
            repo_root / name,
            repo_root / "packages" / "episteme-studio" / name,
            repo_root / "packages" / "episteme-pipeline" / "examples" / name,
            repo_root / "packages" / "episteme-pipeline" / name,
        ]
        seen = {primary}
        for c in candidates:
            if c.is_dir():
                resolved = c.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    extra.append(c)
    except Exception:
        pass
    return extra


def _resolve_default_runs_dir() -> Path:
    """Resolve default path to pipeline runs manifest directory.

    Returns
    -------
    Path
        Found directory in current working directory or parent hierarchy;
        falls back to Path('.pipeline_runs').
    """
    return _resolve_default_dir(".pipeline_runs")


def _resolve_default_artifacts_dir() -> Path:
    """Resolve default path to pipeline artifacts store directory.

    Returns
    -------
    Path
        Found directory in current working directory or parent hierarchy;
        falls back to Path('.pipeline_artifacts').
    """
    return _resolve_default_dir(".pipeline_artifacts")


def _resolve_default_reports_dir() -> Path:
    """Resolve default path to evaluation reports store directory.

    Returns
    -------
    Path
        Found directory in current working directory or parent hierarchy;
        falls back to Path('evaluation/reports').
    """
    return _resolve_default_dir("evaluation/reports")


def _resolve_default_neo4j_url() -> str | None:
    """Resolve default Neo4j connection URI.

    Checks EPISTEME_STUDIO_NEO4J_URL, falling back to NEO4J_URL and NEO4J_URI.

    Returns
    -------
    str or None
        Resolved connection URI, or None if unconfigured.
    """
    return (
        os.environ.get("EPISTEME_STUDIO_NEO4J_URL")
        or os.environ.get("NEO4J_URL")
        or os.environ.get("NEO4J_URI")
    )


def _resolve_default_neo4j_user() -> str | None:
    """Resolve default Neo4j user name.

    Checks EPISTEME_STUDIO_NEO4J_USER, falling back to NEO4J_USERNAME and NEO4J_USER.

    Returns
    -------
    str or None
        Resolved username, or None if unconfigured.
    """
    return (
        os.environ.get("EPISTEME_STUDIO_NEO4J_USER")
        or os.environ.get("NEO4J_USERNAME")
        or os.environ.get("NEO4J_USER")
    )


def _resolve_default_neo4j_password() -> str | None:
    """Resolve default Neo4j password.

    Checks EPISTEME_STUDIO_NEO4J_PASSWORD, falling back to NEO4J_PASSWORD.

    Returns
    -------
    str or None
        Resolved password, or None if unconfigured.
    """
    return os.environ.get("EPISTEME_STUDIO_NEO4J_PASSWORD") or os.environ.get(
        "NEO4J_PASSWORD"
    )


def _resolve_default_neo4j_database() -> str | None:
    """Resolve default Neo4j database name.

    Checks EPISTEME_STUDIO_NEO4J_DATABASE, falling back to NEO4J_DATABASE.

    Returns
    -------
    str or None
        Resolved database name, or None if unconfigured.
    """
    return os.environ.get("EPISTEME_STUDIO_NEO4J_DATABASE") or os.environ.get(
        "NEO4J_DATABASE"
    )


def _resolve_default_langfuse_host() -> str:
    """Resolve default Langfuse host URI.

    Checks EPISTEME_STUDIO_LANGFUSE_HOST, falling back to LANGFUSE_HOST, LANGFUSE_BASE_URL,
    defaulting to 'http://localhost:3000'.

    Returns
    -------
    str
        Resolved host URL, defaulting to 'http://localhost:3000'.
    """
    return (
        os.environ.get("EPISTEME_STUDIO_LANGFUSE_HOST")
        or os.environ.get("LANGFUSE_HOST")
        or os.environ.get("LANGFUSE_BASE_URL")
        or "http://localhost:3000"
    )


class StudioSettings(BaseSettings):
    """Runtime configuration for GLP Studio server and services.

    Parameters
    ----------
    host : str, default '127.0.0.1'
        Host interface to bind the HTTP server to.
    port : int, default 8000
        TCP port for HTTP and WebSocket/SSE traffic.
    token : str or None, optional
        Bearer authentication token. Required if binding to a non-loopback host.
    artifacts_dir : Path, default '.pipeline_artifacts'
        Root path to directory containing artifact envelopes.
    runs_dir : Path, default '.pipeline_runs'
        Root path to directory containing pipeline run manifests.
    node_budget : int, default 500
        Default element cap for graph materialization queries.
    query_timeout_seconds : float, default 30.0
        Timeout in seconds for graph and Cypher queries.
    static_dir : Path or None, optional
        Custom directory override for static assets.
    neo4j_url : str or None, optional
        Bolt URI for Neo4j database connection.
    neo4j_user : str or None, optional
        Neo4j authentication user name.
    neo4j_password : str or None, optional
        Neo4j authentication password.
    neo4j_database : str or None, optional
        Target Neo4j database name.
    langfuse_host : str, default 'https://cloud.langfuse.com'
        Base URL for Langfuse monitoring traces.
    demo_mode : bool, default False
        If True, loads canned demonstration runs and mocks external dependencies.
    """

    model_config = SettingsConfigDict(
        env_prefix="EPISTEME_STUDIO_",
        env_file=".env",
        extra="ignore",
    )

    host: str = "127.0.0.1"
    port: int = 8000
    token: str | None = None
    artifacts_dir: Path = Field(default_factory=_resolve_default_artifacts_dir)
    runs_dir: Path = Field(default_factory=_resolve_default_runs_dir)
    reports_dir: Path = Field(default_factory=_resolve_default_reports_dir)
    extra_runs_dirs: list[Path] = Field(default_factory=list)
    extra_artifacts_dirs: list[Path] = Field(default_factory=list)
    node_budget: int = 500

    @model_validator(mode="after")
    def _populate_extra_dirs(self) -> StudioSettings:
        """Populate secondary directories when using default repo paths."""
        try:
            default_runs = _resolve_default_runs_dir().resolve()
            if "extra_runs_dirs" not in self.model_fields_set:
                if self.runs_dir.resolve() == default_runs or self.runs_dir.name == ".pipeline_runs":
                    self.extra_runs_dirs = _resolve_extra_dirs(".pipeline_runs")
                else:
                    self.extra_runs_dirs = []
        except Exception:
            pass

        try:
            default_artifacts = _resolve_default_artifacts_dir().resolve()
            if "extra_artifacts_dirs" not in self.model_fields_set:
                if self.artifacts_dir.resolve() == default_artifacts or self.artifacts_dir.name == ".pipeline_artifacts":
                    self.extra_artifacts_dirs = _resolve_extra_dirs(".pipeline_artifacts")
                else:
                    self.extra_artifacts_dirs = []
        except Exception:
            pass

        if self.demo_mode:
            try:
                from episteme_studio.fixtures import get_fixture_artifacts_dir, get_fixture_runs_dir
                f_runs = get_fixture_runs_dir()
                if f_runs.is_dir() and f_runs not in self.extra_runs_dirs:
                    self.extra_runs_dirs.append(f_runs)
                f_artifacts = get_fixture_artifacts_dir()
                if f_artifacts.is_dir() and f_artifacts not in self.extra_artifacts_dirs:
                    self.extra_artifacts_dirs.append(f_artifacts)
            except Exception:
                pass

        return self
    query_timeout_seconds: float = 30.0
    static_dir: Path | None = None
    neo4j_url: str | None = Field(default_factory=_resolve_default_neo4j_url)
    neo4j_user: str | None = Field(default_factory=_resolve_default_neo4j_user)
    neo4j_password: str | None = Field(default_factory=_resolve_default_neo4j_password)
    neo4j_database: str | None = Field(default_factory=_resolve_default_neo4j_database)
    langfuse_host: str = Field(default_factory=_resolve_default_langfuse_host)
    demo_mode: bool = False
    dev_mode: str | bool | None = None
    execution_enabled: bool = False

    def is_loopback(self) -> bool:
        """Check if server host is bound strictly to a loopback address.

        Returns
        -------
        bool
            True if host is 127.0.0.1, localhost, or ::1; False otherwise.
        """
        return self.host in {"127.0.0.1", "localhost", "::1"}


def get_default_settings() -> StudioSettings:
    """Instantiate StudioSettings reading from environment variables.

    Returns
    -------
    StudioSettings
        Resolved settings instance.
    """
    return StudioSettings()


def check_env_var_set(name: str) -> bool:
    """Check if an environment variable is set and non-empty.

    Parameters
    ----------
    name : str
        Environment variable name.

    Returns
    -------
    bool
        True if the environment variable exists and contains non-whitespace content.
    """
    return bool(os.environ.get(name, "").strip())


def get_env_var(name: str, default: str | None = None) -> str | None:
    """Read an environment variable safely via settings.

    Parameters
    ----------
    name : str
        Environment variable name.
    default : str or None, optional
        Default value if variable is not set.

    Returns
    -------
    str or None
        Resolved environment variable value.
    """
    return os.environ.get(name, default)


def set_env_var(name: str, value: str) -> None:
    """Set an environment variable safely via settings.

    Parameters
    ----------
    name : str
        Environment variable name.
    value : str
        Value to assign.
    """
    os.environ[name] = value

