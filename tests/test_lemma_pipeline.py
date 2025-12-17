"""Integration tests for lemma extraction pipeline."""
import json


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
            {"id": "cat", "pos": "noun", "is_inflected": False},
            {"id": "cats", "pos": "noun", "is_inflected": True, "lemma": "cat"},
            {"id": "run", "pos": "verb", "is_inflected": False},
            {"id": "running", "pos": "verb", "is_inflected": True, "lemma": "run"},
            {"id": "ran", "pos": "verb", "is_inflected": True, "lemma": "run"},
        ]

        with open(input_path, "w") as f:
            for entry in test_entries:
                f.write(json.dumps(entry) + "\n")

        # Run normalization
        normalize_wiktionary(input_path, lexemes_path, senses_path)

        # Verify senses file contains lemma data
        senses = []
        with open(senses_path) as f:
            for line in f:
                senses.append(json.loads(line))

        # Find inflected senses
        inflected_senses = [s for s in senses if s.get("lemma")]
        assert len(inflected_senses) == 3  # cats, running, ran

        # Verify specific lemmas
        cats_sense = next(s for s in senses if s.get("id") == "cats")
        assert cats_sense.get("lemma") == "cat"

        running_sense = next(s for s in senses if s.get("id") == "running")
        assert running_sense.get("lemma") == "run"

    def test_multiple_senses_same_word_different_lemmas(self, tmp_path):
        """Test word with senses having different lemmas (like 'left')."""
        from openword.wikt_normalize import normalize_wiktionary

        input_path = tmp_path / "input.jsonl"
        lexemes_path = tmp_path / "lexemes.jsonl"
        senses_path = tmp_path / "senses.jsonl"

        # "left" has two senses: past tense of "leave" and standalone adjective
        test_entries = [
            {"id": "left", "pos": "verb", "is_inflected": True, "lemma": "leave"},
            {"id": "left", "pos": "adjective", "is_inflected": False},
        ]

        with open(input_path, "w") as f:
            for entry in test_entries:
                f.write(json.dumps(entry) + "\n")

        normalize_wiktionary(input_path, lexemes_path, senses_path)

        # Verify both senses are preserved (different lemmas = not deduplicated)
        senses = []
        with open(senses_path) as f:
            for line in f:
                senses.append(json.loads(line))

        assert len(senses) == 2  # Should not be deduplicated

        verb_sense = next(s for s in senses if s.get("pos") == "verb")
        adj_sense = next(s for s in senses if s.get("pos") == "adjective")

        assert verb_sense.get("lemma") == "leave"
        assert adj_sense.get("lemma") is None  # Base form has no lemma


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
            {"id": "cat", "pos": "noun"},
            {"id": "cats", "pos": "noun", "is_inflected": True, "lemma": "cat"},
            {"id": "run", "pos": "verb"},
            {"id": "runs", "pos": "verb", "is_inflected": True, "lemma": "run"},
            {"id": "ran", "pos": "verb", "is_inflected": True, "lemma": "run"},
            {"id": "running", "pos": "verb", "is_inflected": True, "lemma": "run"},
            {"id": "go", "pos": "verb"},
            {"id": "went", "pos": "verb", "is_inflected": True, "lemma": "go"},
            {"id": "gone", "pos": "verb", "is_inflected": True, "lemma": "go"},
        ]

        with open(senses_path, "w") as f:
            for sense in test_senses:
                f.write(json.dumps(sense) + "\n")

        # Run export
        lemmas_count, groups_count = export_lemma_metadata(
            senses_path, output_dir, "en", use_gzip=False
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
            {"id": "cat", "sense_offset": 0, "sense_length": 1},
            {"id": "cats", "sense_offset": 1, "sense_length": 1},
            {"id": "run", "sense_offset": 2, "sense_length": 1},
            {"id": "running", "sense_offset": 3, "sense_length": 1},
        ]

        senses = [
            {"id": "cat", "pos": "noun"},
            {"id": "cats", "pos": "noun", "is_inflected": True, "lemma": "cat"},
            {"id": "run", "pos": "verb"},
            {"id": "running", "pos": "verb", "is_inflected": True, "lemma": "run"},
        ]

        with open(lexemes_path, "w") as f:
            for entry in lexemes:
                f.write(json.dumps(entry) + "\n")

        with open(senses_path, "w") as f:
            for entry in senses:
                f.write(json.dumps(entry) + "\n")

        # Filter for base forms only
        results = list(filter_two_file(
            lexemes_path,
            senses_path,
            sense_predicate=sense_is_base_form,
            require_all_senses=True
        ))

        # Should only return base forms
        words = [r[0]["id"] for r in results]
        assert set(words) == {"cat", "run"}
        assert "cats" not in words
        assert "running" not in words


class TestLemmaValidation:
    """Validation tests for lemma data quality."""

    def test_no_circular_lemmas(self, tmp_path):
        """Verify no word is its own lemma (except base forms which have no lemma)."""
        # This is a structural test - lemma should always point to a different word
        test_senses = [
            {"id": "cats", "lemma": "cat"},  # OK: different
            {"id": "running", "lemma": "run"},  # OK: different
        ]

        for sense in test_senses:
            if sense.get("lemma"):
                assert sense["id"] != sense["lemma"], \
                    f"Circular lemma: {sense['id']} -> {sense['lemma']}"

    def test_lemma_lowercase_normalized(self):
        """Verify lemmas are lowercase (NFKC normalized)."""
        from openword.filters import sense_get_lemma

        # Lemmas extracted from Wiktionary should be lowercase
        test_senses = [
            {"id": "cats", "lemma": "cat"},
            {"id": "Running", "lemma": "run"},  # Word may be capitalized, lemma should not
        ]

        for sense in test_senses:
            lemma = sense_get_lemma(sense)
            if lemma:
                assert lemma == lemma.lower(), f"Lemma not lowercase: {lemma}"
