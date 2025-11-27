use bzip2::read::BzDecoder;
use clap::Parser;
use indicatif::{ProgressBar, ProgressStyle};
use lazy_static::lazy_static;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::fs::File;
use std::io::{BufRead, BufReader, BufWriter, Write};
use std::path::PathBuf;
use std::time::Instant;
use unicode_normalization::UnicodeNormalization;

#[derive(Parser)]
#[command(name = "wiktionary-rust")]
#[command(about = "Fast Rust-based Wiktionary XML parser - outputs one entry per sense")]
struct Args {
    /// Input XML file (.xml or .xml.bz2)
    input: PathBuf,

    /// Output JSONL file
    output: PathBuf,

    /// Limit number of entries to extract (for testing)
    #[arg(long)]
    limit: Option<usize>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
struct Morphology {
    #[serde(rename = "type")]
    morph_type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    base: Option<String>,
    components: Vec<String>,
    prefixes: Vec<String>,
    suffixes: Vec<String>,
    is_compound: bool,
    etymology_template: String,
}

/// Flat entry structure - one per sense (definition line)
#[derive(Debug, Serialize, Deserialize)]
struct Entry {
    word: String,
    pos: String,  // Single POS, not Vec

    // Flat label arrays (not nested HashMap)
    #[serde(skip_serializing_if = "Vec::is_empty")]
    register_tags: Vec<String>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    region_tags: Vec<String>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    domain_tags: Vec<String>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    temporal_tags: Vec<String>,

    // Regional spelling variant (e.g., "en-US" for American spelling, "en-GB" for British)
    // Extracted from {{tlb|en|American spelling}} or similar on head lines
    #[serde(skip_serializing_if = "Option::is_none")]
    spelling_region: Option<String>,

    // Word-level fields (duplicated across senses)
    word_count: usize,
    is_phrase: bool,
    is_abbreviation: bool,
    is_proper_noun: bool,
    is_inflected: bool,

    // Lemma (base form) for inflected words
    // Extracted from templates like {{plural of|en|cat}} → "cat"
    #[serde(skip_serializing_if = "Option::is_none")]
    lemma: Option<String>,

    #[serde(skip_serializing_if = "Option::is_none")]
    phrase_type: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    syllables: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    morphology: Option<Morphology>,
}

/// Represents a POS section with its definitions
struct PosSection {
    pos: String,
    is_proper_noun: bool,
    definitions: Vec<String>,  // Raw definition lines
}

/// Word-level data extracted once and shared across senses
struct WordData {
    word: String,
    word_count: usize,
    is_phrase: bool,
    is_abbreviation: bool,
    is_inflected: bool,
    lemma: Option<String>,
    phrase_type: Option<String>,
    syllables: Option<usize>,
    morphology: Option<Morphology>,
    spelling_region: Option<String>,
}

lazy_static! {
    // Basic XML patterns
    static ref TITLE_PATTERN: Regex = Regex::new(r"<title>([^<]+)</title>").unwrap();
    static ref NS_PATTERN: Regex = Regex::new(r"<ns>(\d+)</ns>").unwrap();
    static ref TEXT_PATTERN: Regex = Regex::new(r"(?s)<text[^>]*>(.+?)</text>").unwrap();
    static ref REDIRECT_PATTERN: Regex = Regex::new(r#"<redirect\s+title="[^"]+""#).unwrap();

    // English section
    static ref ENGLISH_SECTION: Regex = Regex::new(r"(?i)==\s*English\s*==").unwrap();
    static ref LANGUAGE_SECTION: Regex = Regex::new(r"(?m)^==\s*([^=]+?)\s*==$").unwrap();

    // POS patterns - match level 3 and 4 headers
    static ref POS_HEADER: Regex = Regex::new(r"(?m)^===+\s*(.+?)\s*===+\s*$").unwrap();
    static ref HEAD_TEMPLATE: Regex = Regex::new(r"(?i)\{\{(?:head|en-head|head-lite)\|en\|([^}|]+)").unwrap();
    static ref EN_POS_TEMPLATE: Regex = Regex::new(r"(?i)\{\{en-(noun|verb|adj|adv|prop|pron)\b").unwrap();

    // Definition line pattern - lines starting with # (but not ## which are sub-definitions)
    static ref DEFINITION_LINE: Regex = Regex::new(r"(?m)^#\s+(.+)$").unwrap();

    // Label patterns - for extracting from definition lines
    static ref CONTEXT_LABEL: Regex = Regex::new(r"(?i)\{\{(?:lb|label|context)\|en\|([^}]+)\}\}").unwrap();
    static ref CATEGORY: Regex = Regex::new(r"(?i)\[\[Category:English\s+([^\]]+)\]\]").unwrap();

    // Other patterns
    static ref ABBREVIATION_TEMPLATE: Regex = Regex::new(r"(?i)\{\{(?:abbreviation of|abbrev of|abbr of|initialism of)\|en\|").unwrap();
    static ref DICT_ONLY: Regex = Regex::new(r"(?i)\{\{no entry\|en").unwrap();

    // Syllable extraction patterns
    static ref HYPHENATION_TEMPLATE: Regex = Regex::new(r"(?i)\{\{(?:hyphenation|hyph)\|en\|([^}]+)\}\}").unwrap();
    static ref RHYMES_SYLLABLE: Regex = Regex::new(r"(?i)\{\{rhymes\|en\|[^}]*\|s=(\d+)").unwrap();
    static ref SYLLABLE_CATEGORY: Regex = Regex::new(r"(?i)\[\[Category:English\s+(\d+)-syllable\s+words?\]\]").unwrap();

    // Phrase type patterns
    static ref PREP_PHRASE_TEMPLATE: Regex = Regex::new(r"(?i)\{\{en-prepphr\b").unwrap();

    // Morphology/etymology patterns
    static ref ETYMOLOGY_SECTION: Regex = Regex::new(r"(?si)===+\s*Etymology\s*\d*\s*===+\s*\n(.+)").unwrap();
    static ref NEXT_SECTION: Regex = Regex::new(r"\n===").unwrap();
    static ref SUFFIX_TEMPLATE: Regex = Regex::new(r"(?i)\{\{suffix\|en\|([^}|]+)\|([^}|]+)(?:\|([^}|]+))?\}\}").unwrap();
    static ref PREFIX_TEMPLATE: Regex = Regex::new(r"(?i)\{\{prefix\|en\|([^}|]+)\|([^}|]+)(?:\|([^}|]+))?\}\}").unwrap();
    static ref AFFIX_TEMPLATE: Regex = Regex::new(r"(?i)\{\{affix\|en\|([^}]+)\}\}").unwrap();
    static ref COMPOUND_TEMPLATE: Regex = Regex::new(r"(?i)\{\{compound\|en\|([^}]+)\}\}").unwrap();
    static ref SURF_TEMPLATE: Regex = Regex::new(r"(?i)\{\{surf\|en\|([^}]+)\}\}").unwrap();
    static ref CONFIX_TEMPLATE: Regex = Regex::new(r"(?i)\{\{confix\|en\|([^}|]+)\|([^}|]+)\|([^}|]+)(?:\|([^}|]+))?\}\}").unwrap();

    // POS mapping
    static ref POS_MAP: HashMap<&'static str, &'static str> = {
        let mut m = HashMap::new();
        m.insert("noun", "noun");
        m.insert("proper noun", "noun");
        m.insert("proper name", "noun");
        m.insert("propernoun", "noun");
        m.insert("verb", "verb");
        m.insert("verb form", "verb");
        m.insert("participle", "verb");
        m.insert("adjective", "adjective");
        m.insert("adverb", "adverb");
        m.insert("pronoun", "pronoun");
        m.insert("preposition", "preposition");
        m.insert("conjunction", "conjunction");
        m.insert("interjection", "interjection");
        m.insert("determiner", "determiner");
        m.insert("article", "article");
        m.insert("particle", "particle");
        m.insert("auxiliary", "auxiliary");
        m.insert("contraction", "verb");
        m.insert("prefix", "affix");
        m.insert("suffix", "affix");
        m.insert("infix", "affix");
        m.insert("circumfix", "affix");
        m.insert("interfix", "affix");
        m.insert("phrase", "phrase");
        m.insert("prepositional phrase", "phrase");
        m.insert("adverbial phrase", "phrase");
        m.insert("verb phrase", "phrase");
        m.insert("verb phrase form", "phrase");
        m.insert("idiom", "phrase");
        m.insert("proverb", "phrase");
        m.insert("numeral", "numeral");
        m.insert("symbol", "symbol");
        m.insert("symbols", "symbol");
        m.insert("letter", "letter");
        m.insert("multiple parts of speech", "multiple");
        m
    };

    // Label sets
    static ref REGISTER_LABELS: HashSet<&'static str> = {
        let mut s = HashSet::new();
        s.insert("informal");
        s.insert("colloquial");
        s.insert("slang");
        s.insert("vulgar");
        s.insert("offensive");
        s.insert("derogatory");
        s.insert("formal");
        s.insert("euphemistic");
        s.insert("humorous");
        s.insert("literary");
        s.insert("childish");
        s.insert("baby talk");
        s.insert("infantile");
        s.insert("puerile");
        s
    };

    static ref TEMPORAL_LABELS: HashSet<&'static str> = {
        let mut s = HashSet::new();
        s.insert("archaic");
        s.insert("obsolete");
        s.insert("dated");
        s.insert("historical");
        s.insert("rare");
        s
    };

    static ref DOMAIN_LABELS: HashSet<&'static str> = {
        let mut s = HashSet::new();
        s.insert("computing");
        s.insert("mathematics");
        s.insert("medicine");
        s.insert("biology");
        s.insert("chemistry");
        s.insert("physics");
        s.insert("law");
        s.insert("military");
        s.insert("nautical");
        s.insert("aviation");
        s.insert("sports");
        s
    };

    // Special page prefixes
    static ref SPECIAL_PREFIXES: Vec<&'static str> = vec![
        "Wiktionary:",
        "MediaWiki:",
        "Module:",
        "Thread:",
        "Appendix:",
        "Help:",
        "Template:",
        "Reconstruction:",
        "Unsupported titles/",
        "Category:",
    ];

    // Regional label patterns
    static ref REGION_LABELS: HashMap<&'static str, &'static str> = {
        let mut m = HashMap::new();
        m.insert("british", "en-GB");
        m.insert("uk", "en-GB");
        m.insert("us", "en-US");
        m.insert("american", "en-US");
        m.insert("canadian", "en-CA");
        m.insert("australia", "en-AU");
        m.insert("australian", "en-AU");
        m.insert("new zealand", "en-NZ");
        m.insert("ireland", "en-IE");
        m.insert("irish", "en-IE");
        m.insert("south africa", "en-ZA");
        m.insert("india", "en-IN");
        m.insert("indian", "en-IN");
        m
    };

    // Spelling variant labels - maps label text to region code
    // These appear in {{tlb|en|American spelling}} templates on head lines
    static ref SPELLING_LABELS: HashMap<&'static str, &'static str> = {
        let mut m = HashMap::new();
        m.insert("american spelling", "en-US");
        m.insert("us spelling", "en-US");
        m.insert("british spelling", "en-GB");
        m.insert("uk spelling", "en-GB");
        m.insert("commonwealth spelling", "en-GB");
        m.insert("canadian spelling", "en-CA");
        m.insert("australian spelling", "en-AU");
        m.insert("irish spelling", "en-IE");
        m.insert("new zealand spelling", "en-NZ");
        m.insert("south african spelling", "en-ZA");
        m.insert("indian spelling", "en-IN");
        m
    };

    // Pattern to extract {{tlb|en|...}} or {{lb|en|...}} from text
    // Used for head line labels (spelling variants)
    static ref TLB_TEMPLATE: Regex = Regex::new(r"(?i)\{\{(?:tlb|lb)\|en\|([^}]+)\}\}").unwrap();

    // Inflection templates for lemma extraction
    // These templates indicate the word is a grammatical inflection of a base word (lemma)
    // Only includes true morphological inflections, not alternative spellings or forms
    // Format: {{template name|en|lemma|optional params...}}
    static ref INFLECTION_TEMPLATES: Vec<(&'static str, Regex)> = vec![
        // Noun inflections
        ("plural of", Regex::new(r"(?i)\{\{plural of\|en\|([^|}]+)").unwrap()),

        // Verb inflections
        ("past tense of", Regex::new(r"(?i)\{\{past tense of\|en\|([^|}]+)").unwrap()),
        ("past participle of", Regex::new(r"(?i)\{\{past participle of\|en\|([^|}]+)").unwrap()),
        ("present participle of", Regex::new(r"(?i)\{\{present participle of\|en\|([^|}]+)").unwrap()),
        ("third-person singular of", Regex::new(r"(?i)\{\{(?:en-third-person singular of|third-person singular of)\|en\|([^|}]+)").unwrap()),

        // Adjective/adverb inflections
        ("comparative of", Regex::new(r"(?i)\{\{comparative of\|en\|([^|}]+)").unwrap()),
        ("superlative of", Regex::new(r"(?i)\{\{superlative of\|en\|([^|}]+)").unwrap()),

        // Generic inflection template (handles various forms)
        ("inflection of", Regex::new(r"(?i)\{\{inflection of\|en\|([^|}]+)").unwrap()),
    ];
}

fn is_englishlike(token: &str) -> bool {
    let normalized: String = token.nfc().collect();

    // Reject non-ASCII whitespace except ordinary space
    if normalized.chars().any(|ch| ch != ' ' && ch.is_whitespace()) {
        return false;
    }

    // Reject empty or only spaces
    if normalized.trim().is_empty() {
        return false;
    }

    let allowed_punct = ['\u{2019}', '\'', '\u{2018}', '-', '\u{2013}', '.', '/'];
    let forbidden = ['&', ';', '<', '>'];

    let mut saw_latin_letter = false;

    for ch in normalized.chars() {
        if ch == ' ' {
            continue;
        }

        if forbidden.contains(&ch) {
            return false;
        }

        if ch.is_ascii() {
            if ch.is_alphabetic() {
                saw_latin_letter = true;
            }
        } else {
            // Non-ASCII character - check if it's Latin-based
            if ch.is_alphabetic() {
                // Accept common Latin diacritics (À-ɏ range)
                if ch as u32 >= 0x00C0 && ch as u32 <= 0x024F {
                    saw_latin_letter = true;
                } else {
                    return false;
                }
            } else if allowed_punct.contains(&ch) {
                // Allow punctuation
            }
        }
    }

    saw_latin_letter
}

fn extract_english_section(text: &str) -> Option<String> {
    let english_match = ENGLISH_SECTION.find(text)?;
    let english_start = english_match.end();

    // Find next language section
    let next_section = LANGUAGE_SECTION
        .find_iter(&text[english_start..])
        .find(|m| {
            let lang = m.as_str().trim_matches('=').trim();
            !lang.eq_ignore_ascii_case("english")
        })
        .map(|m| english_start + m.start());

    Some(
        if let Some(end) = next_section {
            text[english_start..end].to_string()
        } else {
            text[english_start..].to_string()
        }
    )
}

/// Extract labels from a single definition line
fn extract_labels_from_line(line: &str) -> (Vec<String>, Vec<String>, Vec<String>, Vec<String>) {
    let mut register_tags = HashSet::new();
    let mut region_tags = HashSet::new();
    let mut domain_tags = HashSet::new();
    let mut temporal_tags = HashSet::new();

    // Extract from context labels in this line
    for cap in CONTEXT_LABEL.captures_iter(line) {
        for label in cap[1].split('|') {
            let label = label.trim().to_lowercase();

            if REGISTER_LABELS.contains(label.as_str()) {
                register_tags.insert(label);
            } else if TEMPORAL_LABELS.contains(label.as_str()) {
                temporal_tags.insert(label);
            } else if DOMAIN_LABELS.contains(label.as_str()) {
                domain_tags.insert(label);
            } else if let Some(&region_code) = REGION_LABELS.get(label.as_str()) {
                region_tags.insert(region_code.to_string());
            }
        }
    }

    // Convert to sorted vectors
    let mut register: Vec<String> = register_tags.into_iter().collect();
    let mut region: Vec<String> = region_tags.into_iter().collect();
    let mut domain: Vec<String> = domain_tags.into_iter().collect();
    let mut temporal: Vec<String> = temporal_tags.into_iter().collect();

    register.sort();
    region.sort();
    domain.sort();
    temporal.sort();

    (register, region, domain, temporal)
}

/// Parse POS sections and their definitions from English text
fn parse_pos_sections(english_text: &str) -> Vec<PosSection> {
    let mut sections = Vec::new();

    // Find all POS headers and their positions
    let headers: Vec<(usize, &str, bool)> = POS_HEADER
        .captures_iter(english_text)
        .filter_map(|cap| {
            let full_match = cap.get(0)?;
            let header_text = cap.get(1)?.as_str().to_lowercase();
            let header_normalized = header_text.split_whitespace().collect::<Vec<_>>().join(" ");

            // Check if it's a proper noun
            let is_proper = header_normalized.contains("proper noun") ||
                           header_normalized.contains("proper name");

            // Map to normalized POS
            if let Some(&mapped_pos) = POS_MAP.get(header_normalized.as_str()) {
                Some((full_match.start(), mapped_pos, is_proper))
            } else {
                None
            }
        })
        .map(|(pos, mapped, is_proper)| (pos, mapped, is_proper))
        .collect();

    // For each POS header, extract definitions until next header
    for i in 0..headers.len() {
        let (start_pos, pos, is_proper) = headers[i];
        let section_start = start_pos;
        let section_end = if i + 1 < headers.len() {
            headers[i + 1].0
        } else {
            english_text.len()
        };

        let section_text = &english_text[section_start..section_end];

        // Extract definition lines (lines starting with single #)
        let definitions: Vec<String> = DEFINITION_LINE
            .captures_iter(section_text)
            .map(|cap| cap[1].to_string())
            .collect();

        if !definitions.is_empty() {
            sections.push(PosSection {
                pos: pos.to_string(),
                is_proper_noun: is_proper,
                definitions,
            });
        }
    }

    sections
}

fn extract_syllable_count_from_hyphenation(text: &str) -> Option<usize> {
    let cap = HYPHENATION_TEMPLATE.captures(text)?;
    let content = cap[1].to_string();

    // Handle alternatives (||) - use first alternative
    let first_alt = content.split("||").next()?;

    // Parse pipe-separated segments
    let parts: Vec<&str> = first_alt.split('|').collect();

    // Filter syllables (exclude parameters and empty parts)
    let syllables: Vec<String> = parts
        .iter()
        .filter_map(|&part| {
            let part = part.trim();
            if part.is_empty() || part.contains('=') {
                None
            } else {
                Some(part.to_string())
            }
        })
        .collect();

    // Single-part templates with long unseparated text are likely incomplete
    if syllables.len() == 1 && syllables[0].len() > 3 {
        return None;
    }

    if syllables.is_empty() {
        None
    } else {
        Some(syllables.len())
    }
}

fn extract_syllable_count_from_rhymes(text: &str) -> Option<usize> {
    RHYMES_SYLLABLE
        .captures(text)
        .and_then(|cap| cap[1].parse::<usize>().ok())
}

fn extract_syllable_count_from_categories(text: &str) -> Option<usize> {
    SYLLABLE_CATEGORY
        .captures(text)
        .and_then(|cap| cap[1].parse::<usize>().ok())
}

/// Extract regional spelling variant from head lines
/// Looks for {{tlb|en|American spelling}} or similar patterns
fn extract_spelling_region(text: &str) -> Option<String> {
    for cap in TLB_TEMPLATE.captures_iter(text) {
        // Get all labels in this template
        for label in cap[1].split('|') {
            let label = label.trim().to_lowercase();
            // Check if this is a spelling variant label
            if let Some(&region) = SPELLING_LABELS.get(label.as_str()) {
                return Some(region.to_string());
            }
        }
    }
    None
}

/// Clean wiki markup from extracted lemma
/// Removes section anchors (#...), wiki links ([[...]]), and templates ({{...}})
fn clean_lemma(raw: &str) -> String {
    let mut result = raw.to_string();

    // Remove section anchors (e.g., "after#noun" -> "after")
    if let Some(hash_pos) = result.find('#') {
        result = result[..hash_pos].to_string();
    }

    // Remove wiki link syntax: [[target]] or [[target|display]] or [[:en:target]]
    // Extract just the target word
    while result.contains("[[") {
        if let Some(start) = result.find("[[") {
            if let Some(end) = result[start..].find("]]") {
                let link_content = &result[start + 2..start + end];
                // Handle [[target|display]] - take target
                // Handle [[:en:target]] - take target after last colon
                let cleaned = if link_content.contains('|') {
                    link_content.split('|').next().unwrap_or("")
                } else {
                    link_content
                };
                // Remove language prefix like ":en:"
                let cleaned = cleaned.trim_start_matches(':');
                let cleaned = if cleaned.contains(':') {
                    cleaned.rsplit(':').next().unwrap_or(cleaned)
                } else {
                    cleaned
                };
                result = format!("{}{}{}", &result[..start], cleaned, &result[start + end + 2..]);
            } else {
                // Malformed (no closing ]]) - remove from [[ to end of string
                result = result[..start].to_string();
            }
        }
    }

    // Remove any remaining ]]
    result = result.replace("]]", "");

    // Remove template syntax: {{...}} -> empty (nested templates shouldn't be in lemmas)
    while result.contains("{{") {
        if let Some(start) = result.find("{{") {
            if let Some(end) = result[start..].find("}}") {
                result = format!("{}{}", &result[..start], &result[start + end + 2..]);
            } else {
                // Malformed (no closing }}) - remove from {{ to end of string
                result = result[..start].to_string();
            }
        }
    }

    // Remove any remaining }}
    result = result.replace("}}", "");

    // Clean up any double slashes (from malformed templates)
    result = result.replace("//", "");

    result.trim().to_string()
}

/// Extract lemma (base form) from inflection templates
/// Returns the first matching lemma found in the text
fn extract_lemma(text: &str) -> Option<String> {
    for (_template_name, regex) in INFLECTION_TEMPLATES.iter() {
        if let Some(cap) = regex.captures(text) {
            let raw_lemma = cap[1].trim();
            let lemma = clean_lemma(raw_lemma).to_lowercase();
            // Validate the lemma is reasonable
            if !lemma.is_empty() && is_englishlike(&lemma) {
                return Some(lemma);
            }
        }
    }
    None
}

fn extract_phrase_type(text: &str) -> Option<String> {
    // Check section headers for specific phrase types
    for cap in POS_HEADER.captures_iter(text) {
        let header = cap[1].to_lowercase().trim().to_string();
        let header = header.split_whitespace().collect::<Vec<_>>().join(" ");

        match header.as_str() {
            "idiom" | "proverb" | "prepositional phrase" | "adverbial phrase" |
            "verb phrase" | "verb phrase form" | "noun phrase" => {
                return Some(header);
            }
            "saying" | "adage" => {
                return Some("proverb".to_string());
            }
            _ => {}
        }
    }

    // Check {{head}} templates
    for cap in HEAD_TEMPLATE.captures_iter(text) {
        let pos = cap[1].to_lowercase().trim().to_string();
        match pos.as_str() {
            "idiom" | "proverb" | "prepositional phrase" | "adverbial phrase" |
            "verb phrase" | "noun phrase" => {
                return Some(pos);
            }
            "saying" | "adage" => {
                return Some("proverb".to_string());
            }
            _ => {}
        }
    }

    // Check for phrase-specific templates
    if PREP_PHRASE_TEMPLATE.is_match(text) {
        return Some("prepositional phrase".to_string());
    }

    // Check categories
    let category_patterns = [
        ("Category:English idioms", "idiom"),
        ("Category:English proverbs", "proverb"),
        ("Category:English prepositional phrases", "prepositional phrase"),
        ("Category:English adverbial phrases", "adverbial phrase"),
        ("Category:English verb phrases", "verb phrase"),
        ("Category:English noun phrases", "noun phrase"),
        ("Category:English sayings", "proverb"),
    ];

    for (pattern, phrase_type) in &category_patterns {
        if text.contains(pattern) {
            return Some(phrase_type.to_string());
        }
    }

    None
}

fn clean_template_components(parts: &[&str]) -> Vec<String> {
    parts
        .iter()
        .filter_map(|part| {
            let part = part.trim();
            if part.is_empty() || part.contains('=') {
                return None;
            }
            if part.contains(':') && part.len() > 2 && part.chars().take(4).all(|c| c.is_ascii_lowercase() || c == ':') {
                return None;
            }
            Some(part.to_string())
        })
        .collect()
}

fn extract_morphology(text: &str) -> Option<Morphology> {
    let etym_match = ETYMOLOGY_SECTION.captures(text)?;
    let mut etymology_text = etym_match[1].to_string();

    if let Some(next_section) = NEXT_SECTION.find(&etymology_text) {
        etymology_text = etymology_text[..next_section.start()].to_string();
    }

    let etymology_text = etymology_text.as_str();

    // Try suffix template
    if let Some(cap) = SUFFIX_TEMPLATE.captures(etymology_text) {
        let base = cap[1].trim().to_string();
        let mut suffix = cap[2].trim().to_string();
        if !suffix.starts_with('-') {
            suffix = format!("-{}", suffix);
        }
        return Some(Morphology {
            morph_type: "suffixed".to_string(),
            base: Some(base.clone()),
            components: vec![base, suffix.clone()],
            prefixes: vec![],
            suffixes: vec![suffix],
            is_compound: false,
            etymology_template: cap[0].to_string(),
        });
    }

    // Try prefix template
    if let Some(cap) = PREFIX_TEMPLATE.captures(etymology_text) {
        let mut prefix = cap[1].trim().to_string();
        let base = cap[2].trim().to_string();
        if !prefix.ends_with('-') {
            prefix = format!("{}-", prefix);
        }
        return Some(Morphology {
            morph_type: "prefixed".to_string(),
            base: Some(base.clone()),
            components: vec![prefix.clone(), base],
            prefixes: vec![prefix],
            suffixes: vec![],
            is_compound: false,
            etymology_template: cap[0].to_string(),
        });
    }

    // Try confix template
    if let Some(cap) = CONFIX_TEMPLATE.captures(etymology_text) {
        let mut prefix = cap[1].trim().to_string();
        let base = cap[2].trim().to_string();
        let mut suffix = cap[3].trim().to_string();
        if !prefix.ends_with('-') {
            prefix = format!("{}-", prefix);
        }
        if !suffix.starts_with('-') {
            suffix = format!("-{}", suffix);
        }
        return Some(Morphology {
            morph_type: "circumfixed".to_string(),
            base: Some(base.clone()),
            components: vec![prefix.clone(), base, suffix.clone()],
            prefixes: vec![prefix],
            suffixes: vec![suffix],
            is_compound: false,
            etymology_template: cap[0].to_string(),
        });
    }

    // Try compound template
    if let Some(cap) = COMPOUND_TEMPLATE.captures(etymology_text) {
        let parts: Vec<&str> = cap[1].split('|').collect();
        let components = clean_template_components(&parts);
        if components.len() >= 2 {
            return Some(Morphology {
                morph_type: "compound".to_string(),
                base: None,
                components,
                prefixes: vec![],
                suffixes: vec![],
                is_compound: true,
                etymology_template: cap[0].to_string(),
            });
        }
    }

    // Try affix or surf templates
    for (template_re, _template_name) in [(&*AFFIX_TEMPLATE, "affix"), (&*SURF_TEMPLATE, "surf")] {
        if let Some(cap) = template_re.captures(etymology_text) {
            let parts: Vec<&str> = cap[1].split('|').collect();
            let components = clean_template_components(&parts);

            if components.len() >= 2 {
                let prefixes: Vec<String> = components
                    .iter()
                    .filter(|c| c.ends_with('-') && !c.starts_with('-'))
                    .cloned()
                    .collect();

                let suffixes: Vec<String> = components
                    .iter()
                    .filter(|c| c.starts_with('-') && !c.ends_with('-'))
                    .cloned()
                    .collect();

                let bases: Vec<String> = components
                    .iter()
                    .filter(|c| !c.starts_with('-') && !c.ends_with('-'))
                    .cloned()
                    .collect();

                let (morph_type, is_compound, base) = if !prefixes.is_empty() && !suffixes.is_empty() {
                    ("affixed", false, bases.first().cloned())
                } else if !prefixes.is_empty() {
                    ("prefixed", false, bases.first().cloned())
                } else if !suffixes.is_empty() {
                    ("suffixed", false, bases.first().cloned())
                } else if bases.len() >= 2 {
                    ("compound", true, None)
                } else {
                    continue;
                };

                return Some(Morphology {
                    morph_type: morph_type.to_string(),
                    base,
                    components,
                    prefixes,
                    suffixes,
                    is_compound,
                    etymology_template: cap[0].to_string(),
                });
            }
        }
    }

    None
}

/// Parse a page and return multiple entries (one per sense)
fn parse_page(title: &str, text: &str) -> Vec<Entry> {
    let word = title.to_lowercase().trim().to_string();

    // Extract English section
    let english_text = match extract_english_section(text) {
        Some(t) => t,
        None => return vec![],
    };

    // Extract word-level data (shared across all senses)
    let word_count = word.split_whitespace().count();
    let phrase_type = if word_count > 1 {
        extract_phrase_type(&english_text)
    } else {
        None
    };

    let syllables = extract_syllable_count_from_hyphenation(&english_text)
        .or_else(|| extract_syllable_count_from_rhymes(&english_text))
        .or_else(|| extract_syllable_count_from_categories(&english_text));

    let morphology = extract_morphology(&english_text);
    let is_abbreviation = ABBREVIATION_TEMPLATE.is_match(&english_text);
    // Extract lemma from inflection templates (e.g., {{plural of|en|cat}} → "cat")
    // Search in english_text only to avoid matching templates from other language sections
    let lemma = extract_lemma(&english_text);

    // Mark as inflected if we found a lemma OR if category indicates inflection
    let is_inflected = lemma.is_some()
        || english_text.contains("Category:English verb forms")
        || english_text.contains("Category:English noun forms")
        || english_text.contains("Category:English adjective forms")
        || english_text.contains("Category:English adverb forms")
        || english_text.contains("Category:English plurals");

    // Extract regional spelling variant (e.g., "American spelling", "British spelling")
    let spelling_region = extract_spelling_region(&english_text);

    let word_data = WordData {
        word: word.clone(),
        word_count,
        is_phrase: word_count > 1,
        is_abbreviation,
        is_inflected,
        lemma,
        phrase_type,
        syllables,
        morphology,
        spelling_region,
    };

    // Parse POS sections and their definitions
    let pos_sections = parse_pos_sections(&english_text);

    // If no POS sections found, try to create a single entry with unknown POS
    if pos_sections.is_empty() {
        // Check for English categories or templates as validation
        let has_categories = text.to_lowercase().contains("category:english");
        let has_en_templates = text.contains("{{en-");

        if has_categories || has_en_templates {
            // Create a single entry with unknown POS
            return vec![Entry {
                word: word_data.word,
                pos: "unknown".to_string(),
                register_tags: vec![],
                region_tags: vec![],
                domain_tags: vec![],
                temporal_tags: vec![],
                spelling_region: word_data.spelling_region,
                word_count: word_data.word_count,
                is_phrase: word_data.is_phrase,
                is_abbreviation: word_data.is_abbreviation,
                is_proper_noun: false,
                is_inflected: word_data.is_inflected,
                lemma: word_data.lemma,
                phrase_type: word_data.phrase_type,
                syllables: word_data.syllables,
                morphology: word_data.morphology,
            }];
        }
        return vec![];
    }

    // Create one entry per definition
    let mut entries = Vec::new();

    for section in pos_sections {
        for def_line in &section.definitions {
            let (register_tags, region_tags, domain_tags, temporal_tags) =
                extract_labels_from_line(def_line);

            entries.push(Entry {
                word: word_data.word.clone(),
                pos: section.pos.clone(),
                register_tags,
                region_tags,
                domain_tags,
                temporal_tags,
                spelling_region: word_data.spelling_region.clone(),
                word_count: word_data.word_count,
                is_phrase: word_data.is_phrase,
                is_abbreviation: word_data.is_abbreviation,
                is_proper_noun: section.is_proper_noun,
                is_inflected: word_data.is_inflected,
                lemma: word_data.lemma.clone(),
                phrase_type: word_data.phrase_type.clone(),
                syllables: word_data.syllables,
                morphology: word_data.morphology.clone(),
            });
        }
    }

    entries
}

fn scan_pages(mut reader: impl BufRead, mut callback: impl FnMut(String) -> bool) -> std::io::Result<()> {
    let mut buffer = String::new();
    let mut chunk = vec![0u8; 1024 * 1024]; // 1MB chunks

    loop {
        let bytes_read = reader.read(&mut chunk)?;
        if bytes_read == 0 {
            break;
        }

        buffer.push_str(&String::from_utf8_lossy(&chunk[..bytes_read]));

        // Extract complete pages
        while let Some(start) = buffer.find("<page>") {
            if let Some(end_offset) = buffer[start..].find("</page>") {
                let end = start + end_offset + "</page>".len();
                let page_xml = buffer[start..end].to_string();
                buffer.drain(..end);

                if !callback(page_xml) {
                    return Ok(());
                }
            } else {
                buffer.drain(..start);
                break;
            }
        }

        if buffer.len() > 10 && !buffer.contains("<page>") {
            buffer.drain(..buffer.len().saturating_sub(10));
        }
    }

    Ok(())
}

fn main() -> std::io::Result<()> {
    let args = Args::parse();

    println!("Parsing: {}", args.input.display());
    println!("Output: {}", args.output.display());
    println!("Method: Fast Rust scanner (per-sense output)");
    if let Some(limit) = args.limit {
        println!("Limit: {} entries", limit);
    }
    println!();

    let start_time = Instant::now();

    let file = File::open(&args.input)?;
    let reader: Box<dyn BufRead> = if args.input.to_string_lossy().ends_with(".bz2") {
        Box::new(BufReader::with_capacity(256 * 1024, BzDecoder::new(file)))
    } else {
        Box::new(BufReader::with_capacity(256 * 1024, file))
    };

    let output = File::create(&args.output)?;
    let mut writer = BufWriter::with_capacity(256 * 1024, output);

    let mut stats = Stats::default();
    let pb = ProgressBar::new_spinner();
    pb.set_style(
        ProgressStyle::default_spinner()
            .template("{spinner} {msg}")
            .unwrap()
    );

    let limit_reached = std::cell::Cell::new(false);

    scan_pages(reader, |page_xml| {
        if limit_reached.get() {
            return false;
        }

        stats.pages_processed += 1;

        if stats.pages_processed % 1000 == 0 {
            let elapsed = start_time.elapsed().as_secs_f64();
            let rate = stats.pages_processed as f64 / elapsed;
            pb.set_message(format!(
                "Pages: {} | Senses: {} | Words: {} | Rate: {:.0} pg/s",
                stats.pages_processed, stats.senses_written, stats.words_written, rate
            ));
        }

        // Extract title
        let title = match TITLE_PATTERN.captures(&page_xml) {
            Some(cap) => cap[1].to_string(),
            None => {
                stats.skipped += 1;
                return true;
            }
        };

        // Check namespace
        if let Some(cap) = NS_PATTERN.captures(&page_xml) {
            if &cap[1] != "0" {
                stats.special += 1;
                return true;
            }
        }

        // Check for special prefixes
        if SPECIAL_PREFIXES.iter().any(|prefix| title.starts_with(prefix)) {
            stats.special += 1;
            return true;
        }

        // Check for redirects
        if REDIRECT_PATTERN.is_match(&page_xml) {
            stats.redirects += 1;
            return true;
        }

        // Extract text
        let text = match TEXT_PATTERN.captures(&page_xml) {
            Some(cap) => cap[1].to_string(),
            None => {
                stats.skipped += 1;
                return true;
            }
        };

        // Check for English section
        if !ENGLISH_SECTION.is_match(&text) {
            stats.non_english += 1;
            return true;
        }

        // Check for dict-only
        if DICT_ONLY.is_match(&text) {
            stats.dict_only += 1;
            return true;
        }

        // Check if English-like
        if !is_englishlike(&title) {
            stats.non_latin += 1;
            return true;
        }

        // Parse page into multiple entries (one per sense)
        let entries = parse_page(&title, &text);

        if entries.is_empty() {
            stats.skipped += 1;
            return true;
        }

        stats.words_written += 1;

        for entry in entries {
            if let Ok(json) = serde_json::to_string(&entry) {
                writeln!(writer, "{}", json).ok();
                stats.senses_written += 1;

                if let Some(limit) = args.limit {
                    if stats.senses_written >= limit {
                        limit_reached.set(true);
                        return false;
                    }
                }
            }
        }

        true
    })?;

    writer.flush()?;

    if limit_reached.get() {
        pb.finish_with_message(format!("Reached limit of {} entries", args.limit.unwrap()));
    } else {
        pb.finish_and_clear();
    }

    let elapsed = start_time.elapsed();
    println!();
    println!("============================================================");
    println!("Pages processed: {}", stats.pages_processed);
    println!("Words written: {}", stats.words_written);
    println!("Senses written: {}", stats.senses_written);
    println!("Avg senses/word: {:.2}", stats.senses_written as f64 / stats.words_written.max(1) as f64);
    println!("Special pages: {}", stats.special);
    println!("Redirects: {}", stats.redirects);
    println!("Dictionary-only terms: {}", stats.dict_only);
    println!("Non-English pages: {}", stats.non_english);
    println!("Non-Latin scripts: {}", stats.non_latin);
    println!("Skipped: {}", stats.skipped);
    println!("Time: {}m {}s", elapsed.as_secs() / 60, elapsed.as_secs() % 60);
    println!("Rate: {:.0} pages/sec", stats.pages_processed as f64 / elapsed.as_secs_f64());
    println!("============================================================");

    Ok(())
}

#[derive(Default)]
struct Stats {
    pages_processed: usize,
    words_written: usize,
    senses_written: usize,
    special: usize,
    redirects: usize,
    dict_only: usize,
    non_english: usize,
    non_latin: usize,
    skipped: usize,
}
