from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class CredentialDefinition:
    key: str
    label: str
    cost: str
    readiness: str
    recommended: bool


CREDENTIAL_DEFINITIONS = (
    CredentialDefinition(
        key="GITHUB_TOKEN",
        label="GitHub Token",
        cost="free",
        readiness="active",
        recommended=True,
    ),
    CredentialDefinition(
        key="OPENALEX_API_KEY",
        label="OpenAlex API Key",
        cost="free",
        readiness="planned",
        recommended=True,
    ),
    CredentialDefinition(
        key="X_BEARER_TOKEN",
        label="X Bearer Token",
        cost="paid",
        readiness="active",
        recommended=False,
    ),
)

ALLOWED_CREDENTIAL_KEYS = frozenset(definition.key for definition in CREDENTIAL_DEFINITIONS)
MAX_CREDENTIAL_LENGTH = 4096


class CredentialValidationError(ValueError):
    pass


class ApiCredentialStore:
    """Persist a small allowlist of API credentials without ever returning values."""

    def __init__(self, path: Path | str = ".env"):
        self.path = Path(path)

    def status(self) -> dict[str, dict[str, Any]]:
        file_values = self._read_values()
        result: dict[str, dict[str, Any]] = {}
        for definition in CREDENTIAL_DEFINITIONS:
            file_configured = bool(file_values.get(definition.key))
            environment_configured = bool(os.environ.get(definition.key))
            source = "local_file" if file_configured else "environment" if environment_configured else "none"
            result[definition.key] = {
                **asdict(definition),
                "configured": file_configured or environment_configured,
                "source": source,
            }
        return result

    def update(self, values: object, clear: object = ()) -> dict[str, dict[str, Any]]:
        normalized_values = self._validate_values(values)
        normalized_clear = self._validate_clear(clear)
        overlap = sorted(set(normalized_values) & set(normalized_clear))
        if overlap:
            raise CredentialValidationError(f"credential cannot be saved and cleared together: {', '.join(overlap)}")

        old_file_values = self._read_values()
        lines = self.path.read_text(encoding="utf-8").splitlines() if self.path.exists() else self._header_lines()
        updated_lines = self._rewrite_lines(lines, normalized_values, set(normalized_clear))
        self._atomic_write(updated_lines)

        for key, value in normalized_values.items():
            os.environ[key] = value
        for key in normalized_clear:
            old_value = old_file_values.get(key)
            if old_value and os.environ.get(key) == old_value:
                os.environ.pop(key, None)
        return self.status()

    def _read_values(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        values: dict[str, str] = {}
        for line in self.path.read_text(encoding="utf-8").splitlines():
            parsed = _parse_env_assignment(line)
            if parsed is None:
                continue
            key, value = parsed
            if key in ALLOWED_CREDENTIAL_KEYS:
                values[key] = value
        return values

    @staticmethod
    def _validate_values(values: object) -> dict[str, str]:
        if not isinstance(values, dict):
            raise CredentialValidationError("values must be an object")
        normalized: dict[str, str] = {}
        for raw_key, raw_value in values.items():
            key = str(raw_key)
            if key not in ALLOWED_CREDENTIAL_KEYS:
                raise CredentialValidationError(f"unsupported credential: {key}")
            if not isinstance(raw_value, str):
                raise CredentialValidationError(f"credential must be text: {key}")
            if not raw_value or raw_value != raw_value.strip():
                raise CredentialValidationError(f"credential cannot be empty or padded: {key}")
            if len(raw_value) > MAX_CREDENTIAL_LENGTH:
                raise CredentialValidationError(f"credential is too long: {key}")
            if any(character in raw_value for character in ("\n", "\r", "\0")):
                raise CredentialValidationError(f"credential cannot contain control characters: {key}")
            normalized[key] = raw_value
        return normalized

    @staticmethod
    def _validate_clear(clear: object) -> tuple[str, ...]:
        if not isinstance(clear, (list, tuple, set)):
            raise CredentialValidationError("clear must be a list")
        normalized = tuple(str(key) for key in clear)
        unknown = sorted(set(normalized) - ALLOWED_CREDENTIAL_KEYS)
        if unknown:
            raise CredentialValidationError(f"unsupported credential: {', '.join(unknown)}")
        return normalized

    @staticmethod
    def _rewrite_lines(lines: list[str], values: dict[str, str], clear: set[str]) -> list[str]:
        pending = dict(values)
        seen: set[str] = set()
        output: list[str] = []
        for line in lines:
            parsed = _parse_env_assignment(line)
            if parsed is None:
                output.append(line)
                continue
            key, _ = parsed
            if key not in ALLOWED_CREDENTIAL_KEYS:
                output.append(line)
                continue
            if key in clear:
                continue
            if key in pending:
                if key not in seen:
                    output.append(f"{key}={pending.pop(key)}")
                    seen.add(key)
                continue
            output.append(line)

        if pending and output and output[-1] != "":
            output.append("")
        for key in (definition.key for definition in CREDENTIAL_DEFINITIONS):
            if key in pending:
                output.append(f"{key}={pending[key]}")
        return output

    def _atomic_write(self, lines: Iterable[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_name(f".{self.path.name}.tmp-{os.getpid()}")
        payload = "\n".join(lines).rstrip() + "\n"
        descriptor = os.open(temporary_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(payload)
            os.replace(temporary_path, self.path)
            os.chmod(self.path, 0o600)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    @staticmethod
    def _header_lines() -> list[str]:
        return [
            "# Local API credentials for info_radar.",
            "# Managed at http://127.0.0.1:8787/settings; never commit this file.",
        ]


def _parse_env_assignment(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key, value = stripped.split("=", 1)
    key = key.strip()
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value
