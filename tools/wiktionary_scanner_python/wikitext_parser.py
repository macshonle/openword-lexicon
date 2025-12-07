"""
wikitext_parser.py - Recursive descent parser for Wiktionary template parameters.

Provides WikitextParser class and helper functions for parsing wikitext templates,
wikilinks, and extracting POS values from head templates.
"""

import re
from dataclasses import dataclass
from typing import List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Utility Functions
# ─────────────────────────────────────────────────────────────────────────────

def strip_namespace_prefix(text: str) -> str:
    """
    Strip interwiki/namespace prefixes from a string.

    Handles prefixes like:
    - ":en:word" → "word"
    - "Category:English nouns" → "English nouns"
    - "word" → "word"

    Args:
        text: String potentially containing namespace prefix

    Returns:
        The string with leading colon and namespace prefix removed.
    """
    result = text.lstrip(':')
    if ':' in result:
        result = result.rsplit(':', 1)[-1]
    return result


def find_closing_braces(text: str, start_pos: int) -> tuple[int, bool]:
    """
    Find the position after the closing '}}' that matches an opening '{{'.

    Handles nested templates correctly using bracket counting.
    Assumes we're positioned right after an opening '{{'.

    Args:
        text: The text to search in
        start_pos: Position right after the opening '{{'

    Returns:
        Tuple of (position, found) where:
        - position: Position after the matching '}}', or len(text) if unclosed
        - found: True if a matching '}}' was found, False if unclosed
    """
    depth = 1
    pos = start_pos

    while pos < len(text) and depth > 0:
        if text[pos:pos + 2] == '{{':
            depth += 1
            pos += 2
        elif text[pos:pos + 2] == '}}':
            depth -= 1
            pos += 2
        else:
            pos += 1

    return pos, depth == 0


# ─────────────────────────────────────────────────────────────────────────────
# Wikitext Parser Data Structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Wikilink:
    """Represents a parsed wikilink: [[target#anchor|display]]"""
    target: str
    anchor: Optional[str] = None
    display: Optional[str] = None

    def text(self) -> str:
        """Return display text if present, otherwise target."""
        return self.display if self.display is not None else self.target

    def clean_target(self) -> str:
        """
        Return target with namespace prefixes stripped.

        Handles interwiki/namespace prefixes like:
        - [[:en:word]] → "word"
        - [[:Category:English nouns]] → "English nouns"
        - [[word]] → "word"

        Returns:
            The target with leading colon and namespace prefix removed.
        """
        return strip_namespace_prefix(self.target)


@dataclass
class Template:
    """Represents a parsed template: {{name|param1|param2|...}}"""
    name: str
    params: List[str]


# ─────────────────────────────────────────────────────────────────────────────
# Wikitext Recursive Descent Parser
# ─────────────────────────────────────────────────────────────────────────────

class WikitextParser:
    """
    Recursive descent parser for Wiktionary template parameters.

    Parsing methods use recursive descent (call stack handles nesting).
    The skip_template() method uses bracket counting for efficiency.
    Each parse method returns structured data; callers decide what to do with it.

    Grammar:
        params          ::= param ("|" param)*
        param           ::= element*
        element         ::= template | wikilink | char
        template        ::= "{{" template_body "}}"
        template_body   ::= (template | wikilink | template_char)*
        wikilink        ::= "[[" target ("#" anchor)? ("|" display)? "]]"
        target          ::= target_char+
        anchor          ::= anchor_char+
        display         ::= display_char+
    """

    def __init__(self, text: str):
        self.text = text
        self.pos = 0

    def peek(self, n: int = 1) -> str:
        """Look ahead n characters without consuming."""
        return self.text[self.pos:self.pos + n]

    def consume(self, n: int = 1) -> str:
        """Consume and return n characters."""
        result = self.text[self.pos:self.pos + n]
        self.pos += n
        return result

    def at_end(self) -> bool:
        """Check if we've reached end of input."""
        return self.pos >= len(self.text)

    def consume_until(self, terminators: str) -> str:
        """Consume characters until any terminator character is reached."""
        result = ""
        while not self.at_end() and self.peek() not in terminators:
            result += self.consume()
        return result

    # ─────────────────────────────────────────────────────────────
    # Top-level entry point: params ::= param ("|" param)*
    # ─────────────────────────────────────────────────────────────
    def parse_params(self) -> List[str]:
        """Parse template parameters separated by |."""
        params = []
        while not self.at_end():
            param = self.parse_param()
            params.append(param)
            if self.peek() == "|":
                self.consume()
            else:
                break
        return params

    # ─────────────────────────────────────────────────────────────
    # param ::= element*  (terminated by | or end)
    # ─────────────────────────────────────────────────────────────
    def parse_param(self) -> str:
        """Parse elements until | or end of input."""
        result = ""
        while not self.at_end() and self.peek() != "|":
            if self.peek(2) == "[[":
                wikilink = self.parse_wikilink()
                result += wikilink.text()  # Extract display or target
            elif self.peek(2) == "{{":
                template = self.parse_template()
                # For morphology params, nested templates are metadata - discard
                _ = template
            else:
                result += self.consume()
        return result.strip()

    # ─────────────────────────────────────────────────────────────
    # wikilink ::= "[[" target ("#" anchor)? ("|" display)? "]]"
    # ─────────────────────────────────────────────────────────────
    def parse_wikilink(self) -> Wikilink:
        """Parse [[target#anchor|display]] -> Wikilink object."""
        self.consume(2)  # consume "[["

        target = self.parse_target()
        anchor = None
        display = None

        # Optional: "#" anchor
        if self.peek() == "#":
            self.consume()
            anchor = self.parse_anchor()

        # Optional: "|" display
        if self.peek() == "|":
            self.consume()
            display = self.parse_display()

        # Consume "]]"
        if self.peek(2) == "]]":
            self.consume(2)

        return Wikilink(target=target, anchor=anchor, display=display)

    def parse_target(self) -> str:
        """target ::= target_char+  where target_char = [^#|\\]]"""
        return self.consume_until("#|]")

    def parse_anchor(self) -> str:
        """anchor ::= anchor_char+  where anchor_char = [^|\\]]"""
        return self.consume_until("|]")

    def parse_display(self) -> str:
        """display ::= display_char+  where display_char = [^\\]]"""
        return self.consume_until("]")

    # ─────────────────────────────────────────────────────────────
    # template ::= "{{" params "}}"
    # (reuses param parsing - templates have same structure!)
    # ─────────────────────────────────────────────────────────────
    def parse_template(self) -> Template:
        """
        Parse {{name|param1|param2|...}} -> Template object.
        RECURSIVELY handles nested templates via parse_template_param_inner().
        """
        self.consume(2)  # consume "{{"

        # Parse template contents as params (recursive!)
        params = self.parse_template_params_inner()

        if self.peek(2) == "}}":
            self.consume(2)

        # First param is template name, rest are params
        name = params[0] if params else ""
        return Template(name=name, params=params[1:])

    def parse_template_params_inner(self) -> List[str]:
        """Parse params inside a template (terminated by }})."""
        params = []
        while not self.at_end() and self.peek(2) != "}}":
            param = self.parse_template_param_inner()
            params.append(param)
            if self.peek() == "|":
                self.consume()
            else:
                break
        return params

    def parse_template_param_inner(self) -> str:
        """Parse a single param inside a template (terminated by | or }})."""
        result = ""
        while not self.at_end() and self.peek() != "|" and self.peek(2) != "}}":
            if self.peek(2) == "[[":
                wikilink = self.parse_wikilink()
                result += wikilink.text()
            elif self.peek(2) == "{{":
                template = self.parse_template()  # RECURSIVE!
                # Nested templates produce no text for our purposes
                _ = template
            else:
                result += self.consume()
        return result.strip()

    # ─────────────────────────────────────────────────────────────
    # strip_markup: Extract clean text, removing templates and
    # replacing wikilinks with their clean targets
    # ─────────────────────────────────────────────────────────────
    def strip_markup(self) -> str:
        """
        Strip wiki markup, extracting clean text.

        Unlike parse_param() which extracts wikilink display text,
        this extracts wikilink targets (with namespace prefixes stripped).
        Templates are removed entirely. Section anchors (#) truncate.

        Used for cleaning lemma values from inflection templates.

        Returns:
            Clean text with markup removed.

        Examples:
            "[[rhodologist]]" → "rhodologist"
            "[[:en:word]]" → "word"
            "germanic {{italic}}" → "germanic"
            "after#noun" → "after"
        """
        result = ""
        while not self.at_end():
            # Section anchor - truncate here
            if self.peek() == "#":
                break
            elif self.peek(2) == "[[":
                wikilink = self.parse_wikilink()
                result += wikilink.clean_target()
            elif self.peek(2) == "{{":
                # Skip templates entirely
                self.skip_template()
            else:
                result += self.consume()
        return result.strip()

    def skip_template(self) -> None:
        """
        Skip over a template without building the structure.

        Handles nested templates correctly using bracket counting.
        Used by strip_markup() to efficiently remove templates.
        """
        if self.peek(2) != "{{":
            return

        self.consume(2)  # consume "{{"
        # Use shared bracket-counting logic
        end_pos, _ = find_closing_braces(self.text, self.pos)
        self.pos = end_pos


def parse_template_params(content: str) -> List[str]:
    """
    Parse template parameters with proper bracket handling.

    This is the main entry point for parsing template content.
    Handles nested [[wikilinks]] and {{templates}} correctly.

    Args:
        content: The inner content of a template (without outer {{ }})

    Returns:
        List of parsed parameter strings with wikilink display text extracted
    """
    parser = WikitextParser(content)
    return parser.parse_params()


def strip_wikitext_markup(text: str) -> str:
    """
    Strip wiki markup from text, returning clean content.

    This is the main entry point for cleaning raw wikitext strings.
    Uses proper bracket-aware parsing to handle:
    - Wikilinks: [[target]] → target, [[:en:word]] → word
    - Templates: {{...}} → removed entirely
    - Section anchors: text#anchor → text (truncated at #)
    - Stray brackets: ]], }}, // → removed

    Args:
        text: Raw text potentially containing wiki markup

    Returns:
        Clean text with all markup removed

    Examples:
        >>> strip_wikitext_markup("[[rhodologist]]")
        'rhodologist'
        >>> strip_wikitext_markup("[[:en:word]]")
        'word'
        >>> strip_wikitext_markup("germanic {{italic}}")
        'germanic'
        >>> strip_wikitext_markup("after#noun")
        'after'
        >>> strip_wikitext_markup("read -> [[#etymology 1")
        'read ->'
    """
    parser = WikitextParser(text)
    result = parser.strip_markup()

    # Clean up stray brackets that might remain from malformed input
    result = result.replace(']]', '')
    result = result.replace('}}', '')
    result = result.replace('//', '')

    return result.strip()


# ─────────────────────────────────────────────────────────────────────────────
# Head Template POS Extraction - Proper parsing for {{head|en|POS|...}}
# ─────────────────────────────────────────────────────────────────────────────

# Regex to find head templates and capture their FULL content (greedy but balanced)
# This matches {{head|en|...}}, {{en-head|en|...}}, {{head-lite|en|...}}
# We capture everything after the template name up to the closing }}
# Note: This is a two-phase approach:
#   1. Find potential head templates with a simple regex
#   2. Use WikitextParser to properly extract parameters
HEAD_TEMPLATE_FINDER = re.compile(
    r'\{\{(head|en-head|head-lite)\|en\|',
    re.IGNORECASE
)


def extract_head_template_content(text: str, start_pos: int) -> Optional[str]:
    """
    Extract the full content of a template starting at start_pos.

    Uses bracket counting to handle nested templates correctly.

    Args:
        text: Full text to search in
        start_pos: Position right after '{{head|en|' (where content begins)

    Returns:
        Template content (without {{ and }}) or None if malformed
    """
    # Use shared bracket-counting logic
    end_pos, found_closing = find_closing_braces(text, start_pos)

    if found_closing:
        # end_pos is after '}}', so content ends 2 chars before
        content_end = end_pos - 2
    else:
        # Unclosed template - return everything we have
        content_end = end_pos

    if content_end > start_pos:
        return text[start_pos:content_end]
    return None


def extract_pos_from_head_template(template_content: str) -> Optional[str]:
    """
    Extract the POS from head template content using proper parsing.

    The POS is the first positional parameter (no '=' in it).
    Named parameters like 'head=...', 'sort=...' are skipped.

    Args:
        template_content: Content after '{{head|en|' and before '}}'

    Returns:
        The POS string (lowercase) or None if not found

    Examples:
        >>> extract_pos_from_head_template("noun form|head=kris kringles")
        'noun form'
        >>> extract_pos_from_head_template("head=[[word]]|noun")
        'noun'
        >>> extract_pos_from_head_template("proper noun|head=[[United States]]")
        'proper noun'
    """
    # Parse using WikitextParser for proper bracket handling
    params = parse_template_params(template_content)

    # Find first positional parameter (no '=' in it)
    for param in params:
        if '=' not in param and param.strip():
            return param.strip().lower()

    return None


def find_head_template_pos_values(text: str) -> List[str]:
    """
    Find all POS values from {{head|en|...}} templates in text.

    Uses proper parsing to correctly handle:
    - Named parameters like head=...
    - Nested templates
    - Wikilinks in parameters

    Args:
        text: Wikitext to search

    Returns:
        List of POS values found (lowercase, deduplicated by order)

    Examples:
        >>> find_head_template_pos_values("{{head|en|noun form|head=cats}}")
        ['noun form']
        >>> find_head_template_pos_values("{{head|en|head=[[word]]|verb}}")
        ['verb']
    """
    pos_values = []
    seen = set()

    for match in HEAD_TEMPLATE_FINDER.finditer(text):
        # Position right after '{{head|en|'
        content_start = match.end()

        # Extract full template content with bracket balancing
        content = extract_head_template_content(text, content_start)
        if not content:
            continue

        # Parse to get POS
        pos = extract_pos_from_head_template(content)
        if pos and pos not in seen:
            seen.add(pos)
            pos_values.append(pos)

    return pos_values
