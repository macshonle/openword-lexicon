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
#[command(about = "Fast Rust-based Wiktionary XML parser")]
struct Args {
    /// Input XML file (.xml or .xml.bz2)
    input: PathBuf,

    /// Output JSONL file
    output: PathBuf,

    /// Limit number of entries to extract (for testing)
    #[arg(long)]
    limit: Option<usize>,
}

#[derive(Debug, Serialize, Deserialize)]
struct Entry {
    word: String,
    pos: Vec<String>,
    #[serde(skip_serializing_if = "HashMap::is_empty")]
    labels: HashMap<String, Vec<String>>,
    word_count: usize,
    is_phrase: bool,
    is_abbreviation: bool,
    is_proper_noun: bool,
    is_vulgar: bool,
    is_archaic: bool,
    is_rare: bool,
    is_informal: bool,
    is_technical: bool,
    is_regional: bool,
    is_inflected: bool,
    is_dated: bool,
    sources: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    phrase_type: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    syllables: Option<usize>,
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

    // POS patterns
    static ref POS_HEADER: Regex = Regex::new(r"(?m)^===+\s*(.+?)\s*===+\s*$").unwrap();
    static ref HEAD_TEMPLATE: Regex = Regex::new(r"(?i)\{\{(?:head|en-head|head-lite)\|en\|([^}|]+)").unwrap();
    static ref EN_POS_TEMPLATE: Regex = Regex::new(r"(?i)\{\{en-(noun|verb|adj|adv|prop|pron)\b").unwrap();

    // Label patterns
    static ref CONTEXT_LABEL: Regex = Regex::new(r"(?i)\{\{(?:lb|label|context)\|en\|([^}]+)\}\}").unwrap();
    static ref CATEGORY: Regex = Regex::new(r"(?i)\[\[Category:English\s+([^\]]+)\]\]").unwrap();

    // Other patterns
    static ref ABBREVIATION_TEMPLATE: Regex = Regex::new(r"(?i)\{\{(?:abbreviation of|abbrev of|abbr of|initialism of)\|en\|").unwrap();
    static ref DICT_ONLY: Regex = Regex::new(r"(?i)\{\{no entry\|en").unwrap();

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

        // Simplified character validation for spike
        if ch.is_ascii() {
            if ch.is_alphabetic() {
                saw_latin_letter = true;
            } else if ch.is_numeric() {
                // Allow numbers
            } else if allowed_punct.contains(&ch) {
                // Allow specific punctuation
            } else if ch.is_whitespace() {
                // Allow whitespace
            }
        } else {
            // Non-ASCII character - check if it's Latin-based
            // This is a simplified check - for spike purposes
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

fn extract_pos_tags(text: &str) -> Vec<String> {
    let mut pos_tags = HashSet::new();

    // Extract from section headers
    for cap in POS_HEADER.captures_iter(text) {
        let header = cap[1].to_lowercase().trim().to_string();
        let header = header.split_whitespace().collect::<Vec<_>>().join(" ");
        if let Some(&mapped) = POS_MAP.get(header.as_str()) {
            pos_tags.insert(mapped.to_string());
        }
    }

    // Fallback: head templates
    if pos_tags.is_empty() {
        for cap in HEAD_TEMPLATE.captures_iter(text) {
            let pos = cap[1].to_lowercase().trim().to_string();
            if let Some(&mapped) = POS_MAP.get(pos.as_str()) {
                pos_tags.insert(mapped.to_string());
            }
        }
    }

    // Fallback: en-POS templates
    if pos_tags.is_empty() {
        for cap in EN_POS_TEMPLATE.captures_iter(text) {
            let pos = cap[1].to_lowercase();
            let mapped = match pos.as_str() {
                "noun" => "noun",
                "verb" => "verb",
                "adj" => "adjective",
                "adv" => "adverb",
                "prop" => "noun",
                "pron" => "pronoun",
                _ => continue,
            };
            pos_tags.insert(mapped.to_string());
        }
    }

    let mut result: Vec<String> = pos_tags.into_iter().collect();
    result.sort();
    result
}

fn extract_labels(text: &str) -> HashMap<String, Vec<String>> {
    let mut labels: HashMap<String, HashSet<String>> = HashMap::new();

    // Extract from context labels
    for cap in CONTEXT_LABEL.captures_iter(text) {
        for label in cap[1].split('|') {
            let label = label.trim().to_lowercase();

            if REGISTER_LABELS.contains(label.as_str()) {
                labels.entry("register".to_string()).or_default().insert(label);
            } else if TEMPORAL_LABELS.contains(label.as_str()) {
                labels.entry("temporal".to_string()).or_default().insert(label);
            } else if DOMAIN_LABELS.contains(label.as_str()) {
                labels.entry("domain".to_string()).or_default().insert(label);
            }
        }
    }

    // Extract from categories
    for cap in CATEGORY.captures_iter(text) {
        let cat = cap[1].to_lowercase();

        if cat.contains("informal") || cat.contains("colloquial") {
            labels.entry("register".to_string()).or_default().insert("informal".to_string());
        }
        if cat.contains("slang") {
            labels.entry("register".to_string()).or_default().insert("slang".to_string());
        }
        if cat.contains("vulgar") {
            labels.entry("register".to_string()).or_default().insert("vulgar".to_string());
        }
        if cat.contains("offensive") || cat.contains("derogatory") {
            labels.entry("register".to_string()).or_default().insert("offensive".to_string());
        }
        if cat.contains("obsolete") {
            labels.entry("temporal".to_string()).or_default().insert("obsolete".to_string());
        }
        if cat.contains("archaic") {
            labels.entry("temporal".to_string()).or_default().insert("archaic".to_string());
        }
    }

    // Convert to sorted vectors
    labels.into_iter()
        .map(|(k, v)| {
            let mut vec: Vec<String> = v.into_iter().collect();
            vec.sort();
            (k, vec)
        })
        .collect()
}

fn parse_entry(title: &str, text: &str) -> Option<Entry> {
    let word = title.to_lowercase().trim().to_string();

    // Extract English section
    let english_text = extract_english_section(text)?;

    // Extract POS tags
    let pos_tags = extract_pos_tags(&english_text);

    // If no POS tags, check for other English signals
    if pos_tags.is_empty() {
        // Check for English categories or templates as validation
        let has_categories = text.to_lowercase().contains("category:english");
        let has_en_templates = text.contains("{{en-");

        if !has_categories && !has_en_templates {
            return None;
        }
    }

    let labels = extract_labels(&english_text);
    let word_count = word.split_whitespace().count();

    // Extract boolean flags
    let is_abbreviation = ABBREVIATION_TEMPLATE.is_match(&english_text);
    let is_proper_noun = POS_HEADER.captures_iter(&english_text)
        .any(|cap| cap[1].to_lowercase().contains("proper noun"));

    let temporal = labels.get("temporal").map(|v| v.as_slice()).unwrap_or(&[]);
    let register = labels.get("register").map(|v| v.as_slice()).unwrap_or(&[]);
    let domain = labels.get("domain").map(|v| v.as_slice()).unwrap_or(&[]);

    let is_vulgar = register.contains(&"vulgar".to_string()) || register.contains(&"offensive".to_string());
    let is_archaic = temporal.contains(&"archaic".to_string()) || temporal.contains(&"obsolete".to_string());
    let is_rare = temporal.contains(&"rare".to_string());
    let is_informal = register.contains(&"informal".to_string()) || register.contains(&"slang".to_string());
    let is_technical = !domain.is_empty();
    let is_regional = labels.contains_key("region");
    let is_dated = temporal.contains(&"dated".to_string());
    let is_inflected = text.contains("{{plural of|en|") || text.contains("{{past tense of|en|");

    Some(Entry {
        word,
        pos: pos_tags,
        labels,
        word_count,
        is_phrase: word_count > 1,
        is_abbreviation,
        is_proper_noun,
        is_vulgar,
        is_archaic,
        is_rare,
        is_informal,
        is_technical,
        is_regional,
        is_inflected,
        is_dated,
        sources: vec!["wikt".to_string()],
        phrase_type: None,
        syllables: None,
    })
}

fn scan_pages(mut reader: impl BufRead, mut callback: impl FnMut(String)) -> std::io::Result<()> {
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
                callback(page_xml);
            } else {
                // Incomplete page, keep in buffer
                buffer.drain(..start);
                break;
            }
        }

        // Keep last bit in case it's a partial tag
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
    println!("Method: Fast Rust scanner (compiled, optimized)");
    if let Some(limit) = args.limit {
        println!("Limit: {} entries", limit);
    }
    println!();

    let start_time = Instant::now();

    // Open input file
    let file = File::open(&args.input)?;
    let reader: Box<dyn BufRead> = if args.input.to_string_lossy().ends_with(".bz2") {
        Box::new(BufReader::with_capacity(256 * 1024, BzDecoder::new(file)))
    } else {
        Box::new(BufReader::with_capacity(256 * 1024, file))
    };

    // Open output file
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
        // Check if limit already reached
        if limit_reached.get() {
            return;
        }

        stats.processed += 1;

        if stats.processed % 1000 == 0 {
            let elapsed = start_time.elapsed().as_secs_f64();
            let rate = stats.processed as f64 / elapsed;
            pb.set_message(format!(
                "Processed: {} | Written: {} | Skipped: {} | Rate: {:.0} pg/s",
                stats.processed, stats.written, stats.skipped, rate
            ));
        }

        // Extract title
        let title = match TITLE_PATTERN.captures(&page_xml) {
            Some(cap) => cap[1].to_string(),
            None => {
                stats.skipped += 1;
                return;
            }
        };

        // Check namespace (only process ns=0)
        if let Some(cap) = NS_PATTERN.captures(&page_xml) {
            if &cap[1] != "0" {
                stats.special += 1;
                return;
            }
        }

        // Check for special prefixes
        if SPECIAL_PREFIXES.iter().any(|prefix| title.starts_with(prefix)) {
            stats.special += 1;
            return;
        }

        // Check for redirects
        if REDIRECT_PATTERN.is_match(&page_xml) {
            stats.redirects += 1;
            return;
        }

        // Extract text
        let text = match TEXT_PATTERN.captures(&page_xml) {
            Some(cap) => cap[1].to_string(),
            None => {
                stats.skipped += 1;
                return;
            }
        };

        // Check for English section
        if !ENGLISH_SECTION.is_match(&text) {
            stats.non_english += 1;
            return;
        }

        // Check for dict-only
        if DICT_ONLY.is_match(&text) {
            stats.dict_only += 1;
            return;
        }

        // Check if English-like
        if !is_englishlike(&title) {
            stats.non_latin += 1;
            return;
        }

        // Parse entry
        match parse_entry(&title, &text) {
            Some(entry) => {
                if let Ok(json) = serde_json::to_string(&entry) {
                    writeln!(writer, "{}", json).ok();
                    stats.written += 1;

                    if let Some(limit) = args.limit {
                        if stats.written >= limit {
                            limit_reached.set(true);
                        }
                    }
                }
            }
            None => {
                stats.skipped += 1;
            }
        }
    })?;

    // Flush writer before finishing
    writer.flush()?;

    if limit_reached.get() {
        pb.finish_with_message(format!("Reached limit of {} entries", args.limit.unwrap()));
    } else {
        pb.finish_and_clear();
    }

    let elapsed = start_time.elapsed();
    println!();
    println!("============================================================");
    println!("Total processed: {}", stats.processed);
    println!("Total written: {}", stats.written);
    println!("Special pages: {}", stats.special);
    println!("Redirects: {}", stats.redirects);
    println!("Dictionary-only terms: {}", stats.dict_only);
    println!("Non-English pages: {}", stats.non_english);
    println!("Non-Latin scripts: {}", stats.non_latin);
    println!("Total skipped: {}", stats.skipped);
    println!(
        "Success rate: {:.1}%",
        stats.written as f64 / stats.processed as f64 * 100.0
    );
    println!("Time: {}m {}s", elapsed.as_secs() / 60, elapsed.as_secs() % 60);
    println!("Rate: {:.0} pages/sec", stats.processed as f64 / elapsed.as_secs_f64());
    println!("============================================================");

    Ok(())
}

#[derive(Default)]
struct Stats {
    processed: usize,
    written: usize,
    special: usize,
    redirects: usize,
    dict_only: usize,
    non_english: usize,
    non_latin: usize,
    skipped: usize,
}
