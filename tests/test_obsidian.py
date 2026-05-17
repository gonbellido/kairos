import pytest
import tempfile
from pathlib import Path
from kairos.engine.obsidian.writer import ObsidianWriter
from kairos.core.client import ClientProfile, ClientState, ClientProgress, SignalMetrics, Alert
from datetime import datetime, timezone


class TestObsidianWriter:
    @pytest.fixture
    def vault(self):
        with tempfile.TemporaryDirectory() as tmp:
            writer = ObsidianWriter(tmp)
            yield writer

    def test_ensure_structure(self, vault):
        vault.ensure_structure()
        assert (vault._base / "Clientes").exists()
        assert (vault._base / "Alertas").exists()
        assert (vault._base / "Dashboard").exists()
        assert (vault._base / "Metodología").exists()

    def test_write_client_profile(self, vault):
        profile = ClientProfile(
            id="c1", nombre="Ana García", coach_id="coach1",
            estado_actual=ClientState(emocional="ansioso", claridad=0.3, energia=0.4, resistencia=0.7),
            progreso=ClientProgress(
                score_global=0.35,
                senales=SignalMetrics(claridad=0.3, accion=0.5, apertura=0.4, consistencia=0.6),
            ),
        )
        path = vault.write_client_profile(profile)
        assert path.exists()
        content = path.read_text()
        assert "Ana García" in content
        assert "ansioso" in content
        assert "35%" in content  # score_global
        assert "0.3" in content   # claridad (frontmatter)
        assert "kairos/cliente" in content
        assert "score_global:" in content

    def test_write_alert(self, vault):
        alert = Alert(
            tipo="alta_resistencia", nivel="high",
            mensaje="Cliente Ana muestra alta resistencia",
            cliente_id="c1",
        )
        path = vault.write_alert(alert)
        assert path.exists()
        content = path.read_text()
        assert "alta_resistencia" in content
        assert "Cliente Ana" in content
        assert "🔴" in content or "high" in content

    def test_write_dashboard(self, vault):
        clients = [
            ClientProfile(id="c1", nombre="Ana", progreso=ClientProgress(score_global=0.3)),
            ClientProfile(id="c2", nombre="Luis", progreso=ClientProgress(score_global=0.8)),
        ]
        path = vault.write_dashboard(clients)
        assert path.exists()
        content = path.read_text()
        assert "Portafolio" in content
        assert "TABLE" in content
        assert "nombre as Cliente" in content
        assert "SORT score_global ASC" in content
        assert "#kairos/cliente" in content

    def test_write_config_template(self, vault):
        path = vault.write_config_template()
        assert path.exists()
        content = path.read_text()
        assert "Impronta Override" in content
        assert "Instrucciones Calientes" in content

    def test_parse_config(self, vault):
        config_path = vault._base / "Config.md"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("""
# ⚙️ Config

## 🎭 Impronta Override
```yaml
ana_garcia: { "directividad": 0.7, "emocionalidad": 0.4 }
```
""")
        result = vault.parse_config()
        assert "ana_garcia" in result
        assert result["ana_garcia"]["directividad"] == 0.7
        assert result["ana_garcia"]["emocionalidad"] == 0.4

    def test_empty_config_returns_empty(self, vault):
        result = vault.parse_config()
        assert result == {}

    def test_safe_name(self):
        assert ObsidianWriter._safe_name("Ana García") == "Ana_García"
        assert ObsidianWriter._safe_name("test/path:fail") == "test_path_fail"
