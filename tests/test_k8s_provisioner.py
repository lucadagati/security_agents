"""Provisioning helpers stay side-effect free unless invoked."""

from coevsec.environment.k8s.provisioner import tooling_available, CHART_DIR, KIND_CONFIG


def test_chart_and_kind_config_exist():
    assert CHART_DIR.exists()
    assert (CHART_DIR / "Chart.yaml").exists()
    assert (CHART_DIR / "templates" / "gateway.yaml").exists()
    assert (CHART_DIR / "templates" / "datastore.yaml").exists()
    assert KIND_CONFIG.exists()


def test_tooling_available_reports_tuple():
    ok, missing = tooling_available()
    assert isinstance(ok, bool)
    assert isinstance(missing, list)
    # kind is not required to be installed for the rest of the framework.
    if not ok:
        assert "kind" in missing or "kubectl" in missing or "helm" in missing
