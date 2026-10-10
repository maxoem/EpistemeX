from episteme_pipeline.runs.fingerprints import (
    _fingerprint_nested_leafs,
    fingerprint_phase_config_nested,
)


def test_nested_leafs_simple_dict() -> None:
    result = _fingerprint_nested_leafs({"a": 1, "b": "hello"}, prefix="")
    assert result["a"] != result["b"]
    assert isinstance(result["a"], str)
    assert isinstance(result["b"], str)


def test_nested_leafs_deterministic() -> None:
    obj = {"x": {"y": [1, 2, 3]}, "z": True}
    result1 = _fingerprint_nested_leafs(obj, prefix="")
    result2 = _fingerprint_nested_leafs(obj, prefix="")
    assert result1 == result2


def test_nested_leafs_nested_structure() -> None:
    obj = {"level1": {"level2": "value"}}
    result = _fingerprint_nested_leafs(obj, prefix="")
    assert "level1.level2" in result


def test_nested_leafs_list_handling() -> None:
    obj = {"items": [10, 20]}
    result = _fingerprint_nested_leafs(obj, prefix="")
    assert "items[0]" in result
    assert "items[1]" in result


def test_nested_leafs_mixed_nested() -> None:
    obj = {"a": "simple", "b": {"c": [1, {"d": "deep"}]}}
    result = _fingerprint_nested_leafs(obj, prefix="")
    assert "a" in result
    assert "b.c[0]" in result
    assert "b.c[1].d" in result


def test_nested_leafs_empty_dict() -> None:
    result = _fingerprint_nested_leafs({}, prefix="")
    assert result == {}


def test_nested_leafs_non_dict_input() -> None:
    result = _fingerprint_nested_leafs("string", prefix="")
    assert isinstance(result, dict)


def test_nested_leafs_unserializable_nested() -> None:
    """Unserializable values are skipped (return empty for that leaf)."""

    class CustomClass:
        pass

    result = _fingerprint_nested_leafs({"obj": CustomClass()}, prefix="")
    assert result == {}


def test_fingerprint_phase_config_nested_simple() -> None:
    """Test with a simple dict-like object."""

    class MockConfig:
        def __init__(self):
            self.__dict__ = {"setting_a": 42, "setting_b": "text"}

    result = fingerprint_phase_config_nested(MockConfig())
    assert isinstance(result, dict)
    assert len(result) > 0
    assert "setting_a" in result
    assert "setting_b" in result


def test_fingerprint_phase_config_nested_different_leafs_different_fps() -> None:
    """Different leaf values should produce different fingerprints."""

    class MockConfigA:
        def __init__(self):
            self.__dict__ = {"value": 1}

    class MockConfigB:
        def __init__(self):
            self.__dict__ = {"value": 2}

    result_a = fingerprint_phase_config_nested(MockConfigA())
    result_b = fingerprint_phase_config_nested(MockConfigB())
    assert result_a != result_b


def test_fingerprint_phase_config_nested_deterministic() -> None:
    """Same config should produce same fingerprints across runs."""

    class MockConfig:
        def __init__(self):
            self.__dict__ = {"x": 10, "y": "test"}

    result1 = fingerprint_phase_config_nested(MockConfig())
    result2 = fingerprint_phase_config_nested(MockConfig())
    assert result1 == result2


def test_fingerprint_phase_config_nested_deeply_nested() -> None:
    """Nested dicts and lists should produce fine-grained per-leaf fingerprints."""

    class MockConfig:
        def __init__(self):
            self.__dict__ = {"deep": {"level2": {"key": "val"}}}

    result = fingerprint_phase_config_nested(MockConfig())
    assert "deep.level2.key" in result


def test_fingerprint_phase_config_nested_empty() -> None:
    class MockConfig:
        def __init__(self):
            self.__dict__ = {}

    result = fingerprint_phase_config_nested(MockConfig())
    assert result == {}


def test_fine_grained_leaf_detection() -> None:
    """Changed leaf has different fingerprint while unchanged leaves match."""

    class BaseConfig:
        def __init__(self):
            self.__dict__ = {
                "unchanged_int": 42,
                "unchanged_str": "same",
                "nested": {"a": 1, "b": 2},
            }

    config_a = BaseConfig()
    result_a = fingerprint_phase_config_nested(config_a)

    class ConfigB(BaseConfig):
        def __init__(self):
            self.__dict__ = {
                "unchanged_int": 42,
                "unchanged_str": "same",
                "nested": {"a": 999, "b": 2},
            }

    config_b = ConfigB()
    result_b = fingerprint_phase_config_nested(config_b)

    # Unchanged leaves should have identical fingerprints
    assert result_a["unchanged_int"] == result_b["unchanged_int"]
    assert result_a["unchanged_str"] == result_b["unchanged_str"]
    assert result_a["nested.b"] == result_b["nested.b"]

    # Changed leaf should differ
    assert result_a["nested.a"] != result_b["nested.a"]
