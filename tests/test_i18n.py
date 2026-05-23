import pytest
from fastapi.testclient import TestClient
from kairos.api.server import app
from kairos.engine.i18n import get_i18n, set_current_lang

client = TestClient(app)

def test_i18n_engine_translation():
    set_current_lang("es")
    assert get_i18n().t("dashboard") == "Dashboard"

    set_current_lang("en")
    assert get_i18n().t("dashboard") == "Dashboard"

    set_current_lang("es")
    assert "Acceso coaches" in get_i18n().t("login_subtitle")

    set_current_lang("en")
    assert "Coach Access" in get_i18n().t("login_subtitle")

def test_middleware_detection_query_param():
    response = client.get("/login?lang=en")
    assert response.status_code == 200
    assert "Coach Access" in response.text

    response = client.get("/login?lang=es")
    assert response.status_code == 200
    assert "Acceso coaches" in response.text
