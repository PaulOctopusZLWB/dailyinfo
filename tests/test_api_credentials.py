import json
import os
import stat
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from info_radar.api_credentials import ApiCredentialStore, CredentialValidationError
from info_radar.web_app import client_host_is_loopback, create_app


def clear_test_credentials(monkeypatch) -> None:
    for key in ("GITHUB_TOKEN", "OPENALEX_API_KEY", "X_BEARER_TOKEN"):
        monkeypatch.delenv(key, raising=False)


def test_credential_store_preserves_unmanaged_lines_and_never_returns_values(tmp_path: Path, monkeypatch) -> None:
    clear_test_credentials(monkeypatch)
    env_path = tmp_path / ".env"
    env_path.write_text("# keep this comment\nUNRELATED=value\nGITHUB_TOKEN=old-token\n", encoding="utf-8")
    store = ApiCredentialStore(env_path)

    status = store.update(
        {
            "GITHUB_TOKEN": "github_pat_new-token",
            "OPENALEX_API_KEY": "openalex-key",
        }
    )

    content = env_path.read_text(encoding="utf-8")
    assert "# keep this comment" in content
    assert "UNRELATED=value" in content
    assert "GITHUB_TOKEN=github_pat_new-token" in content
    assert "OPENALEX_API_KEY=openalex-key" in content
    assert stat.S_IMODE(env_path.stat().st_mode) == 0o600
    assert status["GITHUB_TOKEN"]["configured"] is True
    assert status["GITHUB_TOKEN"]["source"] == "local_file"
    serialized_status = json.dumps(status)
    assert "github_pat_new-token" not in serialized_status
    assert "openalex-key" not in serialized_status

    cleared = store.update({}, ["GITHUB_TOKEN"])
    content = env_path.read_text(encoding="utf-8")
    assert "GITHUB_TOKEN=" not in content
    assert "OPENALEX_API_KEY=openalex-key" in content
    assert "UNRELATED=value" in content
    assert cleared["GITHUB_TOKEN"]["configured"] is False


@pytest.mark.parametrize(
    ("values", "clear"),
    [
        ({"UNKNOWN_KEY": "value"}, []),
        ({"GITHUB_TOKEN": "line-one\nline-two"}, []),
        ({"GITHUB_TOKEN": " padded "}, []),
        ({"GITHUB_TOKEN": "value"}, ["GITHUB_TOKEN"]),
    ],
)
def test_credential_store_rejects_unsafe_updates(tmp_path: Path, values, clear) -> None:
    store = ApiCredentialStore(tmp_path / ".env")
    with pytest.raises(CredentialValidationError):
        store.update(values, clear)


def test_settings_api_saves_credentials_without_echoing_them(tmp_path: Path, monkeypatch) -> None:
    clear_test_credentials(monkeypatch)
    env_path = tmp_path / ".env"
    client = TestClient(
        create_app(
            reports_dir=tmp_path / "published",
            static_dir=Path("web"),
            credentials_path=env_path,
            settings_local_only=False,
        )
    )

    page = client.get("/settings")
    assert page.status_code == 200
    assert "把密钥接进雷达" in page.text
    assert "GITHUB_TOKEN" in page.text
    assert "OPENALEX_API_KEY" in page.text

    secret = "github_pat_secret-value"
    response = client.post(
        "/api/settings/credentials",
        json={"values": {"GITHUB_TOKEN": secret}, "clear": []},
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert secret not in response.text
    assert response.json()["credentials"]["GITHUB_TOKEN"]["configured"] is True
    assert secret in env_path.read_text(encoding="utf-8")

    status = client.get("/api/settings/credentials")
    assert status.status_code == 200
    assert secret not in status.text
    assert status.json()["storage"]["returns_secret_values"] is False


def test_settings_routes_are_local_only_by_default(tmp_path: Path) -> None:
    client = TestClient(
        create_app(
            reports_dir=tmp_path / "published",
            static_dir=Path("web"),
            credentials_path=tmp_path / ".env",
        )
    )

    assert client.get("/settings").status_code == 403
    assert client.get("/api/settings/credentials").status_code == 403
    assert client_host_is_loopback("127.0.0.1")
    assert client_host_is_loopback("::1")
    assert not client_host_is_loopback("10.0.0.8")
    assert not client_host_is_loopback("testclient")


def test_settings_api_rejects_unknown_credentials(tmp_path: Path) -> None:
    client = TestClient(
        create_app(
            reports_dir=tmp_path / "published",
            static_dir=None,
            credentials_path=tmp_path / ".env",
            settings_local_only=False,
        )
    )

    response = client.post(
        "/api/settings/credentials",
        json={"values": {"OPENAI_API_KEY": "must-not-be-written"}},
    )

    assert response.status_code == 400
    assert not (tmp_path / ".env").exists()
    assert "OPENAI_API_KEY" in response.json()["detail"]


def test_reader_links_to_local_api_settings() -> None:
    html = Path("web/index.html").read_text(encoding="utf-8")
    css = Path("web/settings.css").read_text(encoding="utf-8")
    js = Path("web/settings.js").read_text(encoding="utf-8")

    assert 'href="/settings"' in html
    assert "SOURCE CREDENTIAL BAY" in Path("web/settings.html").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in css
    assert "localStorage" not in js
    assert "/api/settings/credentials" in js
