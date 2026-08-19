"""Tests for the connector_renaming module."""

from pydexpi.syndata.connector_renaming import ConnectorRenamingConvention


def test_connector_renaming_convention_init():
    """Test initialization of a ConnectorRenamingConvention."""
    renaming = ConnectorRenamingConvention()
    assert renaming.encountered_pattern_counter == {}


def test_connector_renaming_convention_rename_connectors(simple_pattern_factory):
    """Test renaming connectors in a pattern."""
    # Create a pattern
    pattern = simple_pattern_factory("TestPattern")
    # Get initial connector labels
    original_labels = list(pattern.connectors.keys())

    # Create renaming convention
    renaming = ConnectorRenamingConvention()

    # Rename all connectors
    renaming.rename_connectors(pattern, [])

    # Check that connector labels have changed
    new_labels = list(pattern.connectors.keys())
    assert set(original_labels) != set(new_labels)

    # Check format of new labels
    for label in new_labels:
        assert label.startswith("TestPattern_")
        # Should follow format pattern_counter_original_label
        parts = label.split("_")
        assert parts[0] == "TestPattern"
        assert parts[1].isdigit()

        # Label key convention retained
        assert label == pattern.connectors[label].label


def test_connector_renaming_convention_rename_skip_connectors(simple_pattern_factory):
    """Test skipping specific connectors during renaming."""
    # Create a pattern
    pattern = simple_pattern_factory("TestPattern")

    # Get a connector to skip
    connectors_list = list(pattern.connectors.values())
    connector_to_skip = connectors_list[0]
    original_label = connector_to_skip.label

    # Create renaming convention
    renaming = ConnectorRenamingConvention()

    # Rename connectors, skipping one
    renaming.rename_connectors(pattern, [connector_to_skip])

    # Check that skipped connector label didn't change
    assert connector_to_skip.label == original_label

    # Check other connector was renamed
    other_connector = connectors_list[1]
    assert other_connector.label != original_label
    assert other_connector.label.startswith("TestPattern_")


def test_connector_renaming_convention_reset_counter(simple_pattern_factory):
    """Test resetting the counter."""
    # Create patterns
    pattern1 = simple_pattern_factory("TestPattern")
    pattern2 = simple_pattern_factory("TestPattern")

    # Create renaming convention
    renaming = ConnectorRenamingConvention()

    # Rename first pattern connectors
    renaming.rename_connectors(pattern1, [])
    first_renamed_labels = list(pattern1.connectors.keys())

    # Reset counter
    renaming.reset()

    # Rename second pattern connectors
    renaming.rename_connectors(pattern2, [])
    second_renamed_labels = list(pattern2.connectors.keys())

    # The labels should be the same since counter was reset
    assert set(first_renamed_labels) == set(second_renamed_labels)


def test_connector_renaming_convention_incremental_renaming(simple_pattern_factory):
    """Test that pattern counter increments for subsequent patterns with same label."""
    # Create patterns with the same label
    pattern1 = simple_pattern_factory("SameLabel")
    pattern2 = simple_pattern_factory("SameLabel")

    # Create renaming convention
    renaming = ConnectorRenamingConvention()

    # Rename first pattern
    renaming.rename_connectors(pattern1, [])
    pattern1_labels = list(pattern1.connectors.keys())

    # All labels should have index 0
    for label in pattern1_labels:
        parts = label.split("_")
        assert parts[0] == "SameLabel"
        assert parts[1] == "0"

    # Rename second pattern
    renaming.rename_connectors(pattern2, [])
    pattern2_labels = list(pattern2.connectors.keys())

    # All labels should have index 1
    for label in pattern2_labels:
        parts = label.split("_")
        assert parts[0] == "SameLabel"
        assert parts[1] == "1"
