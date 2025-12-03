"""Unit tests for unified morphology extraction.

Tests the morphology extraction from Wiktionary etymology templates:
- suffix: {{suffix|en|base|suffix}}
- prefix: {{prefix|en|prefix|base}}
- confix: {{confix|en|prefix|base|suffix}}
- compound: {{compound|en|word1|word2|...}}
- affix/af: {{af|en|part1|part2|...}}
- surf: {{surf|en|part1|part2|...}}

All templates are normalized to a unified Morphology structure with:
- type: 'suffixed' | 'prefixed' | 'affixed' | 'circumfixed' | 'compound' | 'simple'
- components: list of all morphological parts in order
- prefixes: list of prefix morphemes (ending with -)
- suffixes: list of suffix morphemes (starting with -)
- interfixes: list of interfix morphemes (starting and ending with -)
- base: primary base word (None for compounds)
- is_compound: boolean
- etymology_template: raw template string for reference
"""
import pytest
import sys
from pathlib import Path

# Add tools directory to path
tools_path = Path(__file__).parent.parent / "tools"
sys.path.insert(0, str(tools_path))

from wiktionary_scanner_python.scanner import (
    extract_morphology,
    extract_morphology_components,
    classify_morphology,
)


# Test data: (etymology_section_text, expected_result)
# Each test case is a tuple of (input_text, expected_dict or None)

SUFFIX_TEMPLATE_CASES = [
    # Basic suffix template
    (
        "===Etymology===\n{{suffix|en|happy|ness}}",
        {
            'type': 'suffixed',
            'components': ['happy', '-ness'],
            'prefixes': [],
            'suffixes': ['-ness'],
            'base': 'happy',
            'is_compound': False,
        }
    ),
    # Suffix without hyphen in template (should be normalized)
    (
        "===Etymology===\n{{suffix|en|beauty|ful}}",
        {
            'type': 'suffixed',
            'components': ['beauty', '-ful'],
            'prefixes': [],
            'suffixes': ['-ful'],
            'base': 'beauty',
            'is_compound': False,
        }
    ),
    # Suffix with hyphen already present
    (
        "===Etymology===\n{{suffix|en|care|-less}}",
        {
            'type': 'suffixed',
            'components': ['care', '-less'],
            'prefixes': [],
            'suffixes': ['-less'],
            'base': 'care',
            'is_compound': False,
        }
    ),
]

PREFIX_TEMPLATE_CASES = [
    # Basic prefix template
    (
        "===Etymology===\n{{prefix|en|un|happy}}",
        {
            'type': 'prefixed',
            'components': ['un-', 'happy'],
            'prefixes': ['un-'],
            'suffixes': [],
            'base': 'happy',
            'is_compound': False,
        }
    ),
    # Prefix with hyphen already present
    (
        "===Etymology===\n{{prefix|en|re-|build}}",
        {
            'type': 'prefixed',
            'components': ['re-', 'build'],
            'prefixes': ['re-'],
            'suffixes': [],
            'base': 'build',
            'is_compound': False,
        }
    ),
]

CONFIX_TEMPLATE_CASES = [
    # Basic confix template (prefix + base + suffix)
    (
        "===Etymology===\n{{confix|en|en|light|ment}}",
        {
            'type': 'circumfixed',
            'components': ['en-', 'light', '-ment'],
            'prefixes': ['en-'],
            'suffixes': ['-ment'],
            'base': 'light',
            'is_compound': False,
        }
    ),
    # Confix with hyphens already present
    (
        "===Etymology===\n{{confix|en|bio-|chemistry|-ist}}",
        {
            'type': 'circumfixed',
            'components': ['bio-', 'chemistry', '-ist'],
            'prefixes': ['bio-'],
            'suffixes': ['-ist'],
            'base': 'chemistry',
            'is_compound': False,
        }
    ),
]

COMPOUND_TEMPLATE_CASES = [
    # Basic compound
    (
        "===Etymology===\n{{compound|en|sun|flower}}",
        {
            'type': 'compound',
            'components': ['sun', 'flower'],
            'prefixes': [],
            'suffixes': [],
            'base': None,
            'is_compound': True,
        }
    ),
    # Compound with three parts
    (
        "===Etymology===\n{{compound|en|grand|father|clock}}",
        {
            'type': 'compound',
            'components': ['grand', 'father', 'clock'],
            'prefixes': [],
            'suffixes': [],
            'base': None,
            'is_compound': True,
        }
    ),
    # Compound with interfix
    (
        "===Etymology===\n{{compound|en|bee|-s-|wax}}",
        {
            'type': 'compound',
            'components': ['bee', '-s-', 'wax'],
            'prefixes': [],
            'suffixes': [],
            'interfixes': ['-s-'],
            'base': None,
            'is_compound': True,
        }
    ),
]

AFFIX_TEMPLATE_CASES = [
    # Affix template - suffixed
    (
        "===Etymology===\n{{af|en|happy|-ness}}",
        {
            'type': 'suffixed',
            'components': ['happy', '-ness'],
            'prefixes': [],
            'suffixes': ['-ness'],
            'base': 'happy',
            'is_compound': False,
        }
    ),
    # Affix template - prefixed
    (
        "===Etymology===\n{{af|en|un-|happy}}",
        {
            'type': 'prefixed',
            'components': ['un-', 'happy'],
            'prefixes': ['un-'],
            'suffixes': [],
            'base': 'happy',
            'is_compound': False,
        }
    ),
    # Affix template - both prefix and suffix
    (
        "===Etymology===\n{{af|en|un-|break|-able}}",
        {
            'type': 'affixed',
            'components': ['un-', 'break', '-able'],
            'prefixes': ['un-'],
            'suffixes': ['-able'],
            'base': 'break',
            'is_compound': False,
        }
    ),
    # Affix template - compound (no affixes)
    (
        "===Etymology===\n{{af|en|sun|flower}}",
        {
            'type': 'compound',
            'components': ['sun', 'flower'],
            'prefixes': [],
            'suffixes': [],
            'base': None,
            'is_compound': True,
        }
    ),
    # Affix template with full name
    (
        "===Etymology===\n{{affix|en|re-|consider|-ation}}",
        {
            'type': 'affixed',
            'components': ['re-', 'consider', '-ation'],
            'prefixes': ['re-'],
            'suffixes': ['-ation'],
            'base': 'consider',
            'is_compound': False,
        }
    ),
    # Affix with interfix
    (
        "===Etymology===\n{{af|en|speed|-o-|meter}}",
        {
            'type': 'compound',
            'components': ['speed', '-o-', 'meter'],
            'prefixes': [],
            'suffixes': [],
            'interfixes': ['-o-'],
            'base': None,
            'is_compound': True,
        }
    ),
    # Affix with wikilinks
    (
        "===Etymology===\n{{af|en|[[isle|Isle]]|of|[[Man#Etymology 2|Man]]}}",
        {
            'type': 'compound',
            'components': ['Isle', 'of', 'Man'],
            'prefixes': [],
            'suffixes': [],
            'base': None,
            'is_compound': True,
        }
    ),
]

SURF_TEMPLATE_CASES = [
    # Surf template - suffixed (multiple suffixes still counts as 'suffixed')
    (
        "===Etymology===\n{{surf|en|dict|-ion|-ary}}",
        {
            'type': 'suffixed',
            'components': ['dict', '-ion', '-ary'],
            'prefixes': [],
            'suffixes': ['-ion', '-ary'],
            'base': 'dict',
            'is_compound': False,
        }
    ),
    # Surf template - compound-like
    (
        "===Etymology===\n{{surf|en|heli|copter}}",
        {
            'type': 'compound',
            'components': ['heli', 'copter'],
            'prefixes': [],
            'suffixes': [],
            'base': None,
            'is_compound': True,
        }
    ),
]

EDGE_CASES = [
    # No etymology section
    (
        "===Etymology===\nNo morphology template here",
        None
    ),
    # Template with named parameters (should be filtered)
    (
        "===Etymology===\n{{af|en|un-|happy|pos=adjective}}",
        {
            'type': 'prefixed',
            'components': ['un-', 'happy'],
            'prefixes': ['un-'],
            'suffixes': [],
            'base': 'happy',
            'is_compound': False,
        }
    ),
]


class TestExtractMorphologyComponents:
    """Test the component extraction from various template types."""

    @pytest.mark.parametrize("input_text,expected", SUFFIX_TEMPLATE_CASES)
    def test_suffix_templates(self, input_text, expected):
        """Test suffix template extraction and normalization."""
        result = extract_morphology(input_text)
        assert result is not None
        assert result['type'] == expected['type']
        assert result['components'] == expected['components']
        assert result['prefixes'] == expected['prefixes']
        assert result['suffixes'] == expected['suffixes']
        assert result.get('base') == expected.get('base')
        assert result['is_compound'] == expected['is_compound']

    @pytest.mark.parametrize("input_text,expected", PREFIX_TEMPLATE_CASES)
    def test_prefix_templates(self, input_text, expected):
        """Test prefix template extraction and normalization."""
        result = extract_morphology(input_text)
        assert result is not None
        assert result['type'] == expected['type']
        assert result['components'] == expected['components']
        assert result['prefixes'] == expected['prefixes']
        assert result['suffixes'] == expected['suffixes']
        assert result.get('base') == expected.get('base')
        assert result['is_compound'] == expected['is_compound']

    @pytest.mark.parametrize("input_text,expected", CONFIX_TEMPLATE_CASES)
    def test_confix_templates(self, input_text, expected):
        """Test confix template extraction and normalization."""
        result = extract_morphology(input_text)
        assert result is not None
        assert result['type'] == expected['type']
        assert result['components'] == expected['components']
        assert result['prefixes'] == expected['prefixes']
        assert result['suffixes'] == expected['suffixes']
        assert result.get('base') == expected.get('base')
        assert result['is_compound'] == expected['is_compound']

    @pytest.mark.parametrize("input_text,expected", COMPOUND_TEMPLATE_CASES)
    def test_compound_templates(self, input_text, expected):
        """Test compound template extraction."""
        result = extract_morphology(input_text)
        assert result is not None
        assert result['type'] == expected['type']
        assert result['components'] == expected['components']
        assert result['prefixes'] == expected['prefixes']
        assert result['suffixes'] == expected['suffixes']
        assert result.get('base') == expected.get('base')
        assert result['is_compound'] == expected['is_compound']
        if 'interfixes' in expected:
            assert result.get('interfixes') == expected['interfixes']

    @pytest.mark.parametrize("input_text,expected", AFFIX_TEMPLATE_CASES)
    def test_affix_templates(self, input_text, expected):
        """Test affix/af template extraction."""
        result = extract_morphology(input_text)
        assert result is not None
        assert result['type'] == expected['type']
        assert result['components'] == expected['components']
        assert result['prefixes'] == expected['prefixes']
        assert result['suffixes'] == expected['suffixes']
        assert result.get('base') == expected.get('base')
        assert result['is_compound'] == expected['is_compound']
        if 'interfixes' in expected:
            assert result.get('interfixes') == expected['interfixes']

    @pytest.mark.parametrize("input_text,expected", SURF_TEMPLATE_CASES)
    def test_surf_templates(self, input_text, expected):
        """Test surf template extraction."""
        result = extract_morphology(input_text)
        assert result is not None
        assert result['type'] == expected['type']
        assert result['components'] == expected['components']
        assert result['prefixes'] == expected['prefixes']
        assert result['suffixes'] == expected['suffixes']
        assert result.get('base') == expected.get('base')
        assert result['is_compound'] == expected['is_compound']


class TestClassifyMorphology:
    """Test the morphology classification function directly."""

    def test_classify_suffixed(self):
        """Components with only suffix should be classified as suffixed."""
        result = classify_morphology(['happy', '-ness'], '{{test}}')
        assert result['type'] == 'suffixed'
        assert result['base'] == 'happy'
        assert result['suffixes'] == ['-ness']
        assert result['is_compound'] is False

    def test_classify_prefixed(self):
        """Components with only prefix should be classified as prefixed."""
        result = classify_morphology(['un-', 'happy'], '{{test}}')
        assert result['type'] == 'prefixed'
        assert result['base'] == 'happy'
        assert result['prefixes'] == ['un-']
        assert result['is_compound'] is False

    def test_classify_affixed(self):
        """Components with both prefix and suffix should be classified as affixed."""
        result = classify_morphology(['un-', 'break', '-able'], '{{test}}')
        assert result['type'] == 'affixed'
        assert result['base'] == 'break'
        assert result['prefixes'] == ['un-']
        assert result['suffixes'] == ['-able']
        assert result['is_compound'] is False

    def test_classify_compound(self):
        """Components with multiple bases should be classified as compound."""
        result = classify_morphology(['sun', 'flower'], '{{test}}')
        assert result['type'] == 'compound'
        assert result.get('base') is None
        assert result['is_compound'] is True

    def test_classify_compound_with_interfix(self):
        """Compound with interfix should include interfixes."""
        result = classify_morphology(['bee', '-s-', 'wax'], '{{test}}')
        assert result['type'] == 'compound'
        assert result.get('base') is None
        assert result['interfixes'] == ['-s-']
        assert result['is_compound'] is True

    def test_classify_multiple_suffixes(self):
        """Multiple suffixes should all be captured."""
        result = classify_morphology(['dict', '-ion', '-ary'], '{{test}}')
        assert result['suffixes'] == ['-ion', '-ary']
        assert result['base'] == 'dict'

    def test_classify_multiple_prefixes(self):
        """Multiple prefixes should all be captured."""
        result = classify_morphology(['un-', 're-', 'do'], '{{test}}')
        assert result['prefixes'] == ['un-', 're-']
        assert result['base'] == 'do'


class TestTemplatePriority:
    """Test that template matching follows the correct priority order."""

    def test_suffix_before_affix(self):
        """Suffix template should be matched before general affix."""
        # If both templates exist, suffix should take precedence
        text = "===Etymology===\n{{suffix|en|happy|ness}}\n{{af|en|other|stuff}}"
        result = extract_morphology(text)
        assert result is not None
        assert 'suffix' in result['etymology_template'].lower()
        assert result['components'] == ['happy', '-ness']

    def test_compound_before_affix(self):
        """Compound template should be matched before general affix."""
        text = "===Etymology===\n{{compound|en|sun|flower}}\n{{af|en|other|stuff}}"
        result = extract_morphology(text)
        assert result is not None
        assert 'compound' in result['etymology_template'].lower()


class TestRealWorldExamples:
    """Test with real Wiktionary patterns."""

    def test_happiness(self):
        """happiness = happy + -ness"""
        text = "===Etymology===\nFrom {{suffix|en|happy|ness}}."
        result = extract_morphology(text)
        assert result is not None
        assert result['type'] == 'suffixed'
        assert result['base'] == 'happy'

    def test_unhappy(self):
        """unhappy = un- + happy"""
        text = "===Etymology===\nFrom {{prefix|en|un|happy}}."
        result = extract_morphology(text)
        assert result is not None
        assert result['type'] == 'prefixed'
        assert result['base'] == 'happy'

    def test_unbreakable(self):
        """unbreakable = un- + break + -able"""
        text = "===Etymology===\n{{af|en|un-|break|-able}}"
        result = extract_morphology(text)
        assert result is not None
        assert result['type'] == 'affixed'
        assert result['base'] == 'break'
        assert result['prefixes'] == ['un-']
        assert result['suffixes'] == ['-able']

    def test_sunflower(self):
        """sunflower = sun + flower"""
        text = "===Etymology===\n{{compound|en|sun|flower}}"
        result = extract_morphology(text)
        assert result is not None
        assert result['type'] == 'compound'
        assert result['is_compound'] is True
        assert result.get('base') is None

    def test_speedometer(self):
        """speedometer = speed + -o- + meter"""
        text = "===Etymology===\n{{af|en|speed|-o-|meter}}"
        result = extract_morphology(text)
        assert result is not None
        assert result['type'] == 'compound'
        assert result['interfixes'] == ['-o-']

    def test_isle_of_man(self):
        """Isle of Man with wikilinks"""
        text = "===Etymology===\n{{af|en|[[isle|Isle]]|of|[[Man#Etymology 2|Man]]}}"
        result = extract_morphology(text)
        assert result is not None
        assert result['components'] == ['Isle', 'of', 'Man']
