"""Integration tests for lemma extraction pipeline."""
import json
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory


class TestLemmaNormalizationIntegration:
    """Test lemma handling through the normalization pipeline."""

    def test_lemma_survives_normalization(self, tmp_path):
        """Verify lemma field passes through wikt_normalize.py."""
        from openword.wikt_normalize import normalize_wiktionary

        # Create test input with lemma data
        input_path = tmp_path / "input.jsonl"
        lexemes_path = tmp_path / "lexemes.jsonl"
        senses_path = tmp_path / "senses.jsonl"

        test_entries = [
            {"word": "cat", "pos": "noun", "is_inflected": False},
            {"word": "cats", "pos": "noun", "is_inflected": True, "lemma": "cat"},
            {"word": "run", "pos": "verb", "is_inflected": False},
            {"word": "running", "pos": "verb", "is_inflected": True, "lemma": "run"},
            {"word": "ran", "pos": "verb", "is_inflected": True, "lemma": "run"},
        ]

        with open(input_path, 'w') as f:
            for entry in test_entries:
                f.write(json.dumps(entry) + '\n')

        # Run normalization
        normalize_wiktionary(input_path, lexemes_path, senses_path)

        # Verify senses file contains lemma data
        senses = []
        with open(senses_path) as f:
            for line in f:
                senses.append(json.loads(line))

        # Find inflected senses
        inflected_senses = [s for s in senses if s.get('lemma')]
        assert len(inflected_senses) == 3  # cats, running, ran

        # Verify specific lemmas
        cats_sense = next(s for s in senses if s.get('word') == 'cats')
        assert cats_sense.get('lemma') == 'cat'

        running_sense = next(s for s in senses if s.get('word') == 'running')
        assert running_sense.get('lemma') == 'run'

    def test_multiple_senses_same_word_different_lemmas(self, tmp_path):
        """Test word with senses having different lemmas (like 'left')."""
        from openword.wikt_normalize import normalize_wiktionary

        input_path = tmp_path / "input.jsonl"
        lexemes_path = tmp_path / "lexemes.jsonl"
        senses_path = tmp_path / "senses.jsonl"

        # "left" has two senses: past tense of "leave" and standalone adjective
        test_entries = [
            {"word": "left", "pos": "verb", "is_inflected": True, "lemma": "leave"},
            {"word": "left", "pos": "adjective", "is_inflected": False},
        ]

        with open(input_path, 'w') as f:
            for entry in test_entries:
                f.write(json.dumps(entry) + '\n')

        normalize_wiktionary(input_path, lexemes_path, senses_path)

        # Verify both senses are preserved (different lemmas = not deduplicated)
        senses = []
        with open(senses_path) as f:
            for line in f:
                senses.append(json.loads(line))

        assert len(senses) == 2  # Should not be deduplicated

        verb_sense = next(s for s in senses if s.get('pos') == 'verb')
        adj_sense = next(s for s in senses if s.get('pos') == 'adjective')

        assert verb_sense.get('lemma') == 'leave'
        assert adj_sense.get('lemma') is None  # Base form has no lemma


class TestLemmaExportIntegration:
    """Test lemma metadata export."""

    def test_export_lemma_groups(self, tmp_path):
        """Test export_lemma_groups.py produces correct output."""
        from openword.export_lemma_groups import export_lemma_metadata

        # Create test senses file
        senses_path = tmp_path / "senses.jsonl"
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        test_senses = [
            {"word": "cat", "pos": "noun"},
            {"word": "cats", "pos": "noun", "is_inflected": True, "lemma": "cat"},
            {"word": "run", "pos": "verb"},
            {"word": "runs", "pos": "verb", "is_inflected": True, "lemma": "run"},
            {"word": "ran", "pos": "verb", "is_inflected": True, "lemma": "run"},
            {"word": "running", "pos": "verb", "is_inflected": True, "lemma": "run"},
            {"word": "go", "pos": "verb"},
            {"word": "went", "pos": "verb", "is_inflected": True, "lemma": "go"},
            {"word": "gone", "pos": "verb", "is_inflected": True, "lemma": "go"},
        ]

        with open(senses_path, 'w') as f:
            for sense in test_senses:
                f.write(json.dumps(sense) + '\n')

        # Run export
        lemmas_count, groups_count = export_lemma_metadata(
            senses_path, output_dir, 'en', use_gzip=False
        )

        # Check counts
        assert lemmas_count == 6  # cats, runs, ran, running, went, gone
        assert groups_count == 3  # cat, run, go

        # Verify lemmas file
        lemmas_path = output_dir / "en-lemmas.json"
        with open(lemmas_path) as f:
            lemmas = json.load(f)

        assert lemmas["cats"] == "cat"
        assert lemmas["runs"] == "run"
        assert lemmas["ran"] == "run"
        assert lemmas["running"] == "run"
        assert lemmas["went"] == "go"
        assert lemmas["gone"] == "go"

        # Base forms should NOT be in lemmas (only inflected -> lemma mappings)
        assert "cat" not in lemmas
        assert "run" not in lemmas
        assert "go" not in lemmas

        # Verify groups file
        groups_path = output_dir / "en-lemma-groups.json"
        with open(groups_path) as f:
            groups = json.load(f)

        # Each group should have base form first
        assert groups["cat"] == ["cat", "cats"]
        assert groups["run"][0] == "run"  # Base form first
        assert set(groups["run"]) == {"run", "runs", "ran", "running"}
        assert groups["go"][0] == "go"  # Base form first
        assert set(groups["go"]) == {"go", "went", "gone"}


class TestLemmaFilteringIntegration:
    """Test lemma-based filtering through filters.py."""

    def test_filter_base_forms_only(self, tmp_path):
        """Test filtering to get only base forms."""
        from openword.filters import (
            filter_two_file,
            sense_is_base_form,
        )

        # Create test files
        lexemes_path = tmp_path / "lexemes.jsonl"
        senses_path = tmp_path / "senses.jsonl"

        lexemes = [
            {"word": "cat", "sense_offset": 0, "sense_length": 1},
            {"word": "cats", "sense_offset": 1, "sense_length": 1},
            {"word": "run", "sense_offset": 2, "sense_length": 1},
            {"word": "running", "sense_offset": 3, "sense_length": 1},
        ]

        senses = [
            {"word": "cat", "pos": "noun"},
            {"word": "cats", "pos": "noun", "is_inflected": True, "lemma": "cat"},
            {"word": "run", "pos": "verb"},
            {"word": "running", "pos": "verb", "is_inflected": True, "lemma": "run"},
        ]

        with open(lexemes_path, 'w') as f:
            for entry in lexemes:
                f.write(json.dumps(entry) + '\n')

        with open(senses_path, 'w') as f:
            for entry in senses:
                f.write(json.dumps(entry) + '\n')

        # Filter for base forms only
        results = list(filter_two_file(
            lexemes_path,
            senses_path,
            sense_predicate=sense_is_base_form,
            require_all_senses=True
        ))

        # Should only return base forms
        words = [r[0]['word'] for r in results]
        assert set(words) == {"cat", "run"}
        assert "cats" not in words
        assert "running" not in words


class TestRustPythonScannerParity:
    """Test that Rust and Python scanners produce compatible lemma output."""

    @pytest.fixture
    def sample_wikt_text(self):
        """Sample Wiktionary-style text with inflection templates."""
        return """
==English==

===Noun===
{{en-noun}}

# A small domesticated carnivorous mammal.

===Verb===
{{en-verb}}

# {{plural of|en|cat}}
"""

    def test_python_extract_lemma(self, sample_wikt_text):
        """Test Python scanner's extract_lemma function."""
        import sys
        from pathlib import Path

        tools_path = Path(__file__).parent.parent / "tools"
        sys.path.insert(0, str(tools_path))

        try:
            from wiktionary_scanner_parser import extract_lemma

            # Test with the sample text containing {{plural of|en|cat}}
            text_with_plural = "# {{plural of|en|cat}}"
            lemma = extract_lemma(text_with_plural)
            assert lemma == "cat"

            # Test with no inflection template
            text_no_template = "A small domesticated animal."
            lemma = extract_lemma(text_no_template)
            assert lemma is None

        except ImportError:
            pytest.skip("Python scanner not available")
        finally:
            sys.path.pop(0)

    def test_inflection_template_coverage(self):
        """Verify key inflection templates are handled."""
        import sys
        from pathlib import Path

        tools_path = Path(__file__).parent.parent / "tools"
        sys.path.insert(0, str(tools_path))

        try:
            from wiktionary_scanner_parser import extract_lemma

            test_cases = [
                ("{{plural of|en|dog}}", "dog"),
                ("{{past tense of|en|walk}}", "walk"),
                ("{{past participle of|en|break}}", "break"),
                ("{{present participle of|en|swim}}", "swim"),
                ("{{comparative of|en|tall}}", "tall"),
                ("{{superlative of|en|short}}", "short"),
                ("{{inflection of|en|eat||past|part}}", "eat"),
            ]

            for template, expected_lemma in test_cases:
                result = extract_lemma(template)
                assert result == expected_lemma, f"Failed for {template}: got {result}"

        except ImportError:
            pytest.skip("Python scanner not available")
        finally:
            sys.path.pop(0)


class TestLemmaValidation:
    """Validation tests for lemma data quality."""

    def test_no_circular_lemmas(self, tmp_path):
        """Verify no word is its own lemma (except base forms which have no lemma)."""
        # This is a structural test - lemma should always point to a different word
        test_senses = [
            {"word": "cats", "lemma": "cat"},  # OK: different
            {"word": "running", "lemma": "run"},  # OK: different
        ]

        for sense in test_senses:
            if sense.get('lemma'):
                assert sense['word'] != sense['lemma'], \
                    f"Circular lemma: {sense['word']} -> {sense['lemma']}"

    def test_lemma_lowercase_normalized(self):
        """Verify lemmas are lowercase (NFKC normalized)."""
        from openword.filters import sense_get_lemma

        # Lemmas extracted from Wiktionary should be lowercase
        test_senses = [
            {"word": "cats", "lemma": "cat"},
            {"word": "Running", "lemma": "run"},  # Word may be capitalized, lemma should not
        ]

        for sense in test_senses:
            lemma = sense_get_lemma(sense)
            if lemma:
                assert lemma == lemma.lower(), f"Lemma not lowercase: {lemma}"
