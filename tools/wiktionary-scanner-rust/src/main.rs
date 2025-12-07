use bzip2::read::BzDecoder;
use clap::{Parser, ValueEnum};
use indicatif::{ProgressBar, ProgressStyle};
use lazy_static::lazy_static;
use once_cell::sync::OnceCell;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::fs::File;
use std::io::{BufRead, BufReader, BufWriter, Read, Write};
use std::path::PathBuf;
use std::time::{Duration, Instant};
use unicode_normalization::UnicodeNormalization;

mod parallel;
use parallel::{ParallelConfig, process_batch_parallel, process_channel_pipeline, process_two_phase};

/// Processing strategy for parsing
#[derive(Debug, Clone, Copy, PartialEq, Eq, ValueEnum)]
pub enum Strategy {
    /// Sequential processing (original baseline)
    Sequential,
    /// Batch-parallel processing with thread pool
    BatchParallel,
    /// Channel-based pipeline processing
    ChannelPipeline,
    /// Two-phase: load all pages, then process in parallel
    TwoPhase,
}

#[derive(Parser)]
#[command(name = "wiktionary-scanner-rust")]
#[command(about = "Fast Rust-based Wiktionary XML parser - outputs one entry per sense")]
struct Args {
    /// Input XML file (.xml or .xml.bz2)
    input: PathBuf,

    /// Output JSONL file
    output: PathBuf,

    /// Processing strategy
    #[arg(short, long, value_enum, default_value_t = Strategy::ChannelPipeline)]
    strategy: Strategy,

    /// Number of threads (4 = default, 0 = auto-detect)
    #[arg(short, long, default_value_t = 4)]
    threads: usize,

    /// Batch size for batch-parallel strategy
    #[arg(long, default_value_t = 1000)]
    batch_size: usize,

    /// Channel buffer size for channel-pipeline strategy
    #[arg(long, default_value_t = 10000)]
    channel_buffer: usize,

    /// Limit number of entries to extract (for testing)
    #[arg(long)]
    limit: Option<usize>,

    /// Limit number of pages to scan (for testing with raw dumps)
    #[arg(long)]
    page_limit: Option<usize>,

    /// Run all strategies and compare (benchmark mode)
    #[arg(long)]
    benchmark: bool,

    /// Quiet mode - minimal output
    #[arg(short, long)]
    quiet: bool,

    /// Syllable validation mode - outputs all syllable sources for cross-validation
    #[arg(long)]
    syllable_validation: bool,

    /// Path to POS schema YAML file (default: schema/pos.yaml relative to project root)
    #[arg(long)]
    schema: Option<PathBuf>,
}

// === POS Schema YAML structures ===

#[derive(Debug, Deserialize)]
struct PosSchema {
    pos_classes: Vec<PosClass>,
}

#[derive(Debug, Deserialize)]
struct PosClass {
    code: String,
    #[allow(dead_code)]
    name: String,
    #[allow(dead_code)]
    description: String,
    #[allow(dead_code)]
    short_description: Option<String>,
    variants: Vec<String>,
}

// Labels schema for label classifications
#[derive(Debug, Deserialize)]
struct LabelsSchema {
    register_labels: Vec<String>,
    temporal_labels: Vec<String>,
    domain_labels: Vec<String>,
    region_labels: HashMap<String, String>,
    spelling_labels: HashMap<String, String>,
    special_page_prefixes: Vec<String>,
}

// Global POS map loaded from YAML at runtime
static POS_MAP: OnceCell<HashMap<String, String>> = OnceCell::new();

// Global label sets loaded from YAML at runtime
static REGISTER_LABELS_SET: OnceCell<HashSet<String>> = OnceCell::new();
static TEMPORAL_LABELS_SET: OnceCell<HashSet<String>> = OnceCell::new();
static DOMAIN_LABELS_SET: OnceCell<HashSet<String>> = OnceCell::new();
static REGION_LABELS_MAP: OnceCell<HashMap<String, String>> = OnceCell::new();
static SPELLING_LABELS_MAP: OnceCell<HashMap<String, String>> = OnceCell::new();
static SPECIAL_PREFIXES_VEC: OnceCell<Vec<String>> = OnceCell::new();

fn load_pos_schema(schema_path: &PathBuf) -> Result<HashMap<String, String>, String> {
    let mut file = File::open(schema_path)
        .map_err(|e| format!("Failed to open schema file {:?}: {}", schema_path, e))?;

    let mut contents = String::new();
    file.read_to_string(&mut contents)
        .map_err(|e| format!("Failed to read schema file: {}", e))?;

    let schema: PosSchema = serde_yaml::from_str(&contents)
        .map_err(|e| format!("Failed to parse schema YAML: {}", e))?;

    let mut map = HashMap::new();
    for pos_class in schema.pos_classes {
        for variant in pos_class.variants {
            map.insert(variant, pos_class.code.clone());
        }
    }

    Ok(map)
}

fn init_pos_map(schema_path: Option<&PathBuf>) -> Result<(), String> {
    // Try to find schema file
    let path = if let Some(p) = schema_path {
        p.clone()
    } else {
        // Default: look for schema/pos.yaml relative to current dir or parent dirs
        let candidates = [
            PathBuf::from("schema/pos.yaml"),
            PathBuf::from("../../schema/pos.yaml"),  // When running from tools/wiktionary-scanner-rust
        ];
        candidates.into_iter()
            .find(|p| p.exists())
            .ok_or_else(|| "Could not find schema/pos.yaml. Use --schema to specify path.".to_string())?
    };

    let map = load_pos_schema(&path)?;
    POS_MAP.set(map).map_err(|_| "POS_MAP already initialized".to_string())?;
    Ok(())
}

fn get_pos_map() -> &'static HashMap<String, String> {
    POS_MAP.get().expect("POS_MAP not initialized - call init_pos_map() first")
}

fn find_schema_file(filename: &str) -> Result<PathBuf, String> {
    let candidates = [
        PathBuf::from(format!("schema/{}", filename)),
        PathBuf::from(format!("../../schema/{}", filename)),  // When running from tools/wiktionary-scanner-rust
    ];
    candidates.into_iter()
        .find(|p| p.exists())
        .ok_or_else(|| format!("Could not find schema/{}. Use --schema to specify path.", filename))
}

fn load_labels_schema(schema_path: &PathBuf) -> Result<LabelsSchema, String> {
    let mut file = File::open(schema_path)
        .map_err(|e| format!("Failed to open labels schema file {:?}: {}", schema_path, e))?;

    let mut contents = String::new();
    file.read_to_string(&mut contents)
        .map_err(|e| format!("Failed to read labels schema file: {}", e))?;

    serde_yaml::from_str(&contents)
        .map_err(|e| format!("Failed to parse labels schema YAML: {}", e))
}

fn init_labels(schema_path: Option<&PathBuf>) -> Result<(), String> {
    let path = if let Some(p) = schema_path {
        p.clone()
    } else {
        find_schema_file("labels.yaml")?
    };

    let schema = load_labels_schema(&path)?;

    REGISTER_LABELS_SET.set(schema.register_labels.into_iter().collect())
        .map_err(|_| "REGISTER_LABELS_SET already initialized".to_string())?;
    TEMPORAL_LABELS_SET.set(schema.temporal_labels.into_iter().collect())
        .map_err(|_| "TEMPORAL_LABELS_SET already initialized".to_string())?;
    DOMAIN_LABELS_SET.set(schema.domain_labels.into_iter().collect())
        .map_err(|_| "DOMAIN_LABELS_SET already initialized".to_string())?;
    REGION_LABELS_MAP.set(schema.region_labels)
        .map_err(|_| "REGION_LABELS_MAP already initialized".to_string())?;
    SPELLING_LABELS_MAP.set(schema.spelling_labels)
        .map_err(|_| "SPELLING_LABELS_MAP already initialized".to_string())?;
    SPECIAL_PREFIXES_VEC.set(schema.special_page_prefixes)
        .map_err(|_| "SPECIAL_PREFIXES_VEC already initialized".to_string())?;

    Ok(())
}

fn get_register_labels() -> &'static HashSet<String> {
    REGISTER_LABELS_SET.get().expect("Labels not initialized - call init_labels() first")
}

fn get_temporal_labels() -> &'static HashSet<String> {
    TEMPORAL_LABELS_SET.get().expect("Labels not initialized - call init_labels() first")
}

fn get_domain_labels() -> &'static HashSet<String> {
    DOMAIN_LABELS_SET.get().expect("Labels not initialized - call init_labels() first")
}

fn get_region_labels() -> &'static HashMap<String, String> {
    REGION_LABELS_MAP.get().expect("Labels not initialized - call init_labels() first")
}

fn get_spelling_labels() -> &'static HashMap<String, String> {
    SPELLING_LABELS_MAP.get().expect("Labels not initialized - call init_labels() first")
}

pub fn get_special_prefixes() -> &'static Vec<String> {
    SPECIAL_PREFIXES_VEC.get().expect("Labels not initialized - call init_labels() first")
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
    #[serde(skip_serializing_if = "Vec::is_empty")]
    interfixes: Vec<String>,
    is_compound: bool,
    etymology_template: String,
}

// Helper function for serde skip_serializing_if
fn is_false(b: &bool) -> bool {
    !*b
}

/// Flat entry structure - one per sense (definition line)
/// Field order is normalized for consistent JSON output across Python/Rust scanners
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Entry {
    // Core identifiers
    #[serde(rename = "id")]
    word: String,
    pos: String,  // Single POS, not Vec
    #[serde(rename = "wc")]
    word_count: usize,

    // Boolean predicates (alphabetical order) - omit when false
    #[serde(default, skip_serializing_if = "is_false")]
    is_abbreviation: bool,
    #[serde(default, skip_serializing_if = "is_false")]
    is_inflected: bool,
    #[serde(default, skip_serializing_if = "is_false")]
    is_phrase: bool,

    // Syllables and phrase type (before lemma)
    #[serde(rename = "nsyll", skip_serializing_if = "Option::is_none")]
    syllables: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    phrase_type: Option<String>,

    // Lemma (base form) for inflected words
    // Extracted from templates like {{plural of|en|cat}} → "cat"
    #[serde(skip_serializing_if = "Option::is_none")]
    lemma: Option<String>,

    // Tag arrays (alphabetical order)
    #[serde(skip_serializing_if = "Vec::is_empty")]
    domain_tags: Vec<String>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    region_tags: Vec<String>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    register_tags: Vec<String>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    temporal_tags: Vec<String>,

    // Regional spelling variant (e.g., "en-US" for American spelling, "en-GB" for British)
    #[serde(skip_serializing_if = "Option::is_none")]
    spelling_region: Option<String>,

    // Morphology (last)
    #[serde(skip_serializing_if = "Option::is_none")]
    morphology: Option<Morphology>,
}

/// Represents a POS section with its definitions
struct PosSection {
    pos: String,
    definitions: Vec<String>,  // Raw definition lines
}

/// Syllable validation record - shows all sources for cross-validation
#[derive(Debug, Serialize, Deserialize)]
struct SyllableValidation {
    #[serde(rename = "id")]
    word: String,
    rhymes: Option<usize>,
    ipa: Option<usize>,
    category: Option<usize>,
    hyphenation: Option<usize>,
    final_value: Option<usize>,
    has_disagreement: bool,
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
    pub static ref TITLE_PATTERN: Regex = Regex::new(r"<title>([^<]+)</title>").unwrap();
    pub static ref NS_PATTERN: Regex = Regex::new(r"<ns>(\d+)</ns>").unwrap();
    pub static ref TEXT_PATTERN: Regex = Regex::new(r"(?s)<text[^>]*>(.+?)</text>").unwrap();
    pub static ref REDIRECT_PATTERN: Regex = Regex::new(r#"<redirect\s+title="[^"]+""#).unwrap();

    // English section
    pub static ref ENGLISH_SECTION: Regex = Regex::new(r"(?i)==\s*English\s*==").unwrap();
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
    // Template-existence check for inflection detection (handles cases where lemma extraction fails)
    // This matches Python's detect_inflected_form() which just checks if templates exist
    static ref INFLECTION_TEMPLATE_EXISTS: Regex = Regex::new(r"(?i)\{\{(?:plural of|past tense of|past participle of|present participle of|comparative of|superlative of|inflection of)\|en\|").unwrap();
    pub static ref DICT_ONLY: Regex = Regex::new(r"(?i)\{\{no entry\|en").unwrap();

    // Definition-generating templates that indicate English content (even without POS headers)
    // These are tertiary validation signals for entries that have definitions but no POS headers
    static ref DEFINITION_TEMPLATES: Regex = Regex::new(r"(?i)\{\{(?:abbr of|abbreviation of|abbrev of|initialism of|acronym of|alternative form of|alt form|alt sp|plural of|past tense of|past participle of|present participle of|en-(?:noun|verb|adj|adv|past of))\|en\|").unwrap();

    // Syllable extraction patterns
    static ref HYPHENATION_TEMPLATE: Regex = Regex::new(r"(?i)\{\{(?:hyphenation|hyph)\|en\|([^}]+)\}\}").unwrap();
    static ref RHYMES_SYLLABLE: Regex = Regex::new(r"(?i)\{\{rhymes\|en\|[^}]*\|s=(\d+)").unwrap();
    static ref SYLLABLE_CATEGORY: Regex = Regex::new(r"(?i)\[\[Category:English\s+(\d+)-syllable\s+words?\]\]").unwrap();

    // IPA extraction pattern - matches {{IPA|en|/transcription/}} or {{IPA|en|[transcription]}}
    static ref IPA_TEMPLATE: Regex = Regex::new(r"(?i)\{\{IPA\|en\|([^}]+)\}\}").unwrap();
    // Extract transcription from slashes or brackets
    static ref IPA_TRANSCRIPTION: Regex = Regex::new(r"[/\[]([^/\[\]]+)[/\]]").unwrap();

    // Phrase type patterns
    static ref PREP_PHRASE_TEMPLATE: Regex = Regex::new(r"(?i)\{\{en-prepphr\b").unwrap();

    // Morphology/etymology patterns
    static ref ETYMOLOGY_SECTION: Regex = Regex::new(r"(?si)===+\s*Etymology\s*\d*\s*===+\s*\n(.+)").unwrap();
    static ref NEXT_SECTION: Regex = Regex::new(r"\n===").unwrap();
    static ref SUFFIX_TEMPLATE: Regex = Regex::new(r"(?i)\{\{suffix\|en\|([^}|]+)\|([^}|]+)(?:\|([^}|]+))?\}\}").unwrap();
    static ref PREFIX_TEMPLATE: Regex = Regex::new(r"(?i)\{\{prefix\|en\|([^}|]+)\|([^}|]+)(?:\|([^}|]+))?\}\}").unwrap();
    // Matches both {{affix|en|...}} and {{af|en|...}} (common shorthand)
    static ref AFFIX_TEMPLATE: Regex = Regex::new(r"(?i)\{\{af(?:fix)?\|en\|([^}]+)\}\}").unwrap();
    static ref COMPOUND_TEMPLATE: Regex = Regex::new(r"(?i)\{\{compound\|en\|([^}]+)\}\}").unwrap();
    static ref SURF_TEMPLATE: Regex = Regex::new(r"(?i)\{\{surf\|en\|([^}]+)\}\}").unwrap();
    static ref CONFIX_TEMPLATE: Regex = Regex::new(r"(?i)\{\{confix\|en\|([^}|]+)\|([^}|]+)\|([^}|]+)(?:\|([^}|]+))?\}\}").unwrap();
    // Language code prefix pattern (e.g., "pt:", "grc:", "ang:") - matches Python's LANG_CODE_PREFIX
    static ref LANG_CODE_PREFIX: Regex = Regex::new(r"(?i)^[a-z]{2,4}:").unwrap();
    // Wikilink pattern - matches [[word]] or [[word|display]] and extracts the target
    // Used to strip wikilink markup from morphology components
    static ref WIKILINK_PATTERN: Regex = Regex::new(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]").unwrap();

    // POS_MAP and label sets are now loaded from schema/*.yaml at runtime
    // via init_pos_map() and init_labels()

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

pub fn is_englishlike(token: &str) -> bool {
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
            let cp = ch as u32;
            if ch.is_alphabetic() {
                // Accept common Latin diacritics (À-ɏ range)
                if cp >= 0x00C0 && cp <= 0x024F {
                    saw_latin_letter = true;
                } else {
                    return false;
                }
            } else if allowed_punct.contains(&ch) {
                // Allow punctuation
            } else {
                // Reject combining diacritical marks (U+0300-U+036F) and emojis
                // to match Python scanner behavior
                if (0x0300..=0x036F).contains(&cp) {
                    return false;
                }
                if cp > 0xFFFF || (0x1F000..=0x1FFFF).contains(&cp) {
                    return false;
                }
                // Other non-alphabetic non-punctuation chars pass through
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
    let register_labels = get_register_labels();
    let temporal_labels = get_temporal_labels();
    let domain_labels = get_domain_labels();
    let region_labels = get_region_labels();

    for cap in CONTEXT_LABEL.captures_iter(line) {
        for label in cap[1].split('|') {
            let label = label.trim().to_lowercase();

            if register_labels.contains(&label) {
                register_tags.insert(label);
            } else if temporal_labels.contains(&label) {
                temporal_tags.insert(label);
            } else if domain_labels.contains(&label) {
                domain_tags.insert(label);
            } else if let Some(region_code) = region_labels.get(&label) {
                region_tags.insert(region_code.clone());
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
    let headers: Vec<(usize, &str)> = POS_HEADER
        .captures_iter(english_text)
        .filter_map(|cap| {
            let full_match = cap.get(0)?;
            let header_text = cap.get(1)?.as_str().to_lowercase();
            let header_normalized = header_text.split_whitespace().collect::<Vec<_>>().join(" ");

            // Map to normalized POS (proper noun -> proper, etc.)
            if let Some(mapped_pos) = get_pos_map().get(header_normalized.as_str()) {
                Some((full_match.start(), mapped_pos.as_str()))
            } else {
                None
            }
        })
        .collect();

    // For each POS header, extract definitions until next header
    for i in 0..headers.len() {
        let (start_pos, pos) = headers[i];
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

/// Count syllables from IPA transcription
/// Counts vowel nuclei (monophthongs and diphthongs) plus syllabic consonants
fn count_syllables_from_ipa(ipa: &str) -> usize {
    let mut count = 0;
    let chars: Vec<char> = ipa.chars().collect();
    let mut i = 0;

    // IPA vowels (monophthongs) - includes common English vowels and their variants
    let vowels: &[char] = &[
        'i', 'ɪ', 'e', 'ɛ', 'æ', 'a', 'ɑ', 'ɒ', 'ɔ', 'o', 'ʊ', 'u', 'ʌ', 'ə', 'ɜ', 'ɝ', 'ɐ',
        'ᵻ', 'ᵿ', // barred vowels (used in some transcriptions)
        'ɚ',      // rhotic schwa (American English, as in "butter" /bʌtɚ/)
    ];

    // Syllabic consonant marker (combining character U+0329)
    let syllabic_marker = '\u{0329}';

    while i < chars.len() {
        let ch = chars[i];

        // Check for syllabic consonant (consonant followed by syllabic marker)
        if i + 1 < chars.len() && chars[i + 1] == syllabic_marker {
            count += 1;
            i += 2; // Skip consonant and marker
            continue;
        }

        // Check for vowel
        if vowels.contains(&ch) {
            count += 1;
            i += 1;

            // Skip diphthong off-glides and modifiers
            // Only skip high/central vowels (ɪ, ʊ, ə) that serve as off-glides
            // Don't skip full vowels like æ, ɛ, ɔ which start new syllables
            let offglides: &[char] = &['ɪ', 'ʊ', 'ə', 'ɐ'];
            let mut vowel_skipped = false;
            while i < chars.len() {
                let next = chars[i];
                if next == 'ː'  // length marker
                    || next == 'ˑ'  // half-long
                    || next == '\u{0303}'  // combining tilde (nasalization)
                    || next == '\u{032F}'  // combining inverted breve (non-syllabic)
                    || next == '\u{0361}'  // combining double inverted breve (tie bar)
                    || next == '̯'  // non-syllabic diacritic
                {
                    i += 1;
                } else if !vowel_skipped && offglides.contains(&next) {
                    // Skip off-glide vowels (second element of diphthongs)
                    vowel_skipped = true;
                    i += 1;
                } else {
                    break;
                }
            }
            continue;
        }

        i += 1;
    }

    count
}

/// Extract syllable count from IPA transcription
fn extract_syllable_count_from_ipa(text: &str) -> Option<usize> {
    // Find IPA template
    let cap = IPA_TEMPLATE.captures(text)?;
    let template_content = &cap[1];

    // Extract the first transcription (between / / or [ ])
    let transcription = IPA_TRANSCRIPTION.captures(template_content)?;
    let ipa = &transcription[1];

    // Count syllables
    let count = count_syllables_from_ipa(ipa);

    // Return None for implausible counts (0 or very high)
    if count == 0 || count > 15 {
        None
    } else {
        Some(count)
    }
}

/// Extract syllable validation data from a page (for cross-validation analysis)
fn extract_syllable_validation(title: &str, text: &str) -> Option<SyllableValidation> {
    // Extract English section
    let english_text = extract_english_section(text)?;

    // Get all syllable counts from different sources
    let rhymes = extract_syllable_count_from_rhymes(&english_text);
    let ipa = extract_syllable_count_from_ipa(&english_text);
    let category = extract_syllable_count_from_categories(&english_text);
    let hyphenation = extract_syllable_count_from_hyphenation(&english_text);

    // If no syllable data at all, skip
    if rhymes.is_none() && ipa.is_none() && category.is_none() && hyphenation.is_none() {
        return None;
    }

    // Calculate final value using priority order
    let final_value = rhymes
        .or(ipa)
        .or(category)
        .or(hyphenation);

    // Check for disagreement - collect all non-None values and compare
    let values: Vec<usize> = [rhymes, ipa, category, hyphenation]
        .iter()
        .filter_map(|&v| v)
        .collect();

    let has_disagreement = if values.len() <= 1 {
        false
    } else {
        let first = values[0];
        values.iter().any(|&v| v != first)
    };

    Some(SyllableValidation {
        word: title.to_string(),
        rhymes,
        ipa,
        category,
        hyphenation,
        final_value,
        has_disagreement,
    })
}

/// Extract regional spelling variant from head lines
/// Looks for {{tlb|en|American spelling}} or similar patterns
fn extract_spelling_region(text: &str) -> Option<String> {
    let spelling_labels = get_spelling_labels();
    for cap in TLB_TEMPLATE.captures_iter(text) {
        // Get all labels in this template
        for label in cap[1].split('|') {
            let label = label.trim().to_lowercase();
            // Check if this is a spelling variant label
            if let Some(region) = spelling_labels.get(&label) {
                return Some(region.clone());
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

// ─────────────────────────────────────────────────────────────────────────────
// Wikitext Recursive Descent Parser
// ─────────────────────────────────────────────────────────────────────────────

/// Parsed wikilink: [[target#anchor|display]]
/// Note: anchor is parsed for completeness but not currently used
#[derive(Debug)]
#[allow(dead_code)]
struct Wikilink {
    target: String,
    anchor: Option<String>,
    display: Option<String>,
}

impl Wikilink {
    /// Return display text if present, otherwise target
    fn text(&self) -> &str {
        self.display.as_deref().unwrap_or(&self.target)
    }
}

/// Parsed template: {{name|param1|param2|...}}
/// Note: Nested templates are parsed but discarded (treated as metadata)
#[derive(Debug)]
#[allow(dead_code)]
struct ParsedTemplate {
    name: String,
    params: Vec<String>,
}

/// Recursive descent parser for Wiktionary template parameters.
/// Uses the call stack for nesting - no explicit depth counters.
struct WikitextParser<'a> {
    text: &'a str,
    pos: usize,
}

impl<'a> WikitextParser<'a> {
    fn new(text: &'a str) -> Self {
        WikitextParser { text, pos: 0 }
    }

    fn peek(&self, n: usize) -> &str {
        // n is character count, not byte count
        let remaining = &self.text[self.pos..];
        let end_offset: usize = remaining.chars().take(n).map(|c| c.len_utf8()).sum();
        &remaining[..end_offset]
    }

    fn peek_char(&self) -> Option<char> {
        self.text[self.pos..].chars().next()
    }

    fn consume(&mut self, n: usize) -> &str {
        // n is character count, not byte count
        let remaining = &self.text[self.pos..];
        let byte_len: usize = remaining.chars().take(n).map(|c| c.len_utf8()).sum();
        let result = &self.text[self.pos..self.pos + byte_len];
        self.pos += byte_len;
        result
    }

    fn consume_char(&mut self) -> Option<char> {
        let c = self.peek_char()?;
        self.pos += c.len_utf8();
        Some(c)
    }

    fn at_end(&self) -> bool {
        self.pos >= self.text.len()
    }

    // ─────────────────────────────────────────────────────────────
    // Top-level entry point: params ::= param ("|" param)*
    // ─────────────────────────────────────────────────────────────
    fn parse_params(&mut self) -> Vec<String> {
        let mut params = Vec::new();
        while !self.at_end() {
            let param = self.parse_param();
            params.push(param);
            if self.peek(1) == "|" {
                self.consume(1);
            } else {
                break;
            }
        }
        params
    }

    // ─────────────────────────────────────────────────────────────
    // param ::= element*  (terminated by | or end)
    // ─────────────────────────────────────────────────────────────
    fn parse_param(&mut self) -> String {
        let mut result = String::new();
        while !self.at_end() && self.peek(1) != "|" {
            if self.peek(2) == "[[" {
                let wikilink = self.parse_wikilink();
                result.push_str(wikilink.text());
            } else if self.peek(2) == "{{" {
                let template = self.parse_template();
                // For morphology params, nested templates are metadata - discard
                let _ = template;
            } else {
                if let Some(c) = self.consume_char() {
                    result.push(c);
                }
            }
        }
        result.trim().to_string()
    }

    // ─────────────────────────────────────────────────────────────
    // wikilink ::= "[[" target ("#" anchor)? ("|" display)? "]]"
    // ─────────────────────────────────────────────────────────────
    fn parse_wikilink(&mut self) -> Wikilink {
        self.consume(2); // consume "[["

        let target = self.parse_target();
        let mut anchor = None;
        let mut display = None;

        // Optional: "#" anchor
        if self.peek(1) == "#" {
            self.consume(1);
            anchor = Some(self.parse_anchor());
        }

        // Optional: "|" display
        if self.peek(1) == "|" {
            self.consume(1);
            display = Some(self.parse_display());
        }

        // Consume "]]"
        if self.peek(2) == "]]" {
            self.consume(2);
        }

        Wikilink { target, anchor, display }
    }

    fn parse_target(&mut self) -> String {
        let mut result = String::new();
        while !self.at_end() {
            let c = self.peek_char();
            match c {
                Some('#') | Some('|') | Some(']') => break,
                Some(ch) => {
                    self.consume_char();
                    result.push(ch);
                }
                None => break,
            }
        }
        result
    }

    fn parse_anchor(&mut self) -> String {
        let mut result = String::new();
        while !self.at_end() {
            let c = self.peek_char();
            match c {
                Some('|') | Some(']') => break,
                Some(ch) => {
                    self.consume_char();
                    result.push(ch);
                }
                None => break,
            }
        }
        result
    }

    fn parse_display(&mut self) -> String {
        let mut result = String::new();
        while !self.at_end() && self.peek(1) != "]" {
            if let Some(c) = self.consume_char() {
                result.push(c);
            }
        }
        result
    }

    // ─────────────────────────────────────────────────────────────
    // template ::= "{{" params "}}"
    // ─────────────────────────────────────────────────────────────
    fn parse_template(&mut self) -> ParsedTemplate {
        self.consume(2); // consume "{{"

        let params = self.parse_template_params_inner();

        if self.peek(2) == "}}" {
            self.consume(2);
        }

        let name = params.first().cloned().unwrap_or_default();
        let params = params.into_iter().skip(1).collect();
        ParsedTemplate { name, params }
    }

    fn parse_template_params_inner(&mut self) -> Vec<String> {
        let mut params = Vec::new();
        while !self.at_end() && self.peek(2) != "}}" {
            let param = self.parse_template_param_inner();
            params.push(param);
            if self.peek(1) == "|" {
                self.consume(1);
            } else {
                break;
            }
        }
        params
    }

    fn parse_template_param_inner(&mut self) -> String {
        let mut result = String::new();
        while !self.at_end() && self.peek(1) != "|" && self.peek(2) != "}}" {
            if self.peek(2) == "[[" {
                let wikilink = self.parse_wikilink();
                result.push_str(wikilink.text());
            } else if self.peek(2) == "{{" {
                let template = self.parse_template(); // RECURSIVE!
                // Nested templates produce no text for our purposes
                let _ = template;
            } else {
                if let Some(c) = self.consume_char() {
                    result.push(c);
                }
            }
        }
        result.trim().to_string()
    }
}

/// Parse template parameters with proper bracket handling.
fn parse_template_params(content: &str) -> Vec<String> {
    let mut parser = WikitextParser::new(content);
    parser.parse_params()
}

fn clean_template_components(parts: &[String]) -> Vec<String> {
    // Regex to strip XML/HTML tags like <id:...>, <t:...>, etc.
    let tag_pattern = Regex::new(r"<[^>]+>").unwrap();

    // Note: Wikilink handling ([[...]]) is now done by WikitextParser during parsing,
    // so this function only handles post-parsing cleanup.
    parts
        .iter()
        .filter_map(|part| {
            let mut part = part.trim().to_string();
            if part.is_empty() || part.contains('=') {
                return None;
            }
            // Skip language code prefixes (grc:, la:, ang:, pt:, etc.) at start of part
            // These indicate non-English etymological roots
            if LANG_CODE_PREFIX.is_match(&part) {
                return None;
            }
            // Decode HTML entities
            if part.contains("&lt;") || part.contains("&gt;") || part.contains("&amp;") {
                part = part.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&");
            }
            // Remove XML/HTML tags like <id:...>, <t:...>, etc.
            if part.contains('<') || part.contains('>') {
                part = tag_pattern.replace_all(&part, "").to_string();
                if part.is_empty() {
                    return None;
                }
            }
            Some(part)
        })
        .collect()
}

/// Strip wikilink markup from a string: [[word]] -> word, [[word|display]] -> word
fn strip_wikilinks(s: &str) -> String {
    if s.contains("[[") || s.contains("]]") {
        let result = WIKILINK_PATTERN.replace_all(s, "$1").to_string();
        result.replace("]]", "")
    } else {
        s.to_string()
    }
}

/// Classify morphology components and build a unified Morphology result.
///
/// Classification is purely based on hyphen patterns:
/// - Ends with '-' (but doesn't start with '-'): prefix
/// - Starts with '-' (but doesn't end with '-'): suffix
/// - Starts and ends with '-': interfix
/// - No hyphens: base word
fn classify_morphology(components: Vec<String>, etymology_template: String) -> Morphology {
    // Classify components by hyphen pattern in a single pass
    let (prefixes, suffixes, interfixes, bases) = components.iter().fold(
        (Vec::new(), Vec::new(), Vec::new(), Vec::new()),
        |(mut pre, mut suf, mut inter, mut base), c| {
            match (c.starts_with('-'), c.ends_with('-')) {
                (false, true) => pre.push(c.clone()),   // prefix: "un-"
                (true, false) => suf.push(c.clone()),   // suffix: "-ness"
                (true, true) => inter.push(c.clone()),  // interfix: "-s-"
                (false, false) => base.push(c.clone()), // base: "happy"
            }
            (pre, suf, inter, base)
        },
    );

    // Determine morphology type based on what we found
    let has_prefix = !prefixes.is_empty();
    let has_suffix = !suffixes.is_empty();

    let (morph_type, is_compound) = match (has_prefix, has_suffix) {
        (true, true) => ("affixed", false),
        (true, false) => ("prefixed", false),
        (false, true) => ("suffixed", false),
        (false, false) if bases.len() >= 2 => ("compound", true),
        _ => ("simple", false),
    };

    // Determine base word
    // For derivations: first base word is the root
    // For compounds: no single base (all parts are equal constituents)
    let base = if !is_compound { bases.first().cloned() } else { None };

    Morphology {
        morph_type: morph_type.to_string(),
        base,
        components,
        prefixes,
        suffixes,
        interfixes,
        is_compound,
        etymology_template,
    }
}

/// Extract normalized morphology components from any etymology template.
///
/// Tries each template type in priority order and normalizes to a common
/// component format where affixes are marked with hyphens.
///
/// Returns (components, raw_template) or None if no template found.
fn extract_morphology_components(etymology_text: &str) -> Option<(Vec<String>, String)> {
    // 1. Try suffix template: {{suffix|en|base|suffix}}
    if let Some(cap) = SUFFIX_TEMPLATE.captures(etymology_text) {
        let base = strip_wikilinks(cap[1].trim());
        let mut suffix = strip_wikilinks(cap[2].trim());
        // Normalize: add leading hyphen if missing
        if !suffix.starts_with('-') {
            suffix = format!("-{}", suffix);
        }
        return Some((vec![base, suffix], cap[0].to_string()));
    }

    // 2. Try prefix template: {{prefix|en|prefix|base}}
    if let Some(cap) = PREFIX_TEMPLATE.captures(etymology_text) {
        let mut prefix = strip_wikilinks(cap[1].trim());
        let base = strip_wikilinks(cap[2].trim());
        // Normalize: add trailing hyphen if missing
        if !prefix.ends_with('-') {
            prefix = format!("{}-", prefix);
        }
        return Some((vec![prefix, base], cap[0].to_string()));
    }

    // 3. Try confix template: {{confix|en|prefix|base|suffix}}
    if let Some(cap) = CONFIX_TEMPLATE.captures(etymology_text) {
        let mut prefix = strip_wikilinks(cap[1].trim());
        let base = strip_wikilinks(cap[2].trim());
        let mut suffix = strip_wikilinks(cap[3].trim());
        // Normalize affix hyphens
        if !prefix.ends_with('-') {
            prefix = format!("{}-", prefix);
        }
        if !suffix.starts_with('-') {
            suffix = format!("-{}", suffix);
        }
        return Some((vec![prefix, base, suffix], cap[0].to_string()));
    }

    // 4-6. Try variable-arg templates: compound, affix, surf
    // These use parse_template_params for bracket-aware parsing
    for template_re in [&*COMPOUND_TEMPLATE, &*AFFIX_TEMPLATE, &*SURF_TEMPLATE] {
        if let Some(cap) = template_re.captures(etymology_text) {
            let parts = parse_template_params(&cap[1]);
            let components = clean_template_components(&parts);
            if components.len() >= 2 {
                return Some((components, cap[0].to_string()));
            }
        }
    }

    None
}

/// Extract morphological structure from Wiktionary etymology sections.
///
/// This is the main entry point for morphology extraction. It uses a unified
/// approach that:
/// 1. Extracts and normalizes components from any morphology template
/// 2. Classifies the morphology type based on hyphen patterns
fn extract_morphology(text: &str) -> Option<Morphology> {
    let etym_match = ETYMOLOGY_SECTION.captures(text)?;
    let mut etymology_text = etym_match[1].to_string();

    if let Some(next_section) = NEXT_SECTION.find(&etymology_text) {
        etymology_text = etymology_text[..next_section.start()].to_string();
    }

    let etymology_text = etymology_text.as_str();

    // Extract and normalize components from any template type
    let (components, template_str) = extract_morphology_components(etymology_text)?;

    // Special case: confix template should be classified as 'circumfixed'
    // We detect this by checking if the template is confix
    if template_str.to_lowercase().contains("confix") {
        // Build circumfixed result directly
        let prefix = components.get(0).cloned().unwrap_or_default();
        let base = components.get(1).cloned();
        let suffix = components.get(2).cloned();

        return Some(Morphology {
            morph_type: "circumfixed".to_string(),
            base,
            components,
            prefixes: vec![prefix],
            suffixes: suffix.map(|s| vec![s]).unwrap_or_default(),
            interfixes: vec![],
            is_compound: false,
            etymology_template: template_str,
        });
    }

    // Classify morphology based on component hyphen patterns
    Some(classify_morphology(components, template_str))
}

/// Parse a page and return multiple entries (one per sense)
pub fn parse_page(title: &str, text: &str) -> Vec<Entry> {
    // Preserve original case - downstream consumers can filter by case pattern as needed
    let word = title.trim().to_string();

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

    // Priority order: rhymes (explicit) > IPA (parsed) > categories > hyphenation (least reliable)
    let syllables = extract_syllable_count_from_rhymes(&english_text)
        .or_else(|| extract_syllable_count_from_ipa(&english_text))
        .or_else(|| extract_syllable_count_from_categories(&english_text))
        .or_else(|| extract_syllable_count_from_hyphenation(&english_text));

    let morphology = extract_morphology(&english_text);
    // Detect abbreviations via templates only
    // Note: Category checks like 'Category:English acronyms' have false positives
    // because [[:Category:...]] links (to the category page) look similar to
    // [[Category:...]] membership. Template-based detection is more reliable.
    let is_abbreviation = ABBREVIATION_TEMPLATE.is_match(&english_text);
    // Extract lemma from inflection templates (e.g., {{plural of|en|cat}} → "cat")
    // Search in english_text only to avoid matching templates from other language sections
    let lemma = extract_lemma(&english_text);

    // Mark as inflected if we found a lemma OR if inflection template exists OR if category indicates inflection
    // The template-existence check handles cases like {{inflection of|en|[[link|word]]}} where
    // the lemma extraction fails due to complex wiki syntax but the template is present
    let is_inflected = lemma.is_some()
        || INFLECTION_TEMPLATE_EXISTS.is_match(&english_text)
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
        let has_categories = english_text.to_lowercase().contains("category:english");
        let has_en_templates = english_text.contains("{{en-noun")
            || english_text.contains("{{en-verb")
            || english_text.contains("{{en-adj")
            || english_text.contains("{{en-adv");
        let has_definition_templates = DEFINITION_TEMPLATES.is_match(&english_text);

        if has_categories || has_en_templates || has_definition_templates {
            // Create a single entry with unknown POS
            return vec![Entry {
                word: word_data.word,
                pos: "unknown".to_string(),
                word_count: word_data.word_count,
                is_abbreviation: word_data.is_abbreviation,
                is_inflected: word_data.is_inflected,
                is_phrase: word_data.is_phrase,
                syllables: word_data.syllables,
                phrase_type: word_data.phrase_type,
                lemma: word_data.lemma,
                domain_tags: vec![],
                region_tags: vec![],
                register_tags: vec![],
                temporal_tags: vec![],
                spelling_region: word_data.spelling_region,
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
                word_count: word_data.word_count,
                is_abbreviation: word_data.is_abbreviation,
                is_inflected: word_data.is_inflected,
                is_phrase: word_data.is_phrase,
                syllables: word_data.syllables,
                phrase_type: word_data.phrase_type.clone(),
                lemma: word_data.lemma.clone(),
                domain_tags,
                region_tags,
                register_tags,
                temporal_tags,
                spelling_region: word_data.spelling_region.clone(),
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

/// Run sequential processing (original baseline)
fn run_sequential(
    reader: impl BufRead,
    writer: &mut BufWriter<File>,
    limit: Option<usize>,
    quiet: bool,
) -> std::io::Result<Stats> {
    let start_time = Instant::now();
    let mut stats = Stats::default();

    let pb = if quiet {
        ProgressBar::hidden()
    } else {
        let pb = ProgressBar::new_spinner();
        pb.set_style(
            ProgressStyle::default_spinner()
                .template("{spinner} {msg}")
                .unwrap()
        );
        pb
    };

    let limit_reached = std::cell::Cell::new(false);

    scan_pages(reader, |page_xml| {
        if limit_reached.get() {
            return false;
        }

        stats.pages_processed += 1;

        if !quiet && stats.pages_processed % 1000 == 0 {
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
        if get_special_prefixes().iter().any(|prefix| title.starts_with(prefix)) {
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

        // Track case distribution for reporting
        match classify_case(&title) {
            CaseForm::Lower => stats.case_lower += 1,
            CaseForm::Title => stats.case_title += 1,
            CaseForm::Upper => stats.case_upper += 1,
            CaseForm::Mixed => stats.case_mixed += 1,
        }

        for entry in entries {
            if let Ok(json) = serde_json::to_string(&entry) {
                writeln!(writer, "{}", json).ok();
                stats.senses_written += 1;

                if let Some(l) = limit {
                    if stats.senses_written >= l {
                        limit_reached.set(true);
                        return false;
                    }
                }
            }
        }

        true
    })?;

    writer.flush()?;

    if limit_reached.get() && !quiet {
        pb.finish_with_message(format!("Reached limit of {} entries", limit.unwrap()));
    } else {
        pb.finish_and_clear();
    }

    stats.elapsed = start_time.elapsed();
    Ok(stats)
}

/// Run syllable validation mode - extract all syllable sources for cross-validation
fn run_syllable_validation(
    reader: impl BufRead,
    writer: &mut BufWriter<File>,
    page_limit: Option<usize>,
    quiet: bool,
) -> std::io::Result<SyllableValidationStats> {
    let start_time = Instant::now();
    let mut stats = SyllableValidationStats::default();

    let pb = if quiet {
        ProgressBar::hidden()
    } else {
        let pb = ProgressBar::new_spinner();
        pb.set_style(
            ProgressStyle::default_spinner()
                .template("{spinner} {msg}")
                .unwrap()
        );
        pb
    };

    let limit_reached = std::cell::Cell::new(false);

    scan_pages(reader, |page_xml| {
        if limit_reached.get() {
            return false;
        }

        stats.pages_scanned += 1;

        // Check page limit
        if let Some(limit) = page_limit {
            if stats.pages_scanned >= limit {
                limit_reached.set(true);
                return false;
            }
        }

        if !quiet && stats.pages_scanned % 10000 == 0 {
            let elapsed = start_time.elapsed().as_secs_f64();
            let rate = stats.pages_scanned as f64 / elapsed;
            pb.set_message(format!(
                "Pages: {} | With syllables: {} | Disagreements: {} | Rate: {:.0} pg/s",
                stats.pages_scanned, stats.words_with_syllables, stats.disagreements, rate
            ));
        }

        // Extract title
        let title = match TITLE_PATTERN.captures(&page_xml) {
            Some(cap) => cap[1].to_string(),
            None => return true,
        };

        // Check namespace
        if let Some(cap) = NS_PATTERN.captures(&page_xml) {
            if &cap[1] != "0" {
                return true;
            }
        }

        // Check for special prefixes
        if get_special_prefixes().iter().any(|prefix| title.starts_with(prefix)) {
            return true;
        }

        // Check for redirects
        if REDIRECT_PATTERN.is_match(&page_xml) {
            return true;
        }

        // Extract text
        let text = match TEXT_PATTERN.captures(&page_xml) {
            Some(cap) => cap[1].to_string(),
            None => return true,
        };

        // Check for English section
        if !ENGLISH_SECTION.is_match(&text) {
            return true;
        }

        // Check if English-like
        if !is_englishlike(&title) {
            return true;
        }

        // Extract syllable validation data
        if let Some(validation) = extract_syllable_validation(&title, &text) {
            stats.words_with_syllables += 1;

            // Track source coverage
            if validation.rhymes.is_some() { stats.has_rhymes += 1; }
            if validation.ipa.is_some() { stats.has_ipa += 1; }
            if validation.category.is_some() { stats.has_category += 1; }
            if validation.hyphenation.is_some() { stats.has_hyphenation += 1; }

            if validation.has_disagreement {
                stats.disagreements += 1;
            }

            // Write the validation record
            if let Ok(json) = serde_json::to_string(&validation) {
                writeln!(writer, "{}", json).ok();
            }
        }

        true
    })?;

    writer.flush()?;

    if limit_reached.get() && !quiet {
        pb.finish_with_message(format!("Reached page limit of {}", page_limit.unwrap()));
    } else {
        pb.finish_and_clear();
    }

    stats.elapsed = start_time.elapsed();
    Ok(stats)
}

#[derive(Default)]
struct SyllableValidationStats {
    pages_scanned: usize,
    words_with_syllables: usize,
    has_rhymes: usize,
    has_ipa: usize,
    has_category: usize,
    has_hyphenation: usize,
    disagreements: usize,
    elapsed: Duration,
}

fn print_syllable_validation_stats(stats: &SyllableValidationStats) {
    println!();
    println!("============================================================");
    println!("Syllable Validation Results");
    println!("============================================================");
    println!("Pages scanned: {}", stats.pages_scanned);
    println!("Words with syllable data: {}", stats.words_with_syllables);
    println!();
    println!("Source coverage:");
    println!("  Rhymes (s=): {} ({:.1}%)", stats.has_rhymes,
        100.0 * stats.has_rhymes as f64 / stats.words_with_syllables.max(1) as f64);
    println!("  IPA: {} ({:.1}%)", stats.has_ipa,
        100.0 * stats.has_ipa as f64 / stats.words_with_syllables.max(1) as f64);
    println!("  Category: {} ({:.1}%)", stats.has_category,
        100.0 * stats.has_category as f64 / stats.words_with_syllables.max(1) as f64);
    println!("  Hyphenation: {} ({:.1}%)", stats.has_hyphenation,
        100.0 * stats.has_hyphenation as f64 / stats.words_with_syllables.max(1) as f64);
    println!();
    println!("Disagreements: {} ({:.2}%)", stats.disagreements,
        100.0 * stats.disagreements as f64 / stats.words_with_syllables.max(1) as f64);
    println!();
    println!("Time: {}m {}s", stats.elapsed.as_secs() / 60, stats.elapsed.as_secs() % 60);
    println!("Rate: {:.0} pages/sec", stats.pages_scanned as f64 / stats.elapsed.as_secs_f64());
    println!("============================================================");
}

fn print_stats(stats: &Stats, strategy_name: &str) {
    println!();
    println!("============================================================");
    println!("Strategy: {}", strategy_name);
    println!("Pages processed: {}", stats.pages_processed);
    println!("Words written: {}", stats.words_written);
    println!("Senses written: {}", stats.senses_written);
    println!("Avg senses/word: {:.2}", stats.senses_written as f64 / stats.words_written.max(1) as f64);
    println!("------------------------------------------------------------");
    println!("Case distribution:");
    println!("  lowercase: {} (e.g., sat)", stats.case_lower);
    println!("  Titlecase: {} (e.g., Sat)", stats.case_title);
    println!("  UPPERCASE: {} (e.g., SAT)", stats.case_upper);
    println!("  miXedCase: {} (e.g., iPhone)", stats.case_mixed);
    println!("------------------------------------------------------------");
    println!("Special pages: {}", stats.special);
    println!("Redirects: {}", stats.redirects);
    println!("Dictionary-only terms: {}", stats.dict_only);
    println!("Non-English pages: {}", stats.non_english);
    println!("Non-Latin scripts: {}", stats.non_latin);
    println!("Skipped: {}", stats.skipped);
    println!("Time: {}m {}s", stats.elapsed.as_secs() / 60, stats.elapsed.as_secs() % 60);
    println!("Rate: {:.0} pages/sec", stats.pages_processed as f64 / stats.elapsed.as_secs_f64());
    println!("============================================================");
}

fn main() -> std::io::Result<()> {
    let args = Args::parse();

    // Initialize POS map from schema YAML
    if let Err(e) = init_pos_map(args.schema.as_ref()) {
        eprintln!("Error loading POS schema: {}", e);
        std::process::exit(1);
    }

    // Initialize labels from schema YAML
    if let Err(e) = init_labels(None) {
        eprintln!("Error loading labels schema: {}", e);
        std::process::exit(1);
    }

    // Handle syllable validation mode
    if args.syllable_validation {
        if !args.quiet {
            println!("Syllable Validation Mode");
            println!("Input: {}", args.input.display());
            println!("Output: {}", args.output.display());
            if let Some(limit) = args.page_limit {
                println!("Page limit: {}", limit);
            }
            println!();
        }

        let file = File::open(&args.input)?;
        let reader: Box<dyn BufRead> = if args.input.to_string_lossy().ends_with(".bz2") {
            Box::new(BufReader::with_capacity(256 * 1024, BzDecoder::new(file)))
        } else {
            Box::new(BufReader::with_capacity(256 * 1024, file))
        };
        let output = File::create(&args.output)?;
        let mut writer = BufWriter::with_capacity(256 * 1024, output);

        let stats = run_syllable_validation(reader, &mut writer, args.page_limit, args.quiet)?;

        if !args.quiet {
            print_syllable_validation_stats(&stats);
        }

        return Ok(());
    }

    // Validate: --limit requires sequential mode for efficient early termination
    if args.limit.is_some() && args.strategy != Strategy::Sequential {
        eprintln!(
            "Error: --limit requires --strategy sequential for efficient early termination.\n\
             Parallel strategies must process pages out of order and reorder results,\n\
             which means they cannot stop early when the limit is reached."
        );
        std::process::exit(1);
    }

    // Build parallel config
    let mut config = ParallelConfig::default();
    if args.threads > 0 {
        config.num_threads = args.threads;
        config.num_workers = args.threads.saturating_sub(1).max(1);
    }
    config.batch_size = args.batch_size;
    config.channel_buffer = args.channel_buffer;

    if !args.quiet {
        println!("Parsing: {}", args.input.display());
        println!("Output: {}", args.output.display());
        println!("Strategy: {:?}", args.strategy);
        if args.strategy != Strategy::Sequential {
            println!("Threads: {}", config.num_threads);
        }
        if let Some(limit) = args.limit {
            println!("Limit: {} entries", limit);
        }
        if let Some(limit) = args.page_limit {
            println!("Page limit: {}", limit);
        }
        println!();
    }

    // Run the selected strategy
    let stats = match args.strategy {
        Strategy::Sequential => {
            let file = File::open(&args.input)?;
            let reader: Box<dyn BufRead> = if args.input.to_string_lossy().ends_with(".bz2") {
                Box::new(BufReader::with_capacity(256 * 1024, BzDecoder::new(file)))
            } else {
                Box::new(BufReader::with_capacity(256 * 1024, file))
            };
            let output = File::create(&args.output)?;
            let mut writer = BufWriter::with_capacity(256 * 1024, output);
            run_sequential(reader, &mut writer, args.limit, args.quiet)?
        }

        Strategy::BatchParallel => {
            let file = File::open(&args.input)?;
            let reader: Box<dyn BufRead> = if args.input.to_string_lossy().ends_with(".bz2") {
                Box::new(BufReader::with_capacity(256 * 1024, BzDecoder::new(file)))
            } else {
                Box::new(BufReader::with_capacity(256 * 1024, file))
            };
            let output = File::create(&args.output)?;
            let mut writer = BufWriter::with_capacity(256 * 1024, output);
            process_batch_parallel(reader, &mut writer, &config, args.limit)?
        }

        Strategy::ChannelPipeline => {
            let file = File::open(&args.input)?;
            let reader: Box<dyn BufRead + Send> = if args.input.to_string_lossy().ends_with(".bz2") {
                Box::new(BufReader::with_capacity(256 * 1024, BzDecoder::new(file)))
            } else {
                Box::new(BufReader::with_capacity(256 * 1024, file))
            };
            let output = File::create(&args.output)?;
            process_channel_pipeline(reader, output, &config, args.limit)?
        }

        Strategy::TwoPhase => {
            let file = File::open(&args.input)?;
            let reader: Box<dyn BufRead> = if args.input.to_string_lossy().ends_with(".bz2") {
                Box::new(BufReader::with_capacity(256 * 1024, BzDecoder::new(file)))
            } else {
                Box::new(BufReader::with_capacity(256 * 1024, file))
            };
            let output = File::create(&args.output)?;
            let mut writer = BufWriter::with_capacity(256 * 1024, output);
            process_two_phase(reader, &mut writer, &config, args.limit)?
        }
    };

    if !args.quiet {
        print_stats(&stats, &format!("{:?}", args.strategy));
    }

    Ok(())
}

#[derive(Default)]
pub struct Stats {
    pub pages_processed: usize,
    pub words_written: usize,
    pub senses_written: usize,
    pub special: usize,
    pub redirects: usize,
    pub dict_only: usize,
    pub non_english: usize,
    pub non_latin: usize,
    pub skipped: usize,
    pub elapsed: Duration,
    // Case distribution (for reporting)
    pub case_lower: usize,      // all lowercase: "sat"
    pub case_title: usize,      // Capitalized: "Sat"
    pub case_upper: usize,      // ALL CAPS: "SAT"
    pub case_mixed: usize,      // miXed case: "iPhone"
}

/// Classify the case pattern of a word (for reporting purposes)
pub fn classify_case(s: &str) -> CaseForm {
    let has_alpha = s.chars().any(|c| c.is_alphabetic());
    if !has_alpha {
        return CaseForm::Lower; // Treat non-alphabetic as lowercase
    }

    let alpha_chars: Vec<char> = s.chars().filter(|c| c.is_alphabetic()).collect();
    let all_lower = alpha_chars.iter().all(|c| c.is_lowercase());
    let all_upper = alpha_chars.iter().all(|c| c.is_uppercase());
    let first_upper = alpha_chars.first().map(|c| c.is_uppercase()).unwrap_or(false);
    let rest_lower = alpha_chars.iter().skip(1).all(|c| c.is_lowercase());

    if all_lower {
        CaseForm::Lower
    } else if all_upper {
        CaseForm::Upper
    } else if first_upper && rest_lower {
        CaseForm::Title
    } else {
        CaseForm::Mixed
    }
}

#[derive(Debug, Clone, Copy)]
pub enum CaseForm {
    Lower,
    Title,
    Upper,
    Mixed,
}

// ─────────────────────────────────────────────────────────────────────────────
// Tests for WikitextParser
// ─────────────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod wikitext_parser_tests {
    use super::*;

    // ─────────────────────────────────────────────────────────────
    // Wikilink struct tests
    // ─────────────────────────────────────────────────────────────

    #[test]
    fn wikilink_text_returns_display_when_present() {
        let wl = Wikilink {
            target: "isle".to_string(),
            anchor: None,
            display: Some("Isle".to_string()),
        };
        assert_eq!(wl.text(), "Isle");
    }

    #[test]
    fn wikilink_text_returns_target_when_no_display() {
        let wl = Wikilink {
            target: "word".to_string(),
            anchor: None,
            display: None,
        };
        assert_eq!(wl.text(), "word");
    }

    #[test]
    fn wikilink_anchor_preserved() {
        let wl = Wikilink {
            target: "Man".to_string(),
            anchor: Some("Etymology 2".to_string()),
            display: Some("Man".to_string()),
        };
        assert_eq!(wl.anchor, Some("Etymology 2".to_string()));
        assert_eq!(wl.text(), "Man");
    }

    // ─────────────────────────────────────────────────────────────
    // Basic parameter parsing
    // ─────────────────────────────────────────────────────────────

    #[test]
    fn simple_params() {
        let result = parse_template_params("en|word|suffix");
        assert_eq!(result, vec!["en", "word", "suffix"]);
    }

    #[test]
    fn empty_string() {
        let result = parse_template_params("");
        assert!(result.is_empty() || result == vec![""]);
    }

    #[test]
    fn single_param() {
        let result = parse_template_params("word");
        assert_eq!(result, vec!["word"]);
    }

    #[test]
    fn whitespace_trimming() {
        let result = parse_template_params("  en  |  word  |  suffix  ");
        assert_eq!(result, vec!["en", "word", "suffix"]);
    }

    // ─────────────────────────────────────────────────────────────
    // Wikilink parsing
    // ─────────────────────────────────────────────────────────────

    #[test]
    fn simple_wikilink() {
        let result = parse_template_params("[[cat]]");
        assert_eq!(result, vec!["cat"]);
    }

    #[test]
    fn wikilink_with_display() {
        let result = parse_template_params("[[isle|Isle]]");
        assert_eq!(result, vec!["Isle"]);
    }

    #[test]
    fn wikilink_with_anchor() {
        let result = parse_template_params("[[Man#Etymology 2]]");
        assert_eq!(result, vec!["Man"]);
    }

    #[test]
    fn wikilink_with_anchor_and_display() {
        let result = parse_template_params("[[Man#Etymology 2|Man]]");
        assert_eq!(result, vec!["Man"]);
    }

    #[test]
    fn isle_of_man_example() {
        // The motivating example: {{af|en|[[isle|Isle]]|of|[[Man#Etymology 2|Man]]}}
        let result = parse_template_params("en|[[isle|Isle]]|of|[[Man#Etymology 2|Man]]");
        assert_eq!(result, vec!["en", "Isle", "of", "Man"]);
    }

    #[test]
    fn multiple_wikilinks() {
        let result = parse_template_params("[[a|A]]|[[b|B]]|[[c|C]]");
        assert_eq!(result, vec!["A", "B", "C"]);
    }

    #[test]
    fn mixed_wikilinks_and_text() {
        let result = parse_template_params("prefix|[[word|Word]]|suffix");
        assert_eq!(result, vec!["prefix", "Word", "suffix"]);
    }

    // ─────────────────────────────────────────────────────────────
    // Nested template handling
    // ─────────────────────────────────────────────────────────────

    #[test]
    fn nested_template_discarded() {
        let result = parse_template_params("foo|{{q|qualifier}}|bar");
        assert_eq!(result, vec!["foo", "", "bar"]);
    }

    #[test]
    fn deeply_nested_templates() {
        let result = parse_template_params("foo|{{a|{{b|{{c|d}}}}}}|bar");
        assert_eq!(result, vec!["foo", "", "bar"]);
    }

    #[test]
    fn template_with_wikilink_inside() {
        let result = parse_template_params("foo|{{m|en|[[word]]}}|bar");
        assert_eq!(result, vec!["foo", "", "bar"]);
    }

    #[test]
    fn wikilink_after_template() {
        let result = parse_template_params("{{info}}|[[word|Word]]");
        assert_eq!(result, vec!["", "Word"]);
    }

    // ─────────────────────────────────────────────────────────────
    // UTF-8 handling (the bug we fixed!)
    // ─────────────────────────────────────────────────────────────

    #[test]
    fn latin_extended_characters() {
        let result = parse_template_params("nāsus|-o-");
        assert_eq!(result, vec!["nāsus", "-o-"]);
    }

    #[test]
    fn alphabeticus_example() {
        // The case that caused the panic
        let result = parse_template_params("lang1=la|alphabēticus|-al");
        assert_eq!(result, vec!["lang1=la", "alphabēticus", "-al"]);
    }

    #[test]
    fn greek_characters() {
        let result = parse_template_params("en|λόγος");
        assert_eq!(result, vec!["en", "λόγος"]);
    }

    #[test]
    fn cyrillic_characters() {
        let result = parse_template_params("en|слово");
        assert_eq!(result, vec!["en", "слово"]);
    }

    #[test]
    fn mixed_scripts_in_wikilink() {
        let result = parse_template_params("[[word|café]]");
        assert_eq!(result, vec!["café"]);
    }

    #[test]
    fn utf8_in_anchor() {
        let result = parse_template_params("[[page#Étymologie|display]]");
        assert_eq!(result, vec!["display"]);
    }

    // ─────────────────────────────────────────────────────────────
    // Edge cases
    // ─────────────────────────────────────────────────────────────

    #[test]
    fn unclosed_wikilink() {
        let result = parse_template_params("[[word");
        assert_eq!(result, vec!["word"]);
    }

    #[test]
    fn unclosed_template() {
        let result = parse_template_params("{{template");
        assert_eq!(result, vec![""]);
    }

    #[test]
    fn empty_wikilink() {
        let result = parse_template_params("[[]]");
        assert_eq!(result, vec![""]);
    }

    #[test]
    fn consecutive_pipes() {
        let result = parse_template_params("a||b");
        assert_eq!(result, vec!["a", "", "b"]);
    }

    #[test]
    fn wikilink_with_only_anchor() {
        let result = parse_template_params("[[#section]]");
        // Target is empty, anchor is "section", no display
        assert_eq!(result, vec![""]);
    }

    #[test]
    fn wikilink_with_empty_display() {
        let result = parse_template_params("[[word|]]");
        assert_eq!(result, vec![""]);
    }

    #[test]
    fn special_characters_in_text() {
        let result = parse_template_params("word's|don't|it-self");
        assert_eq!(result, vec!["word's", "don't", "it-self"]);
    }

    // ─────────────────────────────────────────────────────────────
    // Real-world examples
    // ─────────────────────────────────────────────────────────────

    #[test]
    fn batsman_compound() {
        // batsman: {{compound|en|bat|-s-|-man}}
        let result = parse_template_params("bat|-s-|-man");
        assert_eq!(result, vec!["bat", "-s-", "-man"]);
    }

    #[test]
    fn affix_with_link() {
        let result = parse_template_params("[[un-]]|[[happy]]");
        assert_eq!(result, vec!["un-", "happy"]);
    }

    #[test]
    fn suffix_template() {
        let result = parse_template_params("beauty|-ful");
        assert_eq!(result, vec!["beauty", "-ful"]);
    }

    #[test]
    fn prefix_template() {
        let result = parse_template_params("un-|happy");
        assert_eq!(result, vec!["un-", "happy"]);
    }

    #[test]
    fn confix_template() {
        let result = parse_template_params("bio-|chemistry|-ist");
        assert_eq!(result, vec!["bio-", "chemistry", "-ist"]);
    }

    #[test]
    fn pictograph_style() {
        // Pattern like pictograph: {{affix|en|la:pictus|-o-|graph}}
        let result = parse_template_params("la:pictus|-o-|graph");
        assert_eq!(result, vec!["la:pictus", "-o-", "graph"]);
    }

    // ─────────────────────────────────────────────────────────────
    // Parser internal tests
    // ─────────────────────────────────────────────────────────────

    #[test]
    fn parser_peek_multibyte() {
        let parser = WikitextParser::new("café");
        // Should handle multi-byte UTF-8 correctly
        assert_eq!(parser.peek(1), "c");
        assert_eq!(parser.peek(4), "café");
    }

    #[test]
    fn parser_consume_multibyte() {
        let mut parser = WikitextParser::new("café");
        assert_eq!(parser.consume(1), "c");
        assert_eq!(parser.consume(1), "a");
        assert_eq!(parser.consume(1), "f");
        assert_eq!(parser.consume(1), "é");
        assert!(parser.at_end());
    }

    #[test]
    fn parser_wikilink_all_parts() {
        let mut parser = WikitextParser::new("[[Man#Etymology 2|Man]]");
        let wl = parser.parse_wikilink();
        assert_eq!(wl.target, "Man");
        assert_eq!(wl.anchor, Some("Etymology 2".to_string()));
        assert_eq!(wl.display, Some("Man".to_string()));
    }

    #[test]
    fn parser_template_simple() {
        let mut parser = WikitextParser::new("{{m|en|word}}");
        let tmpl = parser.parse_template();
        assert_eq!(tmpl.name, "m");
        assert_eq!(tmpl.params, vec!["en", "word"]);
    }

    #[test]
    fn parser_template_nested() {
        let mut parser = WikitextParser::new("{{outer|{{inner|a|b}}}}");
        let tmpl = parser.parse_template();
        assert_eq!(tmpl.name, "outer");
        // Inner template is parsed but its text is discarded
        assert_eq!(tmpl.params, vec![""]);
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Tests for Morphology Extraction
// ─────────────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod morphology_tests {
    use super::*;

    // ─────────────────────────────────────────────────────────────
    // classify_morphology tests
    // ─────────────────────────────────────────────────────────────

    #[test]
    fn classify_suffixed() {
        let result = classify_morphology(
            vec!["happy".to_string(), "-ness".to_string()],
            "{{test}}".to_string()
        );
        assert_eq!(result.morph_type, "suffixed");
        assert_eq!(result.base, Some("happy".to_string()));
        assert_eq!(result.suffixes, vec!["-ness"]);
        assert!(!result.is_compound);
    }

    #[test]
    fn classify_prefixed() {
        let result = classify_morphology(
            vec!["un-".to_string(), "happy".to_string()],
            "{{test}}".to_string()
        );
        assert_eq!(result.morph_type, "prefixed");
        assert_eq!(result.base, Some("happy".to_string()));
        assert_eq!(result.prefixes, vec!["un-"]);
        assert!(!result.is_compound);
    }

    #[test]
    fn classify_affixed() {
        let result = classify_morphology(
            vec!["un-".to_string(), "break".to_string(), "-able".to_string()],
            "{{test}}".to_string()
        );
        assert_eq!(result.morph_type, "affixed");
        assert_eq!(result.base, Some("break".to_string()));
        assert_eq!(result.prefixes, vec!["un-"]);
        assert_eq!(result.suffixes, vec!["-able"]);
        assert!(!result.is_compound);
    }

    #[test]
    fn classify_compound() {
        let result = classify_morphology(
            vec!["sun".to_string(), "flower".to_string()],
            "{{test}}".to_string()
        );
        assert_eq!(result.morph_type, "compound");
        assert_eq!(result.base, None);
        assert!(result.is_compound);
    }

    #[test]
    fn classify_compound_with_interfix() {
        let result = classify_morphology(
            vec!["bee".to_string(), "-s-".to_string(), "wax".to_string()],
            "{{test}}".to_string()
        );
        assert_eq!(result.morph_type, "compound");
        assert_eq!(result.base, None);
        assert_eq!(result.interfixes, vec!["-s-"]);
        assert!(result.is_compound);
    }

    #[test]
    fn classify_multiple_suffixes() {
        let result = classify_morphology(
            vec!["dict".to_string(), "-ion".to_string(), "-ary".to_string()],
            "{{test}}".to_string()
        );
        assert_eq!(result.suffixes, vec!["-ion", "-ary"]);
        assert_eq!(result.base, Some("dict".to_string()));
    }

    // ─────────────────────────────────────────────────────────────
    // extract_morphology tests
    // ─────────────────────────────────────────────────────────────

    #[test]
    fn extract_suffix_template() {
        let text = "===Etymology===\n{{suffix|en|happy|ness}}";
        let result = extract_morphology(text).unwrap();
        assert_eq!(result.morph_type, "suffixed");
        assert_eq!(result.components, vec!["happy", "-ness"]);
        assert_eq!(result.base, Some("happy".to_string()));
    }

    #[test]
    fn extract_prefix_template() {
        let text = "===Etymology===\n{{prefix|en|un|happy}}";
        let result = extract_morphology(text).unwrap();
        assert_eq!(result.morph_type, "prefixed");
        assert_eq!(result.components, vec!["un-", "happy"]);
        assert_eq!(result.base, Some("happy".to_string()));
    }

    #[test]
    fn extract_confix_template() {
        let text = "===Etymology===\n{{confix|en|en|light|ment}}";
        let result = extract_morphology(text).unwrap();
        assert_eq!(result.morph_type, "circumfixed");
        assert_eq!(result.components, vec!["en-", "light", "-ment"]);
        assert_eq!(result.base, Some("light".to_string()));
    }

    #[test]
    fn extract_compound_template() {
        let text = "===Etymology===\n{{compound|en|sun|flower}}";
        let result = extract_morphology(text).unwrap();
        assert_eq!(result.morph_type, "compound");
        assert_eq!(result.components, vec!["sun", "flower"]);
        assert!(result.is_compound);
    }

    #[test]
    fn extract_affix_template_suffixed() {
        let text = "===Etymology===\n{{af|en|happy|-ness}}";
        let result = extract_morphology(text).unwrap();
        assert_eq!(result.morph_type, "suffixed");
        assert_eq!(result.components, vec!["happy", "-ness"]);
    }

    #[test]
    fn extract_affix_template_prefixed() {
        let text = "===Etymology===\n{{af|en|un-|happy}}";
        let result = extract_morphology(text).unwrap();
        assert_eq!(result.morph_type, "prefixed");
        assert_eq!(result.components, vec!["un-", "happy"]);
    }

    #[test]
    fn extract_affix_template_affixed() {
        let text = "===Etymology===\n{{af|en|un-|break|-able}}";
        let result = extract_morphology(text).unwrap();
        assert_eq!(result.morph_type, "affixed");
        assert_eq!(result.prefixes, vec!["un-"]);
        assert_eq!(result.suffixes, vec!["-able"]);
    }

    #[test]
    fn extract_affix_template_compound() {
        let text = "===Etymology===\n{{af|en|sun|flower}}";
        let result = extract_morphology(text).unwrap();
        assert_eq!(result.morph_type, "compound");
        assert!(result.is_compound);
    }

    #[test]
    fn extract_surf_template() {
        let text = "===Etymology===\n{{surf|en|heli|copter}}";
        let result = extract_morphology(text).unwrap();
        assert_eq!(result.morph_type, "compound");
        assert_eq!(result.components, vec!["heli", "copter"]);
    }

    #[test]
    fn extract_with_wikilinks() {
        let text = "===Etymology===\n{{af|en|[[isle|Isle]]|of|[[Man#Etymology 2|Man]]}}";
        let result = extract_morphology(text).unwrap();
        assert_eq!(result.components, vec!["Isle", "of", "Man"]);
    }

    #[test]
    fn extract_speedometer() {
        let text = "===Etymology===\n{{af|en|speed|-o-|meter}}";
        let result = extract_morphology(text).unwrap();
        assert_eq!(result.morph_type, "compound");
        assert_eq!(result.interfixes, vec!["-o-"]);
    }

    #[test]
    fn no_etymology_section() {
        let text = "===Pronunciation===\nSome pronunciation info";
        let result = extract_morphology(text);
        assert!(result.is_none());
    }

    #[test]
    fn no_morphology_template() {
        let text = "===Etymology===\nFrom Old English word.";
        let result = extract_morphology(text);
        assert!(result.is_none());
    }
}
