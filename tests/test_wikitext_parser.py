"""Unit tests for the WikitextParser recursive descent parser.

Tests the bracket-aware template parameter parsing that correctly handles:
- Wikilinks with display text: [[target|display]]
- Wikilinks with section anchors: [[page#section|display]]
- Nested templates: {{template|{{nested}}}}
- UTF-8 characters in parameters
"""
import pytest
import sys
from pathlib import Path

# Add tools directory to path
tools_path = Path(__file__).parent.parent / "tools"
sys.path.insert(0, str(tools_path))

from wiktionary_scanner_parser import (
    WikitextParser,
    Wikilink,
    Template,
    parse_template_params,
    extract_head_template_content,
    extract_pos_from_head_template,
    find_head_template_pos_values,
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
        """Empty string should return empty list."""
        result = parse_template_params("")
        assert result == []

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

    def test_nested_template_discarded(self):
        """Nested templates should be discarded from output."""
        result = parse_template_params("foo|{{q|qualifier}}|bar")
        assert result == ["foo", "", "bar"]

    def test_deeply_nested_templates(self):
        """Multiple levels of nested templates."""
        result = parse_template_params("foo|{{a|{{b|{{c|d}}}}}}|bar")
        assert result == ["foo", "", "bar"]

    def test_template_with_wikilink_inside(self):
        """Template containing wikilink should still be discarded."""
        result = parse_template_params("foo|{{m|en|[[word]]}}|bar")
        assert result == ["foo", "", "bar"]

    def test_wikilink_after_template(self):
        """Wikilinks after templates should be parsed correctly."""
        result = parse_template_params("{{info}}|[[word|Word]]")
        assert result == ["", "Word"]


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
        """Unclosed wikilink should still parse."""
        result = parse_template_params("[[word")
        assert result == ["word"]

    def test_unclosed_template(self):
        """Unclosed template should still parse."""
        result = parse_template_params("{{template")
        assert result == [""]

    def test_empty_wikilink(self):
        """Empty wikilink [[]] should produce empty string."""
        result = parse_template_params("[[]]")
        assert result == [""]

    def test_consecutive_pipes(self):
        """Consecutive pipes produce empty parameters."""
        result = parse_template_params("a||b")
        assert result == ["a", "", "b"]

    def test_wikilink_with_only_anchor(self):
        """[[#section]] should return empty target."""
        result = parse_template_params("[[#section]]")
        # Target is empty, anchor is "section", no display
        # text() returns target which is empty
        assert result == [""]

    def test_wikilink_with_empty_display(self):
        """[[word|]] should return empty display."""
        result = parse_template_params("[[word|]]")
        # Empty display should return empty string
        assert result == [""]

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
        # Inner template is parsed but its text is discarded
        assert tmpl.params == [""]


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

class TestExtractHeadTemplateContent:
    """Test bracket-balanced template content extraction."""

    def test_simple_template(self):
        """Simple template without nesting."""
        text = "{{head|en|noun form|head=cats}}"
        # Start after '{{head|en|'
        content = extract_head_template_content(text, 10)
        assert content == "noun form|head=cats"

    def test_nested_template(self):
        """Template with nested template inside."""
        text = "{{head|en|noun|head={{m|en|word}}}}"
        content = extract_head_template_content(text, 10)
        assert content == "noun|head={{m|en|word}}"

    def test_wikilink_inside(self):
        """Template with wikilink (doesn't affect bracket counting)."""
        text = "{{head|en|noun|head=[[word]]}}"
        content = extract_head_template_content(text, 10)
        assert content == "noun|head=[[word]]"

    def test_deeply_nested(self):
        """Multiple levels of nested templates."""
        text = "{{head|en|noun|head={{a|{{b|c}}}}}}"
        content = extract_head_template_content(text, 10)
        assert content == "noun|head={{a|{{b|c}}}}"

    def test_unclosed_template(self):
        """Unclosed template returns what we have."""
        text = "{{head|en|noun|head=word"
        content = extract_head_template_content(text, 10)
        assert content == "noun|head=word"


class TestExtractPosFromHeadTemplate:
    """Test POS extraction from parsed template content."""

    def test_simple_pos(self):
        """Simple POS as first param."""
        pos = extract_pos_from_head_template("noun")
        assert pos == "noun"

    def test_pos_with_named_params_after(self):
        """POS followed by named params."""
        pos = extract_pos_from_head_template("noun form|head=cats")
        assert pos == "noun form"

    def test_named_param_first_then_pos(self):
        """Named param comes before POS - should skip to POS.

        This is the key bug fix - templates like:
        {{head|en|head=kris kringles|noun form}}
        Should return 'noun form', not 'head=kris kringles'
        """
        pos = extract_pos_from_head_template("head=kris kringles|noun form")
        assert pos == "noun form"

    def test_wikilink_in_named_param(self):
        """Wikilink inside named param shouldn't confuse parser."""
        pos = extract_pos_from_head_template("head=[[word]]|noun")
        assert pos == "noun"

    def test_multiple_named_params_before_pos(self):
        """Multiple named params before POS."""
        pos = extract_pos_from_head_template("head=word|sort=sort key|noun")
        assert pos == "noun"

    def test_proper_noun_pos(self):
        """Multi-word POS like 'proper noun'."""
        pos = extract_pos_from_head_template("proper noun|head=[[United States]]")
        assert pos == "proper noun"

    def test_pos_with_nested_template(self):
        """POS with nested template in another param."""
        pos = extract_pos_from_head_template("verb|head={{m|en|word}}")
        assert pos == "verb"

    def test_only_named_params_returns_none(self):
        """Only named params with no positional returns None."""
        pos = extract_pos_from_head_template("head=word|sort=key")
        assert pos is None

    def test_empty_content_returns_none(self):
        """Empty content returns None."""
        pos = extract_pos_from_head_template("")
        assert pos is None

    def test_case_normalization(self):
        """POS is returned lowercase."""
        pos = extract_pos_from_head_template("Noun Form")
        assert pos == "noun form"


class TestFindHeadTemplatePosValues:
    """Test finding all POS values in text using proper parsing."""

    def test_simple_head_template(self):
        """Simple {{head|en|noun}} template."""
        text = "Some text {{head|en|noun}} more text"
        result = find_head_template_pos_values(text)
        assert result == ["noun"]

    def test_head_template_with_named_param_first(self):
        """{{head|en|head=...|POS}} - the key bug case."""
        text = "{{head|en|head=kris kringles|noun form}}"
        result = find_head_template_pos_values(text)
        assert result == ["noun form"]

    def test_wikilink_in_head_param(self):
        """Wikilink in head= param shouldn't break parsing."""
        text = "{{head|en|head=[[w:nikon|Nikon]]|proper noun}}"
        result = find_head_template_pos_values(text)
        assert result == ["proper noun"]

    def test_multiple_head_templates(self):
        """Multiple head templates in same text."""
        text = """
        ===Noun===
        {{head|en|noun}}

        ===Verb===
        {{head|en|verb}}
        """
        result = find_head_template_pos_values(text)
        assert result == ["noun", "verb"]

    def test_deduplication(self):
        """Same POS appears twice - should be deduplicated."""
        text = "{{head|en|noun}} and {{head|en|noun}}"
        result = find_head_template_pos_values(text)
        assert result == ["noun"]

    def test_en_head_variant(self):
        """{{en-head|en|...}} variant."""
        text = "{{en-head|en|adjective}}"
        result = find_head_template_pos_values(text)
        assert result == ["adjective"]

    def test_head_lite_variant(self):
        """{{head-lite|en|...}} variant."""
        text = "{{head-lite|en|adverb}}"
        result = find_head_template_pos_values(text)
        assert result == ["adverb"]

    def test_nested_template_in_head(self):
        """Nested template in head param doesn't break bracket counting."""
        text = "{{head|en|noun|head={{m|en|[[word]]}}}}"
        result = find_head_template_pos_values(text)
        assert result == ["noun"]

    def test_complex_wikilink_pattern(self):
        """Complex wikilink pattern from real data."""
        text = "{{head|en|noun form|head=[[druid]][[-'s|'s]] [[grove]]}}"
        result = find_head_template_pos_values(text)
        assert result == ["noun form"]

    def test_no_head_templates(self):
        """Text with no head templates."""
        text = "Just some text without templates"
        result = find_head_template_pos_values(text)
        assert result == []

    def test_other_templates_ignored(self):
        """Non-head templates are ignored."""
        text = "{{en-noun}} {{lb|en|slang}} {{head|en|verb}}"
        result = find_head_template_pos_values(text)
        assert result == ["verb"]


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
        result = find_head_template_pos_values(text)
        assert result == ["noun form"]
        assert "head=kris kringles" not in result

    def test_nikon_wikilink_bug(self):
        """The 'head=[[w:nikon' unclosed wikilink bug."""
        # This was captured because regex stopped at first |
        text = "{{head|en|head=[[w:Nikon|Nikon]]|proper noun}}"
        result = find_head_template_pos_values(text)
        assert result == ["proper noun"]

    def test_druids_possessive_bug(self):
        """The 'head=[[druid]][[-'s' complex wikilink bug."""
        text = "{{head|en|noun form|head=[[druid]][[-'s|'s]]}}"
        result = find_head_template_pos_values(text)
        assert result == ["noun form"]

    def test_laffy_taffies_bug(self):
        """The 'head=laffy taffies' bug case."""
        text = "{{head|en|head=Laffy Taffies|noun form}}"
        result = find_head_template_pos_values(text)
        assert result == ["noun form"]

    def test_minds_ear_bug(self):
        """The 'head=[[minds]]' [[ear]]' complex pattern."""
        text = "{{head|en|noun|head=[[mind]][[-'s|'s]] [[ear]]}}"
        result = find_head_template_pos_values(text)
        assert result == ["noun"]

    def test_dash_only_pos(self):
        """The '-' POS edge case (used for some entries)."""
        text = "{{head|en|-}}"
        result = find_head_template_pos_values(text)
        assert result == ["-"]

    def test_nf_abbreviation(self):
        """The 'nf' POS (noun form abbreviation)."""
        text = "{{head|en|nf}}"
        result = find_head_template_pos_values(text)
        assert result == ["nf"]
