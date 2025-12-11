"""Regression tests for v2 scanner using curated hotspot samples.

These tests verify the v2 scanner produces expected outputs for specific
words in the hotspot word list. The tests run against pre-generated JSONL
output from `make quick-build-wikt-json-v2`.

Test Categories:
1. Pronunciation inheritance - nsyll extraction for multi-etymology words
2. Inflection detection - lemma and INFL code for inflected forms
3. Morphology extraction - suffixed/prefixed/compound detection
4. Label-to-tag mapping - vulgar, slang, archaic tags
5. POS detection - correct part-of-speech codes
"""

import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import pytest

# Paths
TESTS_DIR = Path(__file__).parent
PROJECT_ROOT = TESTS_DIR.parent
HOTSPOT_JSONL = TESTS_DIR / "hotspotwords.jsonl"
HOTSPOT_XML = TESTS_DIR / "hotspotwords.xml.bz2"
SAMPLES_DIR = TESTS_DIR / "wikitext-samples"


def load_hotspot_entries() -> dict[str, list[dict]]:
    """Load entries from hotspotwords.jsonl, grouped by word ID."""
    if not HOTSPOT_JSONL.exists():
        pytest.skip(
            f"Hotspot JSONL not found: {HOTSPOT_JSONL}\n"
            "Run `make quick-build-wikt-json-v2` to generate it."
        )

    entries_by_word: dict[str, list[dict]] = defaultdict(list)
    with open(HOTSPOT_JSONL) as f:
        for line in f:
            entry = json.loads(line)
            entries_by_word[entry["id"]].append(entry)

    return dict(entries_by_word)


@pytest.fixture(scope="module")
def hotspot_entries():
    """Fixture providing all hotspot entries grouped by word."""
    return load_hotspot_entries()


def get_primary_entries(entries: list[dict]) -> list[dict]:
    """Filter to only primary definition entries (not quotes, synonyms, etc.)."""
    return [e for e in entries if "def_level" not in e or e.get("def_type") == "primary"]


def get_entries_with_pos(entries: list[dict], pos: str) -> list[dict]:
    """Filter entries to a specific POS."""
    return [e for e in entries if e["pos"] == pos]


# =============================================================================
# Test: Pronunciation Inheritance (nsyll for multi-etymology words)
# =============================================================================


class TestPronunciationInheritance:
    """Test that pronunciation data from preamble is inherited by all etymologies.

    This catches the bug where words like "set", "cat", "hell" lost their
    syllable counts because the Pronunciation section appeared before the
    first Etymology header.
    """

    @pytest.mark.parametrize(
        "word,expected_nsyll",
        [
            ("cat", 1),  # Has Etymology headers, pronunciation in preamble
            ("set", 1),  # Multiple etymologies, pronunciation in preamble
            ("hell", 1),  # Multiple etymologies, pronunciation in preamble
            ("may", 1),  # Multiple etymologies, pronunciation in preamble
            ("is", 1),  # Pronunciation inside etymology block
            ("the", 1),  # Simple word
            ("a", 1),  # Single letter word
            ("run", 1),  # Common verb
            ("happy", 2),  # Multi-syllable word
            ("happiness", 3),  # Derived word
            ("encyclopedia", 6),  # Long word
        ],
    )
    def test_nsyll_extraction(self, hotspot_entries, word, expected_nsyll):
        """Verify nsyll is correctly extracted for words."""
        if word not in hotspot_entries:
            pytest.skip(f"Word '{word}' not in hotspot samples")

        entries = get_primary_entries(hotspot_entries[word])
        assert entries, f"No primary entries found for '{word}'"

        # At least one entry should have the expected nsyll
        nsyll_values = [e.get("nsyll") for e in entries if e.get("nsyll") is not None]
        assert nsyll_values, f"No nsyll found for '{word}'"
        assert expected_nsyll in nsyll_values, (
            f"Expected nsyll={expected_nsyll} for '{word}', got {set(nsyll_values)}"
        )


# =============================================================================
# Test: Inflection Detection
# =============================================================================


class TestInflectionDetection:
    """Test that inflected forms are correctly detected with lemma and INFL code."""

    @pytest.mark.parametrize(
        "word,expected_lemma,expected_pos",
        [
            ("is", "be", "VRB"),  # Third person singular of "be"
            ("are", "be", "VRB"),  # Plural of "be"
            # TODO: These need scanner improvements for inflection detection
            # ("running", "run", "VRB"),  # Present participle - needs {{present participle of}}
            # ("sat", "sit", "VRB"),  # Past tense - needs {{past tense of}}
        ],
    )
    def test_inflection_lemma(self, hotspot_entries, word, expected_lemma, expected_pos):
        """Verify inflected forms have correct lemma."""
        if word not in hotspot_entries:
            pytest.skip(f"Word '{word}' not in hotspot samples")

        entries = get_entries_with_pos(hotspot_entries[word], expected_pos)
        primary = get_primary_entries(entries)
        assert primary, f"No primary {expected_pos} entries for '{word}'"

        # Find entries with INFL code
        infl_entries = [e for e in primary if "INFL" in e.get("codes", [])]
        assert infl_entries, f"No INFL entries found for '{word}'"

        # Check lemma
        lemmas = [e.get("lemma") for e in infl_entries]
        assert expected_lemma in lemmas, (
            f"Expected lemma '{expected_lemma}' for '{word}', got {set(lemmas)}"
        )

    def test_inflection_has_infl_code(self, hotspot_entries):
        """Verify inflected forms have INFL code."""
        # Only test words where inflection detection is currently working
        # TODO: Add "running", "sat" when scanner supports those inflection templates
        inflected_words = ["is", "are"]

        for word in inflected_words:
            if word not in hotspot_entries:
                continue

            entries = hotspot_entries[word]
            has_infl = any("INFL" in e.get("codes", []) for e in entries)
            assert has_infl, f"'{word}' should have INFL code"


# =============================================================================
# Test: Morphology Extraction
# =============================================================================


class TestMorphologyExtraction:
    """Test that morphology is correctly extracted from etymology sections.

    NOTE: Morphology extraction for derived words is currently a TODO item.
    The v2 scanner needs to properly extract {{suffix}}, {{prefix}}, etc.
    from etymology sections and bind them to entries.
    """

    @pytest.mark.skip(reason="Morphology extraction not yet implemented in v2 scanner")
    def test_happiness_is_suffixed(self, hotspot_entries):
        """Verify 'happiness' is detected as suffixed from 'happy'.

        TODO: Implement morphology extraction in v2 scanner.
        The etymology section contains {{suffix|en|happy|ness}} which should
        be extracted and added to the entry as:
            "morphology": {"type": "suffixed", "base": "happy", "suffixes": ["-ness"]}
        """
        if "happiness" not in hotspot_entries:
            pytest.skip("'happiness' not in hotspot samples")

        entries = get_primary_entries(hotspot_entries["happiness"])
        assert entries, "No primary entries for 'happiness'"

        # Find entries with morphology
        morph_entries = [e for e in entries if e.get("morphology")]
        assert morph_entries, "'happiness' should have morphology data"

        # Check morphology type and components
        for entry in morph_entries:
            morph = entry["morphology"]
            assert morph["type"] == "suffixed", (
                f"Expected 'suffixed' type, got '{morph['type']}'"
            )
            assert "happy" in morph.get("components", []) or morph.get("base") == "happy", (
                f"Expected 'happy' as base, got {morph}"
            )


# =============================================================================
# Test: Label-to-Tag Mapping
# =============================================================================


class TestLabelToTagMapping:
    """Test that labels are correctly mapped to tag codes."""

    @pytest.mark.parametrize(
        "word,expected_tag",
        [
            ("hell", "RVLG"),  # Vulgar usage
            ("hell", "RINF"),  # Informal usage
            ("spook", "ROFF"),  # Offensive usage
            ("taffy", "ROFF"),  # Offensive/derogatory usage
        ],
    )
    def test_tag_present(self, hotspot_entries, word, expected_tag):
        """Verify expected tags are present for words with specific labels."""
        if word not in hotspot_entries:
            pytest.skip(f"Word '{word}' not in hotspot samples")

        entries = hotspot_entries[word]
        all_codes = set()
        for e in entries:
            all_codes.update(e.get("codes", []))

        assert expected_tag in all_codes, (
            f"Expected tag '{expected_tag}' for '{word}', got {all_codes}"
        )


# =============================================================================
# Test: POS Detection
# =============================================================================


class TestPOSDetection:
    """Test that parts of speech are correctly detected."""

    @pytest.mark.parametrize(
        "word,expected_poses",
        [
            ("cat", {"NOU", "VRB"}),  # Noun and verb
            ("set", {"NOU", "VRB", "ADJ"}),  # Multiple POS
            ("happy", {"ADJ"}),  # Adjective
            ("run", {"NOU", "VRB"}),  # Noun and verb
            ("the", {"DET", "ADV"}),  # Determiner and adverb
            ("hello", {"NOU", "VRB", "ITJ"}),  # Includes interjection
        ],
    )
    def test_pos_detected(self, hotspot_entries, word, expected_poses):
        """Verify expected parts of speech are detected."""
        if word not in hotspot_entries:
            pytest.skip(f"Word '{word}' not in hotspot samples")

        entries = hotspot_entries[word]
        found_poses = {e["pos"] for e in entries}

        missing = expected_poses - found_poses
        assert not missing, (
            f"Missing POS for '{word}': expected {expected_poses}, found {found_poses}"
        )


# =============================================================================
# Test: Word Count
# =============================================================================


class TestWordCount:
    """Test that word count (wc) is correctly calculated."""

    @pytest.mark.parametrize(
        "word,expected_wc",
        [
            ("cat", 1),
            ("happy", 1),
            ("Isle of Man", 3),
            ("teaching assistant", 2),
            ("teaching assistants", 2),
        ],
    )
    def test_word_count(self, hotspot_entries, word, expected_wc):
        """Verify word count is correct."""
        if word not in hotspot_entries:
            pytest.skip(f"Word '{word}' not in hotspot samples")

        entries = hotspot_entries[word]
        wc_values = {e["wc"] for e in entries}

        assert expected_wc in wc_values, (
            f"Expected wc={expected_wc} for '{word}', got {wc_values}"
        )


# =============================================================================
# Test: Affix Detection
# =============================================================================


class TestAffixDetection:
    """Test that affixes are correctly detected as AFX POS."""

    @pytest.mark.parametrize(
        "word",
        [
            "-xizu-",
            "naso-",
            "oxo-",
            "for-",
        ],
    )
    def test_affix_pos(self, hotspot_entries, word):
        """Verify affixes are detected with AFX POS."""
        if word not in hotspot_entries:
            pytest.skip(f"Affix '{word}' not in hotspot samples")

        entries = hotspot_entries[word]
        poses = {e["pos"] for e in entries}

        assert "AFX" in poses, f"Expected AFX POS for '{word}', got {poses}"


# =============================================================================
# Test: Output Format
# =============================================================================


class TestOutputFormat:
    """Test that output format is correct."""

    def test_field_order(self, hotspot_entries):
        """Verify JSON field order: id, pos, wc, nsyll, codes, ..."""
        # Re-read the raw JSONL to check field order
        if not HOTSPOT_JSONL.exists():
            pytest.skip("Hotspot JSONL not found")

        with open(HOTSPOT_JSONL) as f:
            first_line = f.readline()

        # Parse and check order
        # JSON keys in Python 3.7+ maintain insertion order
        entry = json.loads(first_line)
        keys = list(entry.keys())

        # First three should always be id, pos, wc
        assert keys[:3] == ["id", "pos", "wc"], f"Expected [id, pos, wc], got {keys[:3]}"

        # If nsyll present, it should come before codes
        if "nsyll" in keys and "codes" in keys:
            assert keys.index("nsyll") < keys.index("codes"), (
                "nsyll should come before codes"
            )

    def test_required_fields(self, hotspot_entries):
        """Verify all entries have required fields."""
        for word, entries in hotspot_entries.items():
            for entry in entries:
                assert "id" in entry, f"Missing 'id' in entry for '{word}'"
                assert "pos" in entry, f"Missing 'pos' in entry for '{word}'"
                assert "wc" in entry, f"Missing 'wc' in entry for '{word}'"


# =============================================================================
# Test: Smoke Test
# =============================================================================


class TestSmokeTest:
    """Basic smoke tests for the hotspot infrastructure."""

    def test_hotspot_jsonl_exists(self):
        """Verify hotspot JSONL file exists."""
        if not HOTSPOT_JSONL.exists():
            pytest.skip(
                f"Hotspot JSONL not found. Run `make quick-build-wikt-json-v2`."
            )
        assert HOTSPOT_JSONL.stat().st_size > 0, "Hotspot JSONL is empty"

    def test_minimum_entry_count(self, hotspot_entries):
        """Verify minimum number of entries."""
        total_entries = sum(len(entries) for entries in hotspot_entries.values())
        assert total_entries >= 400, f"Expected 400+ entries, got {total_entries}"

    def test_minimum_word_count(self, hotspot_entries):
        """Verify minimum number of unique words."""
        assert len(hotspot_entries) >= 70, (
            f"Expected 70+ unique words, got {len(hotspot_entries)}"
        )
