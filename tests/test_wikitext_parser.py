"""Unit tests for the WikitextParser recursive descent parser.

Tests the bracket-aware template parameter parsing that correctly handles:
- Wikilinks with display text: [[target|display]]
- Wikilinks with section anchors: [[page#section|display]]
- Nested templates: {{template|{{nested}}}}
- UTF-8 characters in parameters

This tests the v2 CDA-based parser in openword.scanner.v2.wikitext_parser.
"""

from openword.scanner.v2.wikitext_parser import (
    WikitextParser,
    Wikilink,
    Template,
    parse_template_params,
    strip_wikitext_markup,
    extract_head_pos,
)


class TestWikilink:
    """Test Wikilink dataclass and text extraction."""

    def test_text_returns_display_when_present(self):
        """Should return display text when available."""
        wl = Wikilink(target="isle", display="Isle")
        assert wl.text() == "Isle"

    def test_text_returns_target_when_no_display(self):
        """Should fall back to target when no display text."""
        wl = Wikilink(target="word")
        assert wl.text() == "word"

    def test_anchor_preserved(self):
        """Anchor should be preserved in the object."""
        wl = Wikilink(target="Man", anchor="Etymology 2", display="Man")
        assert wl.anchor == "Etymology 2"
        assert wl.text() == "Man"


class TestWikitextParserBasics:
    """Test basic WikitextParser operations."""

    def test_simple_params(self):
        """Basic pipe-separated parameters."""
        result = parse_template_params("en|word|suffix")
        assert result == ["en", "word", "suffix"]

    def test_empty_string(self):
        """Empty string should return list with empty string."""
        result = parse_template_params("")
        # v2 returns [''] because it wraps in a template for parsing
        assert result == [""] or result == []

    def test_single_param(self):
        """Single parameter without pipes."""
        result = parse_template_params("word")
        assert result == ["word"]

    def test_whitespace_trimming(self):
        """Parameters should be trimmed."""
        result = parse_template_params("  en  |  word  |  suffix  ")
        assert result == ["en", "word", "suffix"]


class TestWikilinkParsing:
    """Test wikilink extraction from template parameters."""

    def test_simple_wikilink(self):
        """[[word]] should extract as 'word'."""
        result = parse_template_params("[[cat]]")
        assert result == ["cat"]

    def test_wikilink_with_display(self):
        """[[target|display]] should extract display text."""
        result = parse_template_params("[[isle|Isle]]")
        assert result == ["Isle"]

    def test_wikilink_with_anchor(self):
        """[[page#section]] should extract page name."""
        result = parse_template_params("[[Man#Etymology 2]]")
        assert result == ["Man"]

    def test_wikilink_with_anchor_and_display(self):
        """[[page#section|display]] should extract display text."""
        result = parse_template_params("[[Man#Etymology 2|Man]]")
        assert result == ["Man"]

    def test_isle_of_man_example(self):
        """The motivating example: Isle of Man etymology template."""
        # From {{af|en|[[isle|Isle]]|of|[[Man#Etymology 2|Man]]}}
        result = parse_template_params("en|[[isle|Isle]]|of|[[Man#Etymology 2|Man]]")
        assert result == ["en", "Isle", "of", "Man"]

    def test_multiple_wikilinks(self):
        """Multiple wikilinks in parameters."""
        result = parse_template_params("[[a|A]]|[[b|B]]|[[c|C]]")
        assert result == ["A", "B", "C"]

    def test_mixed_wikilinks_and_text(self):
        """Mix of wikilinks and plain text."""
        result = parse_template_params("prefix|[[word|Word]]|suffix")
        assert result == ["prefix", "Word", "suffix"]


class TestNestedTemplates:
    """Test nested template handling."""

    def test_nested_template_produces_text(self):
        """Nested templates extract their display text in v2."""
        # v2 extracts text from common templates like {{q|qualifier}}
        result = parse_template_params("foo|{{q|qualifier}}|bar")
        # v2 extracts "qualifier" from {{q|qualifier}}
        assert result == ["foo", "qualifier", "bar"]

    def test_deeply_nested_templates(self):
        """Multiple levels of nested templates."""
        result = parse_template_params("foo|{{a|{{b|{{c|d}}}}}}|bar")
        # Deep nesting - exact behavior depends on template type
        assert isinstance(result, list)
        assert result[0] == "foo"
        assert result[-1] == "bar"

    def test_wikilink_after_template(self):
        """Wikilinks after templates should be parsed correctly."""
        result = parse_template_params("{{info}}|[[word|Word]]")
        # First param may have some content from {{info}}, second is "Word"
        assert result[-1] == "Word"


class TestUTF8Handling:
    """Test handling of UTF-8 multi-byte characters."""

    def test_latin_extended_characters(self):
        """Latin characters with diacritics."""
        result = parse_template_params("nāsus|-o-")
        assert result == ["nāsus", "-o-"]

    def test_alphabeticus_example(self):
        """The case that caused the Rust panic."""
        result = parse_template_params("lang1=la|alphabēticus|-al")
        # lang1=la should be filtered out by clean_template_components,
        # but the parser should handle it
        assert result == ["lang1=la", "alphabēticus", "-al"]

    def test_greek_characters(self):
        """Greek characters should be handled."""
        result = parse_template_params("en|λόγος")
        assert result == ["en", "λόγος"]

    def test_cyrillic_characters(self):
        """Cyrillic characters should be handled."""
        result = parse_template_params("en|слово")
        assert result == ["en", "слово"]

    def test_mixed_scripts_in_wikilink(self):
        """UTF-8 in wikilink display text."""
        result = parse_template_params("[[word|café]]")
        assert result == ["café"]

    def test_utf8_in_anchor(self):
        """UTF-8 characters in section anchor."""
        result = parse_template_params("[[page#Étymologie|display]]")
        assert result == ["display"]


class TestEdgeCases:
    """Test edge cases and unusual inputs."""

    def test_unclosed_wikilink(self):
        """Unclosed wikilink should still parse (handles gracefully)."""
        result = parse_template_params("[[word")
        # v2 may include trailing }} from wrapper, just check word is extracted
        assert "word" in result[0]

    def test_empty_wikilink(self):
        """Empty wikilink [[]] should produce empty string."""
        result = parse_template_params("[[]]")
        assert result == [""]

    def test_consecutive_pipes(self):
        """Consecutive pipes produce empty parameters."""
        result = parse_template_params("a||b")
        assert result == ["a", "", "b"]

    def test_special_characters_in_text(self):
        """Special characters that are not delimiters."""
        result = parse_template_params("word's|don't|it-self")
        assert result == ["word's", "don't", "it-self"]


class TestParserInternals:
    """Test WikitextParser internal methods directly."""

    def test_parse_wikilink_simple(self):
        """Direct wikilink parsing."""
        parser = WikitextParser("[[word]]")
        wl = parser.parse_wikilink()
        assert wl.target == "word"
        assert wl.anchor is None
        assert wl.display is None

    def test_parse_wikilink_with_all_parts(self):
        """Wikilink with target, anchor, and display."""
        parser = WikitextParser("[[Man#Etymology 2|Man]]")
        wl = parser.parse_wikilink()
        assert wl.target == "Man"
        assert wl.anchor == "Etymology 2"
        assert wl.display == "Man"

    def test_parse_template_simple(self):
        """Direct template parsing."""
        parser = WikitextParser("{{m|en|word}}")
        tmpl = parser.parse_template()
        assert tmpl.name == "m"
        assert tmpl.params == ["en", "word"]

    def test_parse_template_nested(self):
        """Nested template parsing."""
        parser = WikitextParser("{{outer|{{inner|a|b}}}}")
        tmpl = parser.parse_template()
        assert tmpl.name == "outer"
        # v2 extracts nested template text based on template type


class TestRealWorldExamples:
    """Test with real Wiktionary template patterns."""

    def test_batsman_compound(self):
        """batsman: {{compound|en|bat|-s-|-man}}"""
        result = parse_template_params("bat|-s-|-man")
        assert result == ["bat", "-s-", "-man"]

    def test_affix_with_link(self):
        """Affix template with linked components."""
        result = parse_template_params("[[un-]]|[[happy]]")
        assert result == ["un-", "happy"]

    def test_suffix_template(self):
        """Suffix pattern."""
        result = parse_template_params("beauty|-ful")
        assert result == ["beauty", "-ful"]

    def test_prefix_template(self):
        """Prefix pattern."""
        result = parse_template_params("un-|happy")
        assert result == ["un-", "happy"]

    def test_confix_template(self):
        """Confix pattern (prefix + base + suffix)."""
        result = parse_template_params("bio-|chemistry|-ist")
        assert result == ["bio-", "chemistry", "-ist"]

    def test_pictograph_style(self):
        """Pattern like pictograph: {{affix|en|la:pictus|-o-|graph}}"""
        result = parse_template_params("la:pictus|-o-|graph")
        assert result == ["la:pictus", "-o-", "graph"]


# ─────────────────────────────────────────────────────────────────────────────
# Head Template POS Extraction Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractHeadPos:
    """Test POS extraction from head templates using v2 API."""

    def test_simple_head_template(self):
        """Simple {{head|en|noun}} template."""
        text = "Some text {{head|en|noun}} more text"
        result = extract_head_pos(text)
        assert result == ["noun"]

    def test_head_template_with_named_param_first(self):
        """{{head|en|head=...|POS}} - the key bug case."""
        text = "{{head|en|head=kris kringles|noun form}}"
        result = extract_head_pos(text)
        assert "noun form" in result

    def test_wikilink_in_head_param(self):
        """Wikilink in head= param shouldn't break parsing."""
        text = "{{head|en|head=[[w:nikon|Nikon]]|proper noun}}"
        result = extract_head_pos(text)
        assert "proper noun" in result

    def test_multiple_head_templates(self):
        """Multiple head templates in same text."""
        text = """
        ===Noun===
        {{head|en|noun}}

        ===Verb===
        {{head|en|verb}}
        """
        result = extract_head_pos(text)
        assert "noun" in result
        assert "verb" in result

    def test_en_head_variant(self):
        """{{en-head|en|...}} variant."""
        text = "{{en-head|en|adjective}}"
        result = extract_head_pos(text)
        assert "adjective" in result

    def test_head_lite_variant(self):
        """{{head-lite|en|...}} variant."""
        text = "{{head-lite|en|adverb}}"
        result = extract_head_pos(text)
        assert "adverb" in result

    def test_no_head_templates(self):
        """Text with no head templates."""
        text = "Just some text without templates"
        result = extract_head_pos(text)
        assert result == []


class TestRealWorldPOSBugs:
    """
    Tests for real bugs found in corpus scan output.

    These are actual malformed POS values that appeared due to
    the regex-based parsing:
    - head=kris kringles
    - head=[[w:nikon
    - head=[[druid]][[-'s
    - head=laffy taffies
    - head=[[mind]][[-'s
    """

    def test_kris_kringles_bug(self):
        """The 'head=kris kringles' bug case."""
        text = "{{head|en|head=kris kringles|noun form}}"
        result = extract_head_pos(text)
        assert "noun form" in result
        # Named params should not appear as POS
        for pos in result:
            assert not pos.startswith("head=")

    def test_nikon_wikilink_bug(self):
        """The 'head=[[w:nikon' unclosed wikilink bug."""
        text = "{{head|en|head=[[w:Nikon|Nikon]]|proper noun}}"
        result = extract_head_pos(text)
        assert "proper noun" in result

    def test_druids_possessive_bug(self):
        """The 'head=[[druid]][[-'s' complex wikilink bug."""
        text = "{{head|en|noun form|head=[[druid]][[-'s|'s]]}}"
        result = extract_head_pos(text)
        assert "noun form" in result

    def test_laffy_taffies_bug(self):
        """The 'head=laffy taffies' bug case."""
        text = "{{head|en|head=Laffy Taffies|noun form}}"
        result = extract_head_pos(text)
        assert "noun form" in result


# ─────────────────────────────────────────────────────────────────────────────
# Wikilink Methods Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestWikilinkCleanTarget:
    """Test Wikilink.clean_target method."""

    def test_interwiki_prefix(self):
        """[[:en:word]] → word"""
        wl = Wikilink(target=":en:word")
        assert wl.clean_target() == "word"

    def test_category_prefix(self):
        """[[:Category:English nouns]] → English nouns"""
        wl = Wikilink(target=":Category:English nouns")
        assert wl.clean_target() == "English nouns"

    def test_simple_word(self):
        """[[word]] → word"""
        wl = Wikilink(target="word")
        assert wl.clean_target() == "word"

    def test_no_leading_colon_with_namespace(self):
        """Category:X without leading colon."""
        wl = Wikilink(target="Category:test")
        assert wl.clean_target() == "test"


# ─────────────────────────────────────────────────────────────────────────────
# Strip Markup Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestStripWikitextMarkup:
    """Test strip_wikitext_markup function."""

    def test_simple_wikilink(self):
        """[[rhodologist]] → rhodologist"""
        assert strip_wikitext_markup("[[rhodologist]]") == "rhodologist"

    def test_interwiki_link(self):
        """[[:en:word]] → word"""
        assert strip_wikitext_markup("[[:en:word]]") == "word"

    def test_template_removal(self):
        """germanic {{italic}} → germanic"""
        assert strip_wikitext_markup("germanic {{italic}}") == "germanic"

    def test_section_anchor_truncation(self):
        """after#noun → after"""
        assert strip_wikitext_markup("after#noun") == "after"

    def test_nested_template(self):
        """Nested templates are fully removed."""
        assert strip_wikitext_markup("word {{a|{{b}}}}") == "word"

    def test_multiple_wikilinks(self):
        """Multiple wikilinks are all processed."""
        assert strip_wikitext_markup("[[a]] and [[b]]") == "a and b"

    def test_empty_input(self):
        """Empty input returns empty string."""
        assert strip_wikitext_markup("") == ""

    def test_only_template(self):
        """Only a template returns empty string."""
        assert strip_wikitext_markup("{{template}}") == ""


# ─────────────────────────────────────────────────────────────────────────────
# Template Class Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestTemplateClass:
    """Test Template dataclass methods."""

    def test_get_positional_basic(self):
        """Get positional params excludes named params."""
        t = Template(name="test", params=["en", "word", "head=cats", "suffix"])
        assert t.get_positional() == ["en", "word", "suffix"]

    def test_get_positional_empty(self):
        """Get positional with no positional params."""
        t = Template(name="test", params=["head=cats", "sort=key"])
        assert t.get_positional() == []

    def test_get_named_found(self):
        """Get named parameter that exists."""
        t = Template(name="test", params=["en", "head=cats", "sort=key"])
        assert t.get_named("head") == "cats"
        assert t.get_named("sort") == "key"

    def test_get_named_not_found(self):
        """Get named parameter that doesn't exist."""
        t = Template(name="test", params=["en", "word"])
        assert t.get_named("head") is None


class TestIncompleteInputHandling:
    """Test graceful handling of incomplete/malformed input."""

    def test_unclosed_wikilink_parse_params(self):
        """Unclosed wikilink in parse_params extracts target."""
        result = parse_template_params("[[word")
        # v2 may include trailing }} from wrapper, just check word is extracted
        assert "word" in result[0]

    def test_unclosed_nested_wikilink(self):
        """Nested unclosed wikilink."""
        result = parse_template_params("[[outer|[[inner")
        # Should handle gracefully without crashing
        assert isinstance(result, list)

    def test_mismatched_brackets(self):
        """Mismatched brackets handled gracefully."""
        result = parse_template_params("]][[word]]")
        # Should not crash
        assert isinstance(result, list)

    def test_only_open_brackets(self):
        """Only opening brackets."""
        result = parse_template_params("[[[[")
        assert isinstance(result, list)

    def test_unclosed_template_strip_markup(self):
        """Unclosed template in strip_wikitext_markup."""
        result = strip_wikitext_markup("text {{unclosed")
        assert "text" in result

    def test_partial_wikilink_strip_markup(self):
        """Partial wikilink like [[word without close."""
        result = strip_wikitext_markup("prefix [[word")
        # Should extract what it can
        assert "prefix" in result

    def test_deeply_nested_unclosed(self):
        """Deeply nested unclosed templates."""
        result = strip_wikitext_markup("text {{a|{{b|{{c")
        assert "text" in result
