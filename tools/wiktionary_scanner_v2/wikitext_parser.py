"""
WikitextParser v2 - Clean recursive descent parser for Wiktionary markup.

This parser handles:
- Templates: {{name|param1|param2|...}}
- Wikilinks: [[target#anchor|display]]
- Nested structures (templates within templates, etc.)

Architecture:
    The parser uses recursive descent with explicit grammar rules.
    Each parse method corresponds to a grammar production.

Grammar:
    content         ::= (template | wikilink | text)*
    template        ::= "{{" template_body "}}"
    template_body   ::= name ("|" param)*
    param           ::= (template | wikilink | param_char)*
    wikilink        ::= "[[" target ("#" anchor)? ("|" display)? "]]"
    target          ::= target_char+
    anchor          ::= anchor_char+
    display         ::= (template | wikilink | display_char)*
    name            ::= name_char+
    text            ::= text_char+

Terminal sets:
    name_char       ::= [^|{}]
    param_char      ::= [^|{}]
    target_char     ::= [^#|\\]]
    anchor_char     ::= [^|\\]]
    display_char    ::= [^\\]]
    text_char       ::= [^{}\\[]
"""

from dataclasses import dataclass, field
from typing import Optional


# =============================================================================
# Data structures
# =============================================================================


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
        """Return target with namespace prefixes stripped."""
        result = self.target.lstrip(":")
        if ":" in result:
            result = result.rsplit(":", 1)[-1]
        return result


@dataclass
class Template:
    """Represents a parsed template: {{name|param1|param2|...}}"""

    name: str
    params: list[str] = field(default_factory=list)

    def get_positional(self) -> list[str]:
        """Return only positional parameters (no '=' in them)."""
        return [p for p in self.params if "=" not in p and p.strip()]

    def get_named(self, key: str) -> Optional[str]:
        """Get a named parameter value."""
        prefix = f"{key}="
        for p in self.params:
            if p.startswith(prefix):
                return p[len(prefix) :]
        return None


@dataclass
class ParseResult:
    """Result of parsing content."""

    templates: list[Template] = field(default_factory=list)
    wikilinks: list[Wikilink] = field(default_factory=list)
    text: str = ""


# =============================================================================
# Parser class
# =============================================================================


class WikitextParser:
    """
    Recursive descent parser for Wiktionary markup.

    Usage:
        parser = WikitextParser(text)
        result = parser.parse()  # Get all templates, wikilinks, and text

        # Or for specific extractions:
        templates = parser.find_templates("head")
        labels = parser.extract_labels()
    """

    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.length = len(text)

    # =========================================================================
    # Core parsing primitives
    # =========================================================================

    def peek(self, n: int = 1) -> str:
        """Look ahead n characters without consuming."""
        return self.text[self.pos : self.pos + n]

    def consume(self, n: int = 1) -> str:
        """Consume and return n characters."""
        result = self.text[self.pos : self.pos + n]
        self.pos += n
        return result

    def at_end(self) -> bool:
        """Check if we've reached end of input."""
        return self.pos >= self.length

    def match(self, expected: str) -> bool:
        """Check if current position matches expected string."""
        return self.peek(len(expected)) == expected

    def consume_if(self, expected: str) -> bool:
        """Consume expected string if it matches, return True if consumed."""
        if self.match(expected):
            self.pos += len(expected)
            return True
        return False

    def consume_until(self, terminators: str) -> str:
        """Consume characters until any terminator character is reached."""
        start = self.pos
        while not self.at_end() and self.peek() not in terminators:
            # Don't consume into template/wikilink openers
            if self.match("{{") or self.match("[["):
                break
            self.pos += 1
        return self.text[start : self.pos]

    def consume_until_any(self, *strings: str) -> str:
        """Consume until any of the given strings is found."""
        start = self.pos
        while not self.at_end():
            for s in strings:
                if self.match(s):
                    return self.text[start : self.pos]
            self.pos += 1
        return self.text[start : self.pos]

    # =========================================================================
    # Grammar productions
    # =========================================================================

    def parse(self) -> ParseResult:
        """
        Parse content and return all templates, wikilinks, and remaining text.

        content ::= (template | wikilink | text)*
        """
        result = ParseResult()
        text_parts = []

        while not self.at_end():
            if self.match("{{"):
                template = self.parse_template()
                if template:
                    result.templates.append(template)
            elif self.match("[["):
                wikilink = self.parse_wikilink()
                if wikilink:
                    result.wikilinks.append(wikilink)
                    text_parts.append(wikilink.text())
            else:
                # Plain text
                ch = self.consume()
                text_parts.append(ch)

        result.text = "".join(text_parts)
        return result

    def parse_template(self) -> Optional[Template]:
        """
        Parse a template: {{name|param1|param2|...}}

        template ::= "{{" template_body "}}"
        template_body ::= name ("|" param)*
        """
        if not self.consume_if("{{"):
            return None

        # Parse template name
        name = self.parse_template_name()

        # Parse parameters
        params = []
        while not self.at_end() and not self.match("}}"):
            if self.consume_if("|"):
                param = self.parse_param()
                params.append(param)
            else:
                break

        # Consume closing }}
        self.consume_if("}}")

        return Template(name=name.strip(), params=params)

    def parse_template_name(self) -> str:
        """
        Parse template name (until | or }}).

        name ::= name_char+
        name_char ::= [^|{}]
        """
        chars = []
        while not self.at_end():
            if self.match("|") or self.match("}}"):
                break
            if self.match("{{"):
                # Nested template in name position - skip it
                self.skip_template()
                continue
            chars.append(self.consume())
        return "".join(chars)

    def parse_param(self) -> str:
        """
        Parse a template parameter (until | or }}).

        param ::= (template | wikilink | param_char)*
        param_char ::= [^|{}]
        """
        parts = []
        while not self.at_end():
            if self.match("|") or self.match("}}"):
                break
            if self.match("{{"):
                # Nested template - try to extract meaningful text
                template = self.parse_template()
                if template:
                    text = self._template_to_text(template)
                    if text:
                        parts.append(text)
            elif self.match("[["):
                # Wikilink - extract display text
                wikilink = self.parse_wikilink()
                if wikilink:
                    parts.append(wikilink.text())
            else:
                parts.append(self.consume())

        return "".join(parts).strip()

    def _template_to_text(self, template: Template) -> str:
        """
        Extract display text from a template.

        Handles common templates that produce text:
        - {{m|lang|word}} -> word (mention)
        - {{l|lang|word}} -> word (link)
        - {{w|word}} -> word (Wikipedia link)
        - {{gloss|text}} -> text
        - {{q|text}} -> text (qualifier)
        """
        name = template.name.lower()

        # Templates where second param is the display text (after language)
        if name in ("m", "l", "mention", "link"):
            if len(template.params) >= 2:
                return template.params[1].strip()

        # Templates where first param is the display text
        if name in ("w", "gloss", "q", "qualifier", "i", "qual"):
            if template.params:
                return template.params[0].strip()

        return ""

    def parse_wikilink(self) -> Optional[Wikilink]:
        """
        Parse a wikilink: [[target#anchor|display]]

        wikilink ::= "[[" target ("#" anchor)? ("|" display)? "]]"
        """
        if not self.consume_if("[["):
            return None

        # Parse target
        target = self.parse_wikilink_target()
        anchor = None
        display = None

        # Optional anchor
        if self.consume_if("#"):
            anchor = self.parse_wikilink_anchor()

        # Optional display
        if self.consume_if("|"):
            display = self.parse_wikilink_display()

        # Consume closing ]]
        self.consume_if("]]")

        return Wikilink(target=target, anchor=anchor, display=display if display else None)

    def parse_wikilink_target(self) -> str:
        """
        Parse wikilink target (until #, |, or ]]).

        target ::= target_char+
        target_char ::= [^#|\\]]
        """
        return self.consume_until("#|]")

    def parse_wikilink_anchor(self) -> str:
        """
        Parse wikilink anchor (until | or ]]).

        anchor ::= anchor_char+
        anchor_char ::= [^|\\]]
        """
        return self.consume_until("|]")

    def parse_wikilink_display(self) -> str:
        """
        Parse wikilink display text (until ]]).

        display ::= (template | wikilink | display_char)*
        display_char ::= [^\\]]
        """
        parts = []
        while not self.at_end() and not self.match("]]"):
            if self.match("{{"):
                self.skip_template()
            elif self.match("[["):
                # Nested wikilink
                wikilink = self.parse_wikilink()
                if wikilink:
                    parts.append(wikilink.text())
            else:
                parts.append(self.consume())
        return "".join(parts)

    def skip_template(self) -> None:
        """Skip over a template without building the structure."""
        if not self.consume_if("{{"):
            return

        depth = 1
        while not self.at_end() and depth > 0:
            if self.match("{{"):
                depth += 1
                self.pos += 2
            elif self.match("}}"):
                depth -= 1
                self.pos += 2
            else:
                self.pos += 1

    # =========================================================================
    # High-level extraction methods
    # =========================================================================

    def find_templates(self, *names: str) -> list[Template]:
        """
        Find all templates with the given names (case-insensitive).

        Args:
            names: Template names to search for

        Returns:
            List of matching Template objects
        """
        names_lower = {n.lower() for n in names}
        result = self.parse()
        return [t for t in result.templates if t.name.lower() in names_lower]

    def extract_labels(self) -> list[str]:
        """
        Extract labels from {{lb|en|...}} templates.

        Returns:
            List of label strings (lowercase)
        """
        labels = []
        result = self.parse()

        for template in result.templates:
            name = template.name.lower()
            if name in ("lb", "label", "context"):
                # First param should be language code
                if template.params and template.params[0].lower() == "en":
                    # Rest are labels
                    for param in template.params[1:]:
                        label = param.strip().lower()
                        if label and "=" not in label:
                            labels.append(label)

        return labels

    def extract_head_pos(self) -> list[str]:
        """
        Extract POS values from {{head|en|POS|...}} templates.

        Returns:
            List of POS strings (lowercase)
        """
        pos_values = []
        result = self.parse()

        for template in result.templates:
            name = template.name.lower()
            if name in ("head", "en-head", "head-lite"):
                # First param should be language code
                if template.params and template.params[0].lower() == "en":
                    # Find first positional param after language
                    for param in template.params[1:]:
                        if "=" not in param and param.strip():
                            pos_values.append(param.strip().lower())
                            break

        return pos_values

    def strip_markup(self) -> str:
        """
        Strip wiki markup and return clean text.

        Templates are removed, wikilinks are replaced with their target.
        """
        parts = []
        self.pos = 0  # Reset position

        while not self.at_end():
            if self.match("{{"):
                # Skip template entirely
                self.skip_template()
            elif self.match("[["):
                # Extract wikilink target
                wikilink = self.parse_wikilink()
                if wikilink:
                    parts.append(wikilink.clean_target())
            elif self.peek() == "#":
                # Section anchor - truncate here
                break
            else:
                parts.append(self.consume())

        result = "".join(parts)
        # Clean up stray brackets
        result = result.replace("]]", "").replace("[[", "")
        result = result.replace("}}", "").replace("{{", "")
        return result.strip()


# =============================================================================
# Module-level convenience functions
# =============================================================================


def parse_template_params(content: str) -> list[str]:
    """
    Parse template parameters from content string.

    This parses the content INSIDE a template (without {{ }}).

    Args:
        content: Template content like "en|noun|head=word"

    Returns:
        List of parameter strings
    """
    # Wrap in template markers for the parser
    parser = WikitextParser("{{_|" + content + "}}")
    result = parser.parse()

    if result.templates:
        return result.templates[0].params

    return []


def strip_wikitext_markup(text: str) -> str:
    """
    Strip wiki markup from text, returning clean content.

    Args:
        text: Raw text potentially containing wiki markup

    Returns:
        Clean text with all markup removed
    """
    parser = WikitextParser(text)
    return parser.strip_markup()


def find_templates(text: str, *names: str) -> list[Template]:
    """
    Find all templates with the given names in text.

    Args:
        text: Text to search
        names: Template names to find

    Returns:
        List of matching Template objects
    """
    parser = WikitextParser(text)
    return parser.find_templates(*names)


def extract_labels(text: str) -> list[str]:
    """
    Extract labels from {{lb|en|...}} templates in text.

    Args:
        text: Text to search

    Returns:
        List of label strings
    """
    parser = WikitextParser(text)
    return parser.extract_labels()


def extract_head_pos(text: str) -> list[str]:
    """
    Extract POS values from {{head|en|...}} templates in text.

    Args:
        text: Text to search

    Returns:
        List of POS strings
    """
    parser = WikitextParser(text)
    return parser.extract_head_pos()
