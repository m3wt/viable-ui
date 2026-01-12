# SPDX-License-Identifier: GPL-2.0-or-later
"""Tests for fragment composition system."""
import pytest
import json
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fragments.composer import FragmentComposer
from change_manager import ChangeManager
from change_manager.changes import FragmentSelectionChange


# Load fixture data
FIXTURE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))),
    'qmk', 'keyboards', 'svalboard', 'keymaps', 'viable', 'viable.json'
)


@pytest.fixture
def fragment_definition():
    """Load the viable-fragments.json fixture."""
    with open(FIXTURE_PATH, 'r') as f:
        return json.load(f)


@pytest.fixture
def composer(fragment_definition):
    """Create a FragmentComposer from fixture."""
    return FragmentComposer(fragment_definition)


class TestFragmentComposer:
    """Test FragmentComposer initialization and basic queries."""

    def test_has_fragments(self, composer):
        """Composer detects fragment-based definition."""
        assert composer.has_fragments()

    def test_fragment_ids(self, composer):
        """Fragment IDs are extracted correctly."""
        # Check that fragments exist
        assert len(composer.fragments) > 0

        # Check IDs are assigned - get first fragment name
        first_frag = list(composer.fragments.keys())[0]
        frag_id = composer.get_fragment_id(first_frag)
        assert isinstance(frag_id, int)
        assert 0 <= frag_id <= 254

        # Check all fragments have valid IDs
        for name, frag in composer.fragments.items():
            assert 'id' in frag
            assert 0 <= frag['id'] <= 254

    def test_instance_count(self, composer):
        """Instance count is extracted correctly."""
        count = composer.get_instance_count()
        assert count > 0
        assert count <= 21  # Max instances

    def test_selectable_instances(self, composer):
        """Selectable instances are identified."""
        selectable = composer.get_selectable_instances()
        # Should be a list of (idx, instance) tuples
        assert isinstance(selectable, list)
        for idx, instance in selectable:
            assert isinstance(idx, int)
            assert 'id' in instance
            assert 'fragment_options' in instance

    def test_fragment_options(self, composer):
        """Fragment options list is extracted correctly."""
        selectable = composer.get_selectable_instances()
        if selectable:
            idx, instance = selectable[0]
            options = composer.get_fragment_options(instance)
            assert isinstance(options, list)
            assert len(options) >= 2  # At least 2 options for selectable

    def test_default_fragment(self, composer):
        """Default fragment is identified correctly."""
        selectable = composer.get_selectable_instances()
        if selectable:
            idx, instance = selectable[0]
            default = composer.get_default_fragment(instance)
            assert default is not None
            assert default in composer.fragments


class TestInstanceResolution:
    """Test fragment resolution with various selection sources."""

    def test_resolve_fixed_instance(self, composer):
        """Fixed instances return their assigned fragment."""
        # Find a fixed instance
        for idx, instance in enumerate(composer.instances):
            if 'fragment' in instance:
                frag_name, placement, matrix_map, encoder_offset = \
                    composer.resolve_instance(idx, instance, {}, {}, {})
                assert frag_name == instance['fragment']
                break

    def test_resolve_default(self, composer):
        """Without any selections, default fragment is used."""
        selectable = composer.get_selectable_instances()
        if selectable:
            idx, instance = selectable[0]
            frag_name, placement, matrix_map, encoder_offset = \
                composer.resolve_instance(idx, instance, {}, {}, {})

            default = composer.get_default_fragment(instance)
            assert frag_name == default

    def test_resolve_keymap_selection(self, composer):
        """Keymap file selection takes priority over EEPROM."""
        selectable = composer.get_selectable_instances()
        if selectable:
            idx, instance = selectable[0]
            string_id = instance['id']
            options = composer.get_fragment_options(instance)

            if len(options) >= 2:
                # Use second option (not default)
                selected = options[1]
                keymap_selections = {string_id: selected}

                frag_name, placement, matrix_map, encoder_offset = \
                    composer.resolve_instance(idx, instance, {}, {}, keymap_selections)

                assert frag_name == selected

    def test_resolve_eeprom_selection(self, composer):
        """EEPROM selection is used when no keymap selection."""
        selectable = composer.get_selectable_instances()
        if selectable:
            idx, instance = selectable[0]
            options = composer.get_fragment_options(instance)

            if len(options) >= 2:
                # Use second option
                selected = options[1]
                frag_id = composer.get_fragment_id(selected)
                eeprom_selections = {idx: frag_id}

                frag_name, placement, matrix_map, encoder_offset = \
                    composer.resolve_instance(idx, instance, {}, eeprom_selections, {})

                assert frag_name == selected

    def test_resolve_hw_detection(self, composer):
        """Hardware detection is used when no user selection."""
        selectable = composer.get_selectable_instances()
        if selectable:
            idx, instance = selectable[0]
            options = composer.get_fragment_options(instance)

            if len(options) >= 2:
                # Use second option
                selected = options[1]
                frag_id = composer.get_fragment_id(selected)
                hw_detection = {idx: frag_id}

                frag_name, placement, matrix_map, encoder_offset = \
                    composer.resolve_instance(idx, instance, hw_detection, {}, {})

                assert frag_name == selected

    def test_resolve_hw_locked(self, composer):
        """Hardware detection with allow_override=False locks the selection."""
        selectable = composer.get_selectable_instances()
        for idx, instance in selectable:
            if not instance.get('allow_override', True):
                # Found a locked instance
                options = composer.get_fragment_options(instance)
                if len(options) >= 2:
                    hw_frag = options[0]
                    user_frag = options[1]

                    hw_frag_id = composer.get_fragment_id(hw_frag)
                    hw_detection = {idx: hw_frag_id}

                    # User tries to select different fragment
                    keymap_selections = {instance['id']: user_frag}

                    frag_name, _, _, _ = \
                        composer.resolve_instance(idx, instance, hw_detection, {}, keymap_selections)

                    # Hardware wins when locked
                    assert frag_name == hw_frag
                break


class TestKeyExpansion:
    """Test expansion of fragments to key lists."""

    def test_expand_returns_keys_and_encoders(self, composer):
        """expand_to_keys returns two lists."""
        keys, encoders = composer.expand_to_keys()

        assert isinstance(keys, list)
        assert isinstance(encoders, list)

    def test_keys_have_matrix_positions(self, composer):
        """Expanded keys have row/col attributes."""
        keys, encoders = composer.expand_to_keys()

        for key in keys:
            assert hasattr(key, 'row')
            assert hasattr(key, 'col')
            # Should have valid positions (from matrix_map)
            assert key.row is not None
            assert key.col is not None

    def test_encoders_have_indices(self, composer):
        """Expanded encoders have encoder_idx attribute."""
        keys, encoders = composer.expand_to_keys()

        for encoder in encoders:
            assert hasattr(encoder, 'encoder_idx')
            assert hasattr(encoder, 'encoder_dir')

    def test_keys_have_positions(self, composer):
        """Expanded keys have x/y coordinates."""
        keys, encoders = composer.expand_to_keys()

        for key in keys:
            assert hasattr(key, 'x')
            assert hasattr(key, 'y')


class TestFragmentSelectionChange:
    """Test the FragmentSelectionChange undo/redo."""

    @pytest.fixture
    def cm(self):
        """Fresh ChangeManager with mock keyboard."""
        ChangeManager._instance = None
        cm = ChangeManager.instance()
        cm.set_keyboard(MockKeyboard())
        return cm

    def test_change_key(self):
        """Change key identifies the instance."""
        change = FragmentSelectionChange(
            instance_id='left_index',
            instance_idx=0,
            old_fragment='frag_a',
            new_fragment='frag_b',
            old_fragment_id=1,
            new_fragment_id=2
        )
        assert change.key() == ('fragment_selection', 'left_index')

    def test_change_merge(self):
        """Multiple changes to same instance can merge."""
        change1 = FragmentSelectionChange(
            instance_id='left_index',
            instance_idx=0,
            old_fragment='frag_a',
            new_fragment='frag_b',
            old_fragment_id=1,
            new_fragment_id=2
        )
        change2 = FragmentSelectionChange(
            instance_id='left_index',
            instance_idx=0,
            old_fragment='frag_b',
            new_fragment='frag_c',
            old_fragment_id=2,
            new_fragment_id=3
        )

        result = change1.merge(change2)
        assert result is True
        assert change1.new_fragment == 'frag_c'
        assert change1.new_fragment_id == 3
        # Old values preserved
        assert change1.old_fragment == 'frag_a'
        assert change1.old_fragment_id == 1

    def test_restore_local(self):
        """restore_local updates keyboard state."""
        keyboard = MockKeyboard()
        keyboard.fragment_selections = {}

        change = FragmentSelectionChange(
            instance_id='left_index',
            instance_idx=0,
            old_fragment='frag_a',
            new_fragment='frag_b',
            old_fragment_id=1,
            new_fragment_id=2
        )

        # Restore new value
        change.restore_local(keyboard, use_old=False)
        assert keyboard.fragment_selections['left_index'] == 'frag_b'

        # Restore old value
        change.restore_local(keyboard, use_old=True)
        assert keyboard.fragment_selections['left_index'] == 'frag_a'


class MockKeyboard:
    """Mock keyboard for testing."""

    def __init__(self):
        self.keyboard_id = 12345
        self.fragment_selections = {}
        self.fragment_eeprom_selections = {}

    def set_fragment_selection(self, instance_idx, fragment_id):
        """Mock EEPROM write."""
        if fragment_id == 0xFF:
            self.fragment_eeprom_selections.pop(instance_idx, None)
        else:
            self.fragment_eeprom_selections[instance_idx] = fragment_id
        return True


# Tests for viable_compress.py schema validation
class TestSchemaValidation:
    """Test viable_compress.py validation functions."""

    def test_valid_fixture_passes(self, fragment_definition):
        """The test fixture should pass validation."""
        # Import validation function
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "viable_compress",
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))),
                'qmk', 'modules', 'viable-kb', 'core', 'viable_compress.py'
            )
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Should not raise
        module.validate_fragment_schema(fragment_definition)

    def test_missing_version_fails(self, fragment_definition):
        """Missing fragment_schema_version should fail."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "viable_compress",
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))),
                'qmk', 'modules', 'viable-kb', 'core', 'viable_compress.py'
            )
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        bad_def = dict(fragment_definition)
        del bad_def['fragment_schema_version']

        with pytest.raises(module.FragmentValidationError) as exc_info:
            module.validate_fragment_schema(bad_def)
        assert 'fragment_schema_version' in str(exc_info.value)

    def test_duplicate_fragment_id_fails(self, fragment_definition):
        """Duplicate fragment IDs should fail."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "viable_compress",
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))),
                'qmk', 'modules', 'viable-kb', 'core', 'viable_compress.py'
            )
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        bad_def = json.loads(json.dumps(fragment_definition))
        # Set all fragment IDs to the same value
        for frag in bad_def['fragments'].values():
            frag['id'] = 1

        with pytest.raises(module.FragmentValidationError) as exc_info:
            module.validate_fragment_schema(bad_def)
        assert 'Duplicate' in str(exc_info.value)
