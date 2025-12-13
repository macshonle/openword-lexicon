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
SAMPLES_DIR = PROJECT_ROOT / "reference" / "wiktionary" / "samples"


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
            ("running", "run", "VRB"),  # {{infl of|en|run||ing-form}}
            # TODO: Add "sat" when sample is available with {{past tense of}}
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
        inflected_words = ["is", "are", "running"]

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

    The v2 scanner extracts {{suffix}}, {{prefix}}, {{affix}}, {{compound}},
    {{confix}}, and {{surf}} templates from etymology sections and binds
    them to entries with morphology type codes (SUFF, PREF, AFFX, COMP, etc.).
    """

    def test_happiness_is_suffixed(self, hotspot_entries):
        """Verify 'happiness' is detected as suffixed from 'happy'.

        The etymology section contains {{suffix|en|happy|ness}} which should
        be extracted and added to the entry as:
            "codes": ["SUFF"],
            "morphology": {"base": "happy", "suffixes": ["-ness"], "components": [...]}
        Note: morphology type code (SUFF) is in codes array, not in morphology dict.
        """
        if "happiness" not in hotspot_entries:
            pytest.skip("'happiness' not in hotspot samples")

        entries = get_primary_entries(hotspot_entries["happiness"])
        assert entries, "No primary entries for 'happiness'"

        # Find entries with morphology
        morph_entries = [e for e in entries if e.get("morphology")]
        assert morph_entries, "'happiness' should have morphology data"

        # Check morphology type code is in codes array and components are correct
        for entry in morph_entries:
            codes = entry.get("codes", [])
            assert "SUFF" in codes, (
                f"Expected 'SUFF' in codes, got {codes}"
            )
            morph = entry["morphology"]
            assert morph.get("base") == "happy", (
                f"Expected 'happy' as base, got {morph}"
            )
            assert "-ness" in morph.get("suffixes", []), (
                f"Expected '-ness' in suffixes, got {morph}"
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
# Test: Spelling Code Detection
# =============================================================================


class TestSpellingCodeDetection:
    """Test that spelling variants are correctly detected via {{standard spelling of}}.

    The scanner extracts spelling region codes from templates like:
        {{standard spelling of|en|from=Commonwealth|from2=Ireland|color}}

    The from= and from2= parameters map to spelling tags:
        - Commonwealth → SPGB (British/Commonwealth spelling)
        - Ireland → SPIE (Irish spelling)

    The word also gets ALTH flag and the target as lemma.
    """

    def test_colour_has_spelling_codes(self, hotspot_entries):
        """Verify 'colour' has SPGB and SPIE from {{standard spelling of}} template."""
        if "colour" not in hotspot_entries:
            pytest.skip("'colour' not in hotspot samples")

        entries = hotspot_entries["colour"]
        all_codes = set()
        for e in entries:
            all_codes.update(e.get("codes", []))

        # Should have spelling region codes
        assert "SPGB" in all_codes, f"Expected SPGB for 'colour', got {all_codes}"
        assert "SPIE" in all_codes, f"Expected SPIE for 'colour', got {all_codes}"

        # Should have alternative form flag
        assert "ALTH" in all_codes, f"Expected ALTH for 'colour', got {all_codes}"

    def test_colour_has_color_lemma(self, hotspot_entries):
        """Verify 'colour' has 'color' as lemma from {{standard spelling of}} target."""
        if "colour" not in hotspot_entries:
            pytest.skip("'colour' not in hotspot samples")

        entries = hotspot_entries["colour"]
        lemmas = {e.get("lemma") for e in entries if e.get("lemma")}

        assert "color" in lemmas, f"Expected lemma 'color' for 'colour', got {lemmas}"


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
        """Verify minimum number of entries.

        Note: Count is based on primary definitions only (# lines).
        Sub-definitions (##), quotes (#*), and examples (#:) don't create entries.
        """
        total_entries = sum(len(entries) for entries in hotspot_entries.values())
        assert total_entries >= 300, f"Expected 300+ entries, got {total_entries}"

    def test_minimum_word_count(self, hotspot_entries):
        """Verify minimum number of unique words."""
        assert len(hotspot_entries) >= 70, (
            f"Expected 70+ unique words, got {len(hotspot_entries)}"
        )


# =============================================================================
# Test: Category-Based Flag Detection
# =============================================================================


class TestCategoryBasedDetection:
    """Test that categories are correctly used for INFL/ABRV flag detection.

    These tests use synthetic data to verify the category-based detection
    infrastructure, since hotspot samples may not contain explicit categories
    (Wiktionary categories are often dynamically generated by templates).
    """

    def test_category_extraction(self):
        """Test that categories are extracted from wikitext."""
        from openword.scanner.v2.evidence import extract_categories

        text = """
==English==

===Noun===
# A test word.

[[Category:English verb forms]]
[[Category:English abbreviations]]
[[Category:English noun forms]]
"""
        categories = extract_categories(text)
        assert "verb forms" in categories
        assert "abbreviations" in categories
        assert "noun forms" in categories

    def test_category_suffix_to_flag_mapping(self):
        """Test that config has category_suffix_to_flag populated."""
        from pathlib import Path
        from openword.scanner.v2.cdaload import load_binding_config

        config = load_binding_config(
            Path("schema/core"),
            Path("schema/bindings"),
        )

        # INFL categories
        assert "verb forms" in config.category_suffix_to_flag
        assert config.category_suffix_to_flag["verb forms"] == "INFL"
        assert "noun forms" in config.category_suffix_to_flag
        assert config.category_suffix_to_flag["noun forms"] == "INFL"
        assert "plurals" in config.category_suffix_to_flag
        assert config.category_suffix_to_flag["plurals"] == "INFL"

        # ABRV categories
        assert "abbreviations" in config.category_suffix_to_flag
        assert config.category_suffix_to_flag["abbreviations"] == "ABRV"
        assert "initialisms" in config.category_suffix_to_flag
        assert config.category_suffix_to_flag["initialisms"] == "ABRV"
        assert "acronyms" in config.category_suffix_to_flag
        assert config.category_suffix_to_flag["acronyms"] == "ABRV"

    def test_compute_flags_from_categories(self):
        """Test that compute_flags uses categories for flag detection."""
        from pathlib import Path
        from openword.scanner.v2.cdaload import load_binding_config
        from openword.scanner.v2.evidence import Evidence
        from openword.scanner.v2.rules import compute_flags

        config = load_binding_config(
            Path("schema/core"),
            Path("schema/bindings"),
        )

        # Create evidence with INFL category
        evidence_infl = Evidence(
            title="tests",
            wc=1,
            pos_header="Verb",
            categories=["verb forms"],
            categories_lower=["verb forms"],
        )
        flags = compute_flags(evidence_infl, config)
        assert "INFL" in flags, f"Expected INFL flag from category, got {flags}"

        # Create evidence with ABRV category
        evidence_abrv = Evidence(
            title="ABC",
            wc=1,
            pos_header="Noun",
            categories=["abbreviations"],
            categories_lower=["abbreviations"],
        )
        flags = compute_flags(evidence_abrv, config)
        assert "ABRV" in flags, f"Expected ABRV flag from category, got {flags}"

        # Test case-insensitivity (categories_lower is used)
        evidence_case = Evidence(
            title="runs",
            wc=1,
            pos_header="Verb",
            categories=["Verb Forms"],  # Original case
            categories_lower=["verb forms"],  # Lowercased for matching
        )
        flags = compute_flags(evidence_case, config)
        assert "INFL" in flags, f"Expected INFL flag with case variation, got {flags}"

    def test_multiple_category_flags(self):
        """Test that multiple category-based flags can be detected."""
        from pathlib import Path
        from openword.scanner.v2.cdaload import load_binding_config
        from openword.scanner.v2.evidence import Evidence
        from openword.scanner.v2.rules import compute_flags

        config = load_binding_config(
            Path("schema/core"),
            Path("schema/bindings"),
        )

        # Entry with both INFL and ABRV categories (unusual but possible)
        evidence = Evidence(
            title="ABCs",
            wc=1,
            pos_header="Noun",
            categories=["plurals", "initialisms"],
            categories_lower=["plurals", "initialisms"],
        )
        flags = compute_flags(evidence, config)
        assert "INFL" in flags, f"Expected INFL flag, got {flags}"
        assert "ABRV" in flags, f"Expected ABRV flag, got {flags}"
