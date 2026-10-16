"""Test connection to FalkorDB."""

from dig.graph.client import check_health, get_graph


def test_falkordb_return_one():
    """Verify FalkorDB connectivity by executing RETURN 1."""
    graph = get_graph("dig_test_connection")
    result = graph.query("RETURN 1 AS val")
    assert result.result_set is not None
    assert len(result.result_set) == 1
    assert result.result_set[0][0] == 1


def test_falkordb_check_health():
    """Verify health check function returns valid payload."""
    health = check_health("dig_test_connection")
    assert health["ok"] is True
    assert health["graph"] == "dig_test_connection"
    assert "counts" in health
