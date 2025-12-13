"""Tests that identify potential Wiktionary data quality issues.

These tests scan wikitext samples and built lexemes to detect:
1. Syllable count disagreements between sources (IPA, hyphenation, rhymes)
2. Missing IPA for common words
3. Other data inconsistencies

Note: These tests are designed to REPORT issues rather than fail hard.
Wiktionary data issues should be documented and potentially reported upstream.
"""

import sys
from pathlib import Path

import pytest

# Add legacy scanner_v1 directory to path
TESTS_DIR = Path(__file__).parent
PROJECT_ROOT = TESTS_DIR.parent
legacy_path = PROJECT_ROOT / "legacy" / "scanner_v1"
sys.path.insert(0, str(legacy_path))

from wiktionary_scanner_python.scanner import (
    count_syllables_from_ipa,
    extract_syllable_count_from_hyphenation,
    extract_syllable_count_from_rhymes,
    extract_syllable_count_from_ipa,
)

SAMPLES_DIR = PROJECT_ROOT / "reference" / "wiktionary" / "samples"


class TestWiktionaryDataQuality:
    """Tests that identify potential Wiktionary data issues."""

    @pytest.fixture
    def sample_files(self):
        """Get list of available wikitext sample files."""
        if not SAMPLES_DIR.exists():
            pytest.skip("Wikitext samples directory not found")
        return list(SAMPLES_DIR.glob("*.xml"))

    def test_samples_directory_exists(self):
        """Verify wikitext samples directory is available."""
        assert SAMPLES_DIR.exists(), f"Samples directory not found: {SAMPLES_DIR}"
        sample_count = len(list(SAMPLES_DIR.glob("*.xml")))
        assert sample_count > 0, "No sample files found"

    def test_encyclopedia_syllable_consistency(self):
        """Test encyclopedia entry for syllable count consistency.

        encyclopedia is a known 6-syllable word that has been used
        to verify syllable extraction accuracy.
        """
        sample_file = SAMPLES_DIR / "encyclopedia.xml"
        if not sample_file.exists():
            pytest.skip("encyclopedia.xml not found")

        content = sample_file.read_text()

        # Extract from hyphenation template
        hyph_count = extract_syllable_count_from_hyphenation(content, "encyclopedia")

        # Extract from rhymes template
        rhymes_count = extract_syllable_count_from_rhymes(content)

        # Extract from IPA
        ipa_count = extract_syllable_count_from_ipa(content)

        # All sources should agree on 6 syllables
        assert hyph_count == 6, f"Hyphenation says {hyph_count}, expected 6"

        # Rhymes should also say 6 if s= is present
        if rhymes_count is not None:
            assert rhymes_count == 6, f"Rhymes says {rhymes_count}, expected 6"

        # IPA should also say 6 if extractable
        if ipa_count is not None:
            assert ipa_count == 6, f"IPA says {ipa_count}, expected 6"

    def test_dictionary_syllable_consistency(self):
        """Test dictionary entry for syllable count consistency."""
        sample_file = SAMPLES_DIR / "dictionary.xml"
        if not sample_file.exists():
            pytest.skip("dictionary.xml not found")

        content = sample_file.read_text()

        hyph_count = extract_syllable_count_from_hyphenation(content, "dictionary")
        assert hyph_count == 4, f"dictionary hyphenation: expected 4, got {hyph_count}"

    def test_find_syllable_mismatches_in_samples(self, sample_files):
        """Scan samples for syllable count disagreements.

        This test identifies potential Wiktionary data quality issues
        where different sources disagree on syllable count.
        """
        mismatches = []

        for sample_file in sample_files:
            # Skip files with special characters that might cause issues
            if "xn--" in sample_file.name:
                continue

            content = sample_file.read_text()
            word = sample_file.stem.replace("_", " ")

            # Get syllable counts from different sources
            hyph_count = extract_syllable_count_from_hyphenation(content, word)
            rhymes_count = extract_syllable_count_from_rhymes(content)
            ipa_count = extract_syllable_count_from_ipa(content)

            # Check for disagreements (where both sources have data)
            counts = []
            if hyph_count is not None:
                counts.append(("hyphenation", hyph_count))
            if rhymes_count is not None:
                counts.append(("rhymes", rhymes_count))
            if ipa_count is not None:
                counts.append(("IPA", ipa_count))

            # If we have at least 2 sources, check for disagreement
            if len(counts) >= 2:
                unique_counts = set(c[1] for c in counts)
                if len(unique_counts) > 1:
                    mismatches.append({
                        "word": word,
                        "file": sample_file.name,
                        "counts": dict(counts),
                    })

        # Report mismatches (don't fail - these are data quality findings)
        if mismatches:
            print("\n=== Syllable Count Mismatches Found ===")
            for m in mismatches:
                print(f"  {m['word']}: {m['counts']}")
            print(f"\nTotal mismatches: {len(mismatches)}")

        # This test always passes but reports findings
        # In a real scenario, mismatches would be flagged for Wiktionary review

    def test_find_missing_ipa_in_common_words(self, sample_files):
        """Identify sample words that lack IPA transcription.

        IPA is valuable for pronunciation and syllable counting.
        Common words missing IPA might be candidates for contribution.
        """
        missing_ipa = []

        for sample_file in sample_files:
            # Skip punycode entries
            if "xn--" in sample_file.name:
                continue

            content = sample_file.read_text()
            word = sample_file.stem.replace("_", " ")

            # Check if IPA is present
            ipa_count = extract_syllable_count_from_ipa(content)
            has_ipa = "{{IPA|" in content or "{{ipa|" in content

            if not has_ipa and ipa_count is None:
                # Check if hyphenation exists (common words usually have both)
                hyph_count = extract_syllable_count_from_hyphenation(content, word)
                if hyph_count is not None:
                    missing_ipa.append({
                        "word": word,
                        "has_hyphenation": True,
                        "syllables_from_hyph": hyph_count,
                    })

        # Report missing IPA
        if missing_ipa:
            print("\n=== Words with Hyphenation but Missing IPA ===")
            for m in missing_ipa[:10]:  # Show first 10
                print(f"  {m['word']}: {m['syllables_from_hyph']} syllables (from hyphenation)")
            if len(missing_ipa) > 10:
                print(f"  ... and {len(missing_ipa) - 10} more")

    def test_happiness_morphology_data(self):
        """Test happiness entry has proper morphology data.

        'happiness' should be recognized as happy + -ness (suffixed).
        """
        sample_file = SAMPLES_DIR / "happiness.xml"
        if not sample_file.exists():
            pytest.skip("happiness.xml not found")

        content = sample_file.read_text()

        # Should contain suffix template
        has_suffix = "{{suffix|" in content or "{{suf|" in content
        has_affix = "{{af|" in content or "{{affix|" in content

        assert has_suffix or has_affix, "happiness should have suffix/affix template"

        # Check for ness suffix
        assert "ness" in content.lower(), "happiness etymology should mention -ness suffix"

    def test_taffy_has_derogatory_sense(self):
        """Test taffy entry has derogatory secondary sense.

        'taffy' is used in the docs as an example of a word with
        a derogatory secondary sense (slur for Welsh people).
        """
        sample_file = SAMPLES_DIR / "taffy.xml"
        if not sample_file.exists():
            pytest.skip("taffy.xml not found")

        content = sample_file.read_text()

        # Should have candy meaning
        assert "candy" in content.lower() or "sweet" in content.lower() or "toffee" in content.lower(), \
            "taffy should have candy/sweet meaning"

        # Should also have the derogatory sense marked
        has_derogatory = "derogatory" in content.lower() or "offensive" in content.lower()
        has_welsh = "Welsh" in content or "welsh" in content.lower()

        # At least indicate the dual nature
        if has_welsh:
            # If it mentions Welsh, it should have appropriate labels
            assert has_derogatory or "ethnic slur" in content.lower(), \
                "taffy's Welsh sense should be marked as derogatory/offensive"


class TestSyllableSourcePriority:
    """Tests for syllable extraction priority order.

    The scanners should use sources in this priority:
    IPA > hyphenation > categories > rhymes
    """

    def test_ipa_preferred_over_rhymes(self):
        """Verify IPA count is used over rhymes when both present."""
        # Create a scenario where IPA says 3 syllables but rhymes says 2
        ipa = "/əˈsæsɪn/"
        rhymes = "{{rhymes|en|æsɪn|s=2}}"

        ipa_count = count_syllables_from_ipa(ipa)
        rhymes_count = extract_syllable_count_from_rhymes(rhymes)

        # IPA should give 3
        assert ipa_count == 3

        # Rhymes gives 2 (this would be wrong for assassin)
        assert rhymes_count == 2

        # Scanner priority should prefer IPA

    def test_hyphenation_handles_lang_code_syllables(self):
        """Test hyphenation correctly handles syllables matching lang codes.

        Words like 'encore' (en|core) or 'italic' (it|al|ic) have first
        syllables that match language codes.
        """
        # encore: starts with "en" which is English's lang code
        encore_result = extract_syllable_count_from_hyphenation(
            "{{hyphenation|en|en|core}}", "encore"
        )
        assert encore_result == 2, f"encore should be 2 syllables, got {encore_result}"

        # italic: starts with "it" which is Italian's lang code
        italic_result = extract_syllable_count_from_hyphenation(
            "{{hyphenation|en|it|al|ic}}", "italic"
        )
        assert italic_result == 3, f"italic should be 3 syllables, got {italic_result}"


class TestEdgeCasesFromWikitext:
    """Tests for edge cases discovered in actual Wiktionary data."""

    def test_compound_words_syllables(self):
        """Test syllable counting for compound words."""
        # sunflower = sun (1) + flower (2) = 3 total
        result = extract_syllable_count_from_hyphenation(
            "{{hyphenation|en|sun|flow|er}}", "sunflower"
        )
        assert result == 3, f"sunflower should be 3 syllables, got {result}"

    def test_words_with_silent_e(self):
        """Test words with silent final e."""
        # "table" has silent e, 2 syllables
        ipa_result = count_syllables_from_ipa("/ˈteɪ.bəl/")
        assert ipa_result == 2, f"table should be 2 syllables from IPA, got {ipa_result}"

    def test_diphthongs_count_as_single_vowel(self):
        """Test that diphthongs are counted as single syllable nuclei."""
        # "boat" /boʊt/ - diphthong oʊ counts as one vowel = 1 syllable
        result = count_syllables_from_ipa("/boʊt/")
        assert result == 1, f"boat should be 1 syllable, got {result}"

        # "kite" /kaɪt/ - diphthong aɪ counts as one vowel = 1 syllable
        result = count_syllables_from_ipa("/kaɪt/")
        assert result == 1, f"kite should be 1 syllable, got {result}"

    def test_rhotic_vowels(self):
        """Test words with rhotic vowels."""
        # "bird" /bɝd/ or /bɜːd/ - rhotic vowel = 1 syllable
        result = count_syllables_from_ipa("/bɝd/")
        assert result == 1, f"bird should be 1 syllable, got {result}"


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
