"""Unit tests for the Wiktionary category computation module.

These tests serve as living documentation of assumptions about Wiktionary's
category generation logic. Each test class documents a specific category type
and the rules that govern it.

The category logic is ported from Wiktionary's Lua modules:
- Module:en-headword (English-specific)
- Module:headword (base category generation)
- Module:labels/data (label → category mappings)

References:
- https://en.wiktionary.org/wiki/Module:en-headword
- https://en.wiktionary.org/wiki/Module:headword
"""

import pytest
import sys
from pathlib import Path

# Add tools directory to path
tools_path = Path(__file__).parent.parent / "tools"
sys.path.insert(0, str(tools_path))

from wiktionary_categories import (
    CategoryBuilder,
    ComparabilityInfo,
    detect_phrasal_verb,
    is_multiword_term,
    get_pos_category,
    get_comparability_category,
    parse_adj_adv_comparability,
    get_regional_category,
    get_regional_categories,
    PHRASAL_ADVERBS,
    PHRASAL_PLACEHOLDERS,
    REGIONAL_LABELS,
)


# ─────────────────────────────────────────────────────────────────────────────
# Phrasal Verb Detection Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPhrasalVerbDetection:
    """
    Tests for phrasal verb detection, ported from Module:en-headword.

    A phrasal verb is a multi-word verb where the base verb is followed by
    one or more particles (adverbs) from a specific list. Placeholder words
    like "it", "one", "oneself" may appear but don't make a verb phrasal.

    The detection requires:
    1. POS must be "verb"
    2. Word must contain spaces
    3. All words after the base must be either phrasal adverbs or placeholders
    4. At least one phrasal adverb must be present

    Examples from Wiktionary:
    - "give up" → phrasal verb
    - "freak out" → phrasal verb
    - "put up with" → phrasal verb (multiple adverbs)
    - "can it" → NOT phrasal ("it" is placeholder only)
    """

    def test_simple_phrasal_verb(self):
        """Basic phrasal verb: base verb + single adverb."""
        is_phrasal, adverbs = detect_phrasal_verb("give up", "verb")
        assert is_phrasal is True
        assert adverbs == ["up"]

    def test_phrasal_verb_with_out(self):
        """Phrasal verb with 'out' particle."""
        is_phrasal, adverbs = detect_phrasal_verb("freak out", "verb")
        assert is_phrasal is True
        assert adverbs == ["out"]

    def test_phrasal_verb_multiple_adverbs(self):
        """Phrasal verb with multiple adverbs: put up with."""
        is_phrasal, adverbs = detect_phrasal_verb("put up with", "verb")
        assert is_phrasal is True
        assert adverbs == ["up", "with"]

    def test_phrasal_verb_with_placeholder(self):
        """Phrasal verb containing placeholder word 'it'."""
        # "psych oneself up" - has placeholder "oneself" and adverb "up"
        is_phrasal, adverbs = detect_phrasal_verb("psych oneself up", "verb")
        assert is_phrasal is True
        assert adverbs == ["up"]

    def test_placeholder_only_not_phrasal(self):
        """Word with only placeholder is NOT phrasal."""
        # "can it" has "it" which is placeholder but no adverb
        is_phrasal, adverbs = detect_phrasal_verb("can it", "verb")
        assert is_phrasal is False
        assert adverbs == []

    def test_single_word_verb_not_phrasal(self):
        """Single-word verb is never phrasal."""
        is_phrasal, adverbs = detect_phrasal_verb("run", "verb")
        assert is_phrasal is False
        assert adverbs == []

    def test_non_verb_pos_not_phrasal(self):
        """Non-verb POS is never detected as phrasal."""
        # "give up" as a noun should not be phrasal
        is_phrasal, adverbs = detect_phrasal_verb("give up", "noun")
        assert is_phrasal is False
        assert adverbs == []

    def test_unknown_word_breaks_pattern(self):
        """Unknown word in the pattern breaks phrasal detection."""
        # "run quickly away" - "quickly" is not in phrasal adverbs or placeholders
        is_phrasal, adverbs = detect_phrasal_verb("run quickly away", "verb")
        assert is_phrasal is False
        assert adverbs == []

    def test_forward_not_in_phrasal_adverbs(self):
        """'forward' is NOT in Wiktionary's phrasal adverb list.

        This documents an important assumption: Wiktionary's list is curated
        to only include common phrasal particles. Words like 'forward', 'low',
        'adrift' are explicitly excluded.

        "look forward to" is detected by Wiktionary via a different mechanism
        (direct category tagging in the entry template).
        """
        is_phrasal, adverbs = detect_phrasal_verb("look forward to", "verb")
        # "forward" is NOT in the adverb list, so this breaks the pattern
        assert is_phrasal is False

    def test_all_common_phrasal_patterns(self):
        """Common phrasal verb patterns should all be detected."""
        common_phrasal_verbs = [
            ("turn on", ["on"]),
            ("turn off", ["off"]),
            ("pick up", ["up"]),
            ("put down", ["down"]),
            ("come back", ["back"]),
            ("go away", ["away"]),
            ("get out", ["out"]),
            ("take over", ["over"]),
            ("break down", ["down"]),
            ("bring up", ["up"]),
        ]
        for word, expected_adverbs in common_phrasal_verbs:
            is_phrasal, adverbs = detect_phrasal_verb(word, "verb")
            assert is_phrasal is True, f"{word} should be phrasal"
            assert adverbs == expected_adverbs, f"{word} should have adverbs {expected_adverbs}"


class TestPhrasalAdverbList:
    """
    Tests documenting the canonical phrasal adverb list from Module:en-headword.

    This list is curated by Wiktionary editors and should only contain common
    phrasal particles. The exact list was extracted from:
    https://en.wiktionary.org/wiki/Module:en-headword

    These tests serve as documentation of what IS and IS NOT included.
    """

    def test_common_directional_particles_included(self):
        """Common directional particles are in the list."""
        directional = {"up", "down", "in", "out", "over", "under", "through", "around"}
        assert directional.issubset(PHRASAL_ADVERBS)

    def test_common_prepositional_particles_included(self):
        """Common prepositional particles are in the list."""
        prepositional = {"on", "off", "at", "for", "from", "to", "with", "without"}
        assert prepositional.issubset(PHRASAL_ADVERBS)

    def test_positional_particles_included(self):
        """Positional particles are in the list."""
        positional = {"back", "away", "aside", "apart", "together", "forth"}
        assert positional.issubset(PHRASAL_ADVERBS)

    def test_forward_not_included(self):
        """'forward' is explicitly NOT in the list (per Lua comments)."""
        assert "forward" not in PHRASAL_ADVERBS

    def test_low_not_included(self):
        """'low' is explicitly NOT in the list (per Lua comments)."""
        assert "low" not in PHRASAL_ADVERBS

    def test_adrift_not_included(self):
        """'adrift' is explicitly NOT in the list (per Lua comments)."""
        assert "adrift" not in PHRASAL_ADVERBS

    def test_placeholder_list(self):
        """Document the placeholder word list."""
        assert PHRASAL_PLACEHOLDERS == {"it", "one", "oneself"}


# ─────────────────────────────────────────────────────────────────────────────
# Multiword Term Detection Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestMultiwordTermDetection:
    """
    Tests for multiword term detection from Module:headword.

    Any entry whose headword contains a space is considered a multiword term.
    """

    def test_two_word_term(self):
        """Two-word term is multiword."""
        assert is_multiword_term("ice cream") is True

    def test_three_word_term(self):
        """Three-word term is multiword."""
        assert is_multiword_term("United States of America") is True

    def test_single_word_not_multiword(self):
        """Single word is not multiword."""
        assert is_multiword_term("cat") is False

    def test_hyphenated_not_multiword(self):
        """Hyphenated word (no spaces) is not multiword."""
        assert is_multiword_term("ice-cream") is False


# ─────────────────────────────────────────────────────────────────────────────
# POS Category Generation Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPOSCategoryGeneration:
    """
    Tests for POS → category name mapping from Module:headword.

    The pattern is: "English " + plural form of POS
    Special case: "proper" → "proper nouns" (not "propers")
    """

    def test_noun_category(self):
        """Noun → 'nouns'."""
        assert get_pos_category("noun") == "nouns"

    def test_verb_category(self):
        """Verb → 'verbs'."""
        assert get_pos_category("verb") == "verbs"

    def test_adjective_category(self):
        """Adjective → 'adjectives'."""
        assert get_pos_category("adjective") == "adjectives"

    def test_proper_noun_special_case(self):
        """Proper noun uses 'proper nouns' not 'propers'."""
        assert get_pos_category("proper") == "proper nouns"

    def test_unknown_pos_returns_none(self):
        """Unknown POS returns None."""
        assert get_pos_category("unknown") is None
        assert get_pos_category("foo") is None


# ─────────────────────────────────────────────────────────────────────────────
# Category Builder Integration Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCategoryBuilder:
    """
    Integration tests for CategoryBuilder combining multiple category types.

    These tests verify that the builder correctly accumulates categories
    from all applicable rules.
    """

    def test_simple_noun(self):
        """Simple noun gets only POS category."""
        categories = CategoryBuilder.compute_all("cat", "noun")
        assert categories == ["English nouns"]

    def test_multiword_noun(self):
        """Multiword noun gets POS + multiword categories."""
        categories = CategoryBuilder.compute_all("ice cream", "noun")
        assert "English nouns" in categories
        assert "English multiword terms" in categories
        assert len(categories) == 2

    def test_simple_verb(self):
        """Simple verb gets only POS category."""
        categories = CategoryBuilder.compute_all("run", "verb")
        assert categories == ["English verbs"]

    def test_phrasal_verb(self):
        """Phrasal verb gets POS + multiword + phrasal categories."""
        categories = CategoryBuilder.compute_all("give up", "verb")
        assert "English verbs" in categories
        assert "English multiword terms" in categories
        assert "English phrasal verbs" in categories
        assert 'English phrasal verbs formed with "up"' in categories
        assert len(categories) == 4

    def test_phrasal_verb_multiple_adverbs(self):
        """Phrasal verb with multiple adverbs gets category for each."""
        categories = CategoryBuilder.compute_all("put up with", "verb")
        assert 'English phrasal verbs formed with "up"' in categories
        assert 'English phrasal verbs formed with "with"' in categories

    def test_proper_noun(self):
        """Proper noun gets correct category name."""
        categories = CategoryBuilder.compute_all("London", "proper")
        assert categories == ["English proper nouns"]

    def test_multiword_proper_noun(self):
        """Multiword proper noun gets both categories."""
        categories = CategoryBuilder.compute_all("United States", "proper")
        assert "English proper nouns" in categories
        assert "English multiword terms" in categories

    def test_builder_pattern_fluent_api(self):
        """Builder supports fluent API for manual category computation."""
        builder = CategoryBuilder(word="give up", pos="verb")
        result = (
            builder
            .add_pos_category()
            .add_multiword_category()
            .add_phrasal_verb_categories()
            .build()
        )
        assert "English verbs" in result
        assert "English phrasal verbs" in result


# ─────────────────────────────────────────────────────────────────────────────
# Real World Examples from Wiktionary
# ─────────────────────────────────────────────────────────────────────────────

class TestRealWorldExamples:
    """
    Tests based on actual Wiktionary entries.

    These serve as regression tests and documentation of expected behavior
    for real dictionary entries.
    """

    def test_give_up_verb(self):
        """'give up' - common phrasal verb.

        Wiktionary page: https://en.wiktionary.org/wiki/give_up
        Expected categories: English verbs, English phrasal verbs,
                            English phrasal verbs formed with "up"
        """
        categories = CategoryBuilder.compute_all("give up", "verb")
        assert "English verbs" in categories
        assert "English phrasal verbs" in categories
        assert 'English phrasal verbs formed with "up"' in categories

    def test_break_down_verb(self):
        """'break down' - phrasal verb with 'down'.

        Wiktionary page: https://en.wiktionary.org/wiki/break_down
        """
        categories = CategoryBuilder.compute_all("break down", "verb")
        assert "English phrasal verbs" in categories
        assert 'English phrasal verbs formed with "down"' in categories

    def test_freak_out_verb(self):
        """'freak out' - phrasal verb with 'out'.

        Wiktionary page: https://en.wiktionary.org/wiki/freak_out
        """
        categories = CategoryBuilder.compute_all("freak out", "verb")
        assert "English phrasal verbs" in categories
        assert 'English phrasal verbs formed with "out"' in categories

    def test_ice_cream_noun(self):
        """'ice cream' - compound noun.

        Wiktionary page: https://en.wiktionary.org/wiki/ice_cream
        Expected categories: English nouns, English multiword terms
        """
        categories = CategoryBuilder.compute_all("ice cream", "noun")
        assert categories == ["English nouns", "English multiword terms"]

    def test_run_simple_verb(self):
        """'run' - simple verb, not phrasal.

        Wiktionary page: https://en.wiktionary.org/wiki/run
        """
        categories = CategoryBuilder.compute_all("run", "verb")
        assert categories == ["English verbs"]
        assert "English phrasal verbs" not in categories


# ─────────────────────────────────────────────────────────────────────────────
# Label → Category Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestLabelCategoryMappings:
    """
    Tests for label → category mappings from Module:labels/data.

    Labels in Wiktionary are grammatical annotations added via {{lb|en|...}}
    templates. Many labels map to categories, e.g.:
    - "transitive" → "English transitive verbs"
    - "countable" → "English countable nouns"

    These mappings are ported from:
    https://en.wiktionary.org/wiki/Module:labels/data
    """

    def test_transitive_verb(self):
        """'transitive' label adds transitive verbs category.

        This is the most common grammatical label (~17,759 occurrences in 200k sample).
        """
        categories = CategoryBuilder.compute_all("eat", "verb", labels=["transitive"])
        assert "English verbs" in categories
        assert "English transitive verbs" in categories

    def test_intransitive_verb(self):
        """'intransitive' label adds intransitive verbs category."""
        categories = CategoryBuilder.compute_all("sleep", "verb", labels=["intransitive"])
        assert "English intransitive verbs" in categories

    def test_ambitransitive_verb(self):
        """'ambitransitive' label adds BOTH transitive AND intransitive categories.

        From Module:labels/data:
            labels["ambitransitive"] = { pos_categories = {"transitive verbs", "intransitive verbs"} }

        This is correct behavior - ambitransitive verbs can be used both ways.
        """
        categories = CategoryBuilder.compute_all("run", "verb", labels=["ambitransitive"])
        assert "English transitive verbs" in categories
        assert "English intransitive verbs" in categories

    def test_countable_noun(self):
        """'countable' label adds countable nouns category."""
        categories = CategoryBuilder.compute_all("cat", "noun", labels=["countable"])
        assert "English countable nouns" in categories

    def test_uncountable_noun(self):
        """'uncountable' label adds uncountable nouns category."""
        categories = CategoryBuilder.compute_all("information", "noun", labels=["uncountable"])
        assert "English uncountable nouns" in categories

    def test_uncountable_alias(self):
        """'not countable' is an alias for 'uncountable'."""
        categories = CategoryBuilder.compute_all("information", "noun", labels=["not countable"])
        assert "English uncountable nouns" in categories

    def test_plural_only_noun(self):
        """'plural only' label adds pluralia tantum category."""
        categories = CategoryBuilder.compute_all("scissors", "noun", labels=["plural only"])
        assert "English pluralia tantum" in categories

    def test_plural_only_alias(self):
        """'plurale tantum' is an alias for 'plural only'."""
        categories = CategoryBuilder.compute_all("pants", "noun", labels=["plurale tantum"])
        assert "English pluralia tantum" in categories

    def test_auxiliary_verb(self):
        """'auxiliary' label adds auxiliary verbs category."""
        categories = CategoryBuilder.compute_all("have", "verb", labels=["auxiliary"])
        assert "English auxiliary verbs" in categories

    def test_modal_verb(self):
        """'modal' label adds modal verbs category."""
        categories = CategoryBuilder.compute_all("can", "verb", labels=["modal"])
        assert "English modal verbs" in categories

    def test_collective_noun(self):
        """'collective' label adds collective nouns category."""
        categories = CategoryBuilder.compute_all("flock", "noun", labels=["collective"])
        assert "English collective nouns" in categories

    def test_acronym(self):
        """'acronym' label adds acronyms category."""
        categories = CategoryBuilder.compute_all("NASA", "noun", labels=["acronym"])
        assert "English acronyms" in categories

    def test_initialism(self):
        """'initialism' label adds initialisms category."""
        categories = CategoryBuilder.compute_all("FBI", "noun", labels=["initialism"])
        assert "English initialisms" in categories

    def test_abbreviation(self):
        """'abbreviation' label adds abbreviations category."""
        categories = CategoryBuilder.compute_all("etc", "noun", labels=["abbreviation"])
        assert "English abbreviations" in categories


class TestLabelWithNoCategory:
    """
    Tests verifying that labels without pos_categories don't add categories.

    Many labels in Wiktionary are display-only (like "slang", "informal")
    and don't map to categories. These should return empty lists.
    """

    def test_slang_no_category(self):
        """'slang' has no pos_categories mapping."""
        from wiktionary_categories import get_categories_for_label
        assert get_categories_for_label("slang") == []

    def test_informal_no_category(self):
        """'informal' has no pos_categories mapping."""
        from wiktionary_categories import get_categories_for_label
        assert get_categories_for_label("informal") == []

    def test_figurative_no_category(self):
        """'figurative' has no pos_categories mapping."""
        from wiktionary_categories import get_categories_for_label
        assert get_categories_for_label("figurative") == []

    def test_unknown_label_no_category(self):
        """Unknown labels return empty list."""
        from wiktionary_categories import get_categories_for_label
        assert get_categories_for_label("nonexistent_label") == []


class TestMultipleLabels:
    """Tests for entries with multiple labels."""

    def test_multiple_verb_labels(self):
        """Verb with multiple labels gets all applicable categories."""
        categories = CategoryBuilder.compute_all(
            "be", "verb", labels=["auxiliary", "copulative", "intransitive"]
        )
        assert "English auxiliary verbs" in categories
        assert "English copulative verbs" in categories
        assert "English intransitive verbs" in categories

    def test_mixed_labels_some_with_categories(self):
        """Only labels with pos_categories mappings add categories."""
        categories = CategoryBuilder.compute_all(
            "eat", "verb", labels=["transitive", "informal", "slang"]
        )
        # Only "transitive" has a category mapping
        assert "English transitive verbs" in categories
        # "informal" and "slang" should not add categories
        assert len([c for c in categories if "informal" in c.lower()]) == 0
        assert len([c for c in categories if "slang" in c.lower()]) == 0

    def test_deduplicated_categories(self):
        """Duplicate categories from multiple labels are deduplicated."""
        # Both "ambitransitive" and "transitive" would add "transitive verbs"
        categories = CategoryBuilder.compute_all(
            "run", "verb", labels=["ambitransitive", "transitive"]
        )
        # Should only have one "English transitive verbs"
        assert categories.count("English transitive verbs") == 1


# ─────────────────────────────────────────────────────────────────────────────
# Comparability Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestComparabilityParsing:
    """
    Tests for parsing {{en-adj}} and {{en-adv}} template parameters.

    From Module:en-headword, comparability is determined by:
    - "-" as first param (alone) → uncomparable
    - componly=1 → comparative-only
    - suponly=1 → superlative-only

    Corpus analysis (200k sample):
    - Uncomparable: 75.6% of adjectives, 86.0% of adverbs
    - Comparative-only: 4 adjectives (rare)
    - Superlative-only: 0 found (extremely rare)
    """

    def test_uncomparable_dash_only(self):
        """Single '-' param means uncomparable."""
        info = parse_adj_adv_comparability("-")
        assert info.uncomparable is True
        assert info.componly is False
        assert info.suponly is False

    def test_dash_with_other_params_not_uncomparable(self):
        """'-' with other comparatives is NOT uncomparable (has alternates)."""
        info = parse_adj_adv_comparability("-|more")
        assert info.uncomparable is False

    def test_componly_parameter(self):
        """componly=1 means comparative-only."""
        info = parse_adj_adv_comparability("componly=1")
        assert info.componly is True
        assert info.uncomparable is False
        assert info.suponly is False

    def test_suponly_parameter(self):
        """suponly=1 means superlative-only."""
        info = parse_adj_adv_comparability("suponly=1")
        assert info.suponly is True
        assert info.uncomparable is False
        assert info.componly is False

    def test_regular_comparable_er(self):
        """Regular -er comparative is just comparable, no special flags."""
        info = parse_adj_adv_comparability("er")
        assert info.uncomparable is False
        assert info.componly is False
        assert info.suponly is False

    def test_regular_comparable_more(self):
        """Regular 'more' comparative is just comparable."""
        info = parse_adj_adv_comparability("more")
        assert info.uncomparable is False
        assert info.componly is False
        assert info.suponly is False

    def test_empty_params(self):
        """Empty params means default comparable."""
        info = parse_adj_adv_comparability("")
        assert info.uncomparable is False
        assert info.componly is False
        assert info.suponly is False

    def test_complex_template_params(self):
        """Complex template with head= and other params."""
        info = parse_adj_adv_comparability("head=[[more]] [[than]]|componly=1")
        assert info.componly is True
        assert info.uncomparable is False


class TestComparabilityCategoryGeneration:
    """
    Tests for generating comparability categories.

    Categories from Module:en-headword:
    - "English uncomparable adjectives"
    - "English uncomparable adverbs"
    - "English comparative-only adjectives"
    - "English comparative-only adverbs"
    - "English superlative-only adjectives"
    - "English superlative-only adverbs"
    """

    def test_uncomparable_adjective_category(self):
        """Uncomparable adjective gets 'uncomparable adjectives' category."""
        info = ComparabilityInfo(uncomparable=True)
        cat = get_comparability_category("adjective", info)
        assert cat == "uncomparable adjectives"

    def test_uncomparable_adverb_category(self):
        """Uncomparable adverb gets 'uncomparable adverbs' category."""
        info = ComparabilityInfo(uncomparable=True)
        cat = get_comparability_category("adverb", info)
        assert cat == "uncomparable adverbs"

    def test_comparative_only_adjective_category(self):
        """Comparative-only adjective gets 'comparative-only adjectives' category."""
        info = ComparabilityInfo(componly=True)
        cat = get_comparability_category("adjective", info)
        assert cat == "comparative-only adjectives"

    def test_comparative_only_adverb_category(self):
        """Comparative-only adverb gets 'comparative-only adverbs' category."""
        info = ComparabilityInfo(componly=True)
        cat = get_comparability_category("adverb", info)
        assert cat == "comparative-only adverbs"

    def test_superlative_only_adjective_category(self):
        """Superlative-only adjective gets 'superlative-only adjectives' category."""
        info = ComparabilityInfo(suponly=True)
        cat = get_comparability_category("adjective", info)
        assert cat == "superlative-only adjectives"

    def test_noun_no_comparability_category(self):
        """Nouns don't get comparability categories."""
        info = ComparabilityInfo(uncomparable=True)
        cat = get_comparability_category("noun", info)
        assert cat is None

    def test_verb_no_comparability_category(self):
        """Verbs don't get comparability categories."""
        info = ComparabilityInfo(uncomparable=True)
        cat = get_comparability_category("verb", info)
        assert cat is None

    def test_no_flags_no_category(self):
        """Default comparable has no special category."""
        info = ComparabilityInfo()
        cat = get_comparability_category("adjective", info)
        assert cat is None


class TestComparabilityIntegration:
    """
    Integration tests for comparability with CategoryBuilder.

    Tests real-world examples from corpus analysis:
    - 'cat' → {{en-adj|-}} → "English uncomparable adjectives"
    - 'larger-than-life' → {{en-adj|componly=1}} → "English comparative-only adjectives"
    """

    def test_uncomparable_adjective_via_builder(self):
        """Uncomparable adjective via CategoryBuilder.compute_all."""
        categories = CategoryBuilder.compute_all(
            "alphabetical", "adjective",
            comparability=ComparabilityInfo(uncomparable=True)
        )
        assert "English adjectives" in categories
        assert "English uncomparable adjectives" in categories

    def test_uncomparable_adverb_via_builder(self):
        """Uncomparable adverb via CategoryBuilder.compute_all."""
        categories = CategoryBuilder.compute_all(
            "gratis", "adverb",
            comparability=ComparabilityInfo(uncomparable=True)
        )
        assert "English adverbs" in categories
        assert "English uncomparable adverbs" in categories

    def test_comparative_only_adjective_via_builder(self):
        """Comparative-only adjective like 'larger-than-life'."""
        categories = CategoryBuilder.compute_all(
            "larger-than-life", "adjective",
            comparability=ComparabilityInfo(componly=True)
        )
        assert "English adjectives" in categories
        assert "English comparative-only adjectives" in categories

    def test_regular_adjective_no_extra_category(self):
        """Regular comparable adjective has no comparability category."""
        categories = CategoryBuilder.compute_all(
            "happy", "adjective",
            comparability=ComparabilityInfo()
        )
        assert "English adjectives" in categories
        assert "English uncomparable adjectives" not in categories
        assert "English comparative-only adjectives" not in categories

    def test_adjective_without_comparability_info(self):
        """Adjective without comparability info provided."""
        categories = CategoryBuilder.compute_all("tall", "adjective")
        assert "English adjectives" in categories
        assert "English uncomparable adjectives" not in categories

    def test_uncomparable_adjective_with_labels(self):
        """Uncomparable adjective can have labels too."""
        categories = CategoryBuilder.compute_all(
            "portmanteau", "adjective",
            labels=["attributive"],
            comparability=ComparabilityInfo(uncomparable=True)
        )
        assert "English adjectives" in categories
        assert "English uncomparable adjectives" in categories


class TestComparabilityRealWorldExamples:
    """
    Tests based on actual Wiktionary entries from corpus analysis.

    Examples found in 200k sample scan:
    - Uncomparable: 'cat', 'gratis', 'alphabetical', 'raven', 'portmanteau'
    - Comparative-only: 'faster-than-light', 'larger-than-life', 'FTL'
    """

    def test_portmanteau_uncomparable(self):
        """'portmanteau' as adjective is uncomparable ({{en-adj|-}})."""
        info = parse_adj_adv_comparability("-")
        categories = CategoryBuilder.compute_all(
            "portmanteau", "adjective", comparability=info
        )
        assert "English uncomparable adjectives" in categories

    def test_gratis_adverb_uncomparable(self):
        """'gratis' as adverb is uncomparable."""
        info = parse_adj_adv_comparability("-")
        categories = CategoryBuilder.compute_all(
            "gratis", "adverb", comparability=info
        )
        assert "English uncomparable adverbs" in categories

    def test_larger_than_life_comparative_only(self):
        """'larger-than-life' is comparative-only ({{en-adj|componly=1}})."""
        info = parse_adj_adv_comparability("componly=1")
        categories = CategoryBuilder.compute_all(
            "larger-than-life", "adjective", comparability=info
        )
        assert "English comparative-only adjectives" in categories

    def test_ftl_comparative_only(self):
        """'FTL' (faster-than-light) is comparative-only."""
        info = parse_adj_adv_comparability("componly=1")
        categories = CategoryBuilder.compute_all(
            "FTL", "adjective", comparability=info
        )
        assert "English comparative-only adjectives" in categories


# ─────────────────────────────────────────────────────────────────────────────
# Regional Dialect Category Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestRegionalCategoryMappings:
    """
    Tests for regional dialect category mappings from Module:labels/data/lang/en.

    Regional labels in Wiktionary indicate dialect/variety usage:
    - "US" → "American English"
    - "UK" / "British" → "British English"
    - "Australia" → "Australian English"

    Corpus analysis (200k sample):
    - US: 4,529    UK: 3,347    British: 1,484    Australia: 1,273
    - Scotland: 1,105    Ireland: 815    Canada: 708
    """

    def test_us_label(self):
        """'US' maps to 'American English'."""
        assert get_regional_category("US") == "American English"

    def test_us_aliases(self):
        """US aliases all map to 'American English'."""
        aliases = ["U.S.", "USA", "America", "American", "American English"]
        for alias in aliases:
            assert get_regional_category(alias) == "American English"

    def test_uk_label(self):
        """'UK' maps to 'British English'."""
        assert get_regional_category("UK") == "British English"

    def test_british_label(self):
        """'British' is alias for UK, maps to 'British English'."""
        assert get_regional_category("British") == "British English"

    def test_australia_label(self):
        """'Australia' maps to 'Australian English'."""
        assert get_regional_category("Australia") == "Australian English"

    def test_australia_aliases(self):
        """Australia aliases all map to 'Australian English'."""
        aliases = ["Australian", "AU", "AuE", "Aus", "AusE"]
        for alias in aliases:
            assert get_regional_category(alias) == "Australian English"

    def test_canada_label(self):
        """'Canada' maps to 'Canadian English'."""
        assert get_regional_category("Canada") == "Canadian English"

    def test_canada_aliases(self):
        """Canada aliases all map to 'Canadian English'."""
        aliases = ["Canadian", "CA", "CanE"]
        for alias in aliases:
            assert get_regional_category(alias) == "Canadian English"

    def test_ireland_label(self):
        """'Ireland' maps to 'Irish English'."""
        assert get_regional_category("Ireland") == "Irish English"

    def test_irish_alias(self):
        """'Irish' is alias for Ireland."""
        assert get_regional_category("Irish") == "Irish English"

    def test_scotland_label(self):
        """'Scotland' maps to 'Scottish English'."""
        assert get_regional_category("Scotland") == "Scottish English"

    def test_new_zealand_label(self):
        """'New Zealand' maps to 'New Zealand English'."""
        assert get_regional_category("New Zealand") == "New Zealand English"

    def test_south_africa_label(self):
        """'South Africa' maps to 'South African English'."""
        assert get_regional_category("South Africa") == "South African English"

    def test_india_label(self):
        """'India' maps to 'Indian English'."""
        assert get_regional_category("India") == "Indian English"

    def test_philippines_label(self):
        """'Philippines' maps to 'Philippine English'."""
        assert get_regional_category("Philippines") == "Philippine English"

    def test_singapore_label(self):
        """'Singapore' maps to 'Singapore English'."""
        assert get_regional_category("Singapore") == "Singapore English"

    def test_non_regional_label_returns_none(self):
        """Non-regional labels return None."""
        assert get_regional_category("slang") is None
        assert get_regional_category("informal") is None
        assert get_regional_category("transitive") is None

    def test_case_insensitive(self):
        """Regional label lookup is case-insensitive."""
        assert get_regional_category("us") == "American English"
        assert get_regional_category("US") == "American English"
        assert get_regional_category("British") == "British English"
        assert get_regional_category("BRITISH") == "British English"


class TestRegionalCategoryMultiple:
    """Tests for getting regional categories from multiple labels."""

    def test_single_regional_label(self):
        """Single regional label returns single category."""
        cats = get_regional_categories(["US"])
        assert cats == ["American English"]

    def test_multiple_regional_labels(self):
        """Multiple regional labels return multiple categories."""
        cats = get_regional_categories(["US", "UK"])
        assert "American English" in cats
        assert "British English" in cats
        assert len(cats) == 2

    def test_mixed_labels(self):
        """Only regional labels return categories."""
        cats = get_regional_categories(["US", "informal", "slang"])
        assert cats == ["American English"]

    def test_deduplicated(self):
        """Duplicate regional labels are deduplicated."""
        cats = get_regional_categories(["US", "American", "USA"])
        assert cats == ["American English"]

    def test_empty_labels(self):
        """Empty labels list returns empty categories."""
        cats = get_regional_categories([])
        assert cats == []


class TestRegionalCategoryIntegration:
    """
    Integration tests for regional categories with CategoryBuilder.

    Tests real-world scenarios from corpus analysis.
    """

    def test_us_slang_noun(self):
        """US slang noun gets POS + regional categories."""
        categories = CategoryBuilder.compute_all(
            "dude", "noun", labels=["US", "slang"]
        )
        assert "English nouns" in categories
        assert "American English" in categories

    def test_british_informal_verb(self):
        """British informal verb gets POS + regional categories."""
        categories = CategoryBuilder.compute_all(
            "snog", "verb", labels=["UK", "informal"]
        )
        assert "English verbs" in categories
        assert "British English" in categories

    def test_australian_noun(self):
        """Australian noun gets regional category."""
        categories = CategoryBuilder.compute_all(
            "arvo", "noun", labels=["Australia"]
        )
        assert "English nouns" in categories
        assert "Australian English" in categories

    def test_multiple_regions(self):
        """Word used in multiple regions gets both categories."""
        categories = CategoryBuilder.compute_all(
            "colour", "noun", labels=["UK", "Australia", "Canada"]
        )
        assert "British English" in categories
        assert "Australian English" in categories
        assert "Canadian English" in categories

    def test_regional_with_grammatical_labels(self):
        """Regional labels combined with grammatical labels."""
        categories = CategoryBuilder.compute_all(
            "reckon", "verb", labels=["US", "transitive"]
        )
        assert "English verbs" in categories
        assert "English transitive verbs" in categories
        assert "American English" in categories

    def test_no_regional_labels(self):
        """Entry without regional labels has no regional categories."""
        categories = CategoryBuilder.compute_all(
            "cat", "noun", labels=["countable"]
        )
        assert "English countable nouns" in categories
        # No regional categories
        assert "American English" not in categories
        assert "British English" not in categories


class TestRegionalDialectData:
    """Tests validating the regional dialect data structure."""

    def test_major_varieties_present(self):
        """All major English varieties are in REGIONAL_LABELS."""
        major = ["US", "UK", "Australia", "Canada", "Ireland", "Scotland", "New Zealand"]
        for variety in major:
            assert variety in REGIONAL_LABELS

    def test_all_labels_have_category(self):
        """All regional labels have a non-empty category."""
        for label, (aliases, category) in REGIONAL_LABELS.items():
            assert category, f"{label} has empty category"
            assert isinstance(category, str)

    def test_aliases_are_sets(self):
        """All alias collections are sets."""
        for label, (aliases, category) in REGIONAL_LABELS.items():
            assert isinstance(aliases, set), f"{label} aliases should be set"
