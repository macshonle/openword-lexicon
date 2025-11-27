//! Parallel processing strategies for Wiktionary XML parsing.
//!
//! This module provides multiple parallelization strategies using only std library:
//! - Sequential (baseline)
//! - Batch-parallel (std::thread on batches of pages)
//! - Channel-pipeline (producer-consumer with mpsc channels)
//! - Two-phase (read all pages, then process in parallel)

use crate::{Entry, Stats, parse_page, is_englishlike};
use crate::{TITLE_PATTERN, NS_PATTERN, TEXT_PATTERN, REDIRECT_PATTERN, ENGLISH_SECTION, DICT_ONLY, SPECIAL_PREFIXES};

use std::io::{BufRead, Write, BufWriter};
use std::sync::mpsc::{sync_channel, Receiver, SyncSender};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread::{self, JoinHandle};
use std::time::Instant;

/// Configuration for parallel processing
#[derive(Debug, Clone)]
pub struct ParallelConfig {
    /// Number of threads to use
    pub num_threads: usize,
    /// Batch size for batch-parallel processing
    pub batch_size: usize,
    /// Channel buffer size for pipeline processing
    pub channel_buffer: usize,
    /// Number of worker threads for pipeline
    pub num_workers: usize,
}

impl Default for ParallelConfig {
    fn default() -> Self {
        // Detect CPU count using std
        let cpus = thread::available_parallelism()
            .map(|p| p.get())
            .unwrap_or(4);
        Self {
            num_threads: cpus,
            batch_size: 1000,
            channel_buffer: 10000,
            num_workers: cpus.saturating_sub(1).max(1),
        }
    }
}

/// Parsed page ready for processing
#[derive(Debug)]
pub struct RawPage {
    pub title: String,
    pub text: String,
    pub page_id: usize,
}

/// Result of page processing
#[derive(Debug)]
pub struct ProcessedPage {
    pub entries: Vec<Entry>,
    pub page_id: usize,
    pub was_english: bool,
    pub was_redirect: bool,
    pub was_special: bool,
    pub was_non_latin: bool,
    pub was_dict_only: bool,
}

/// Extract pages from XML stream into raw pages
pub fn extract_pages_from_xml(page_xml: &str, page_id: usize) -> Option<RawPage> {
    // Extract title
    let title = TITLE_PATTERN.captures(page_xml)
        .map(|cap| cap[1].to_string())?;

    // Check namespace
    if let Some(cap) = NS_PATTERN.captures(page_xml) {
        if &cap[1] != "0" {
            return None;
        }
    }

    // Check for special prefixes
    if SPECIAL_PREFIXES.iter().any(|prefix| title.starts_with(prefix)) {
        return None;
    }

    // Extract text
    let text = TEXT_PATTERN.captures(page_xml)
        .map(|cap| cap[1].to_string())?;

    Some(RawPage { title, text, page_id })
}

/// Process a raw page into entries
pub fn process_raw_page(raw: RawPage) -> ProcessedPage {
    let page_id = raw.page_id;

    // Check for redirects
    if REDIRECT_PATTERN.is_match(&raw.text) {
        return ProcessedPage {
            entries: vec![],
            page_id,
            was_english: false,
            was_redirect: true,
            was_special: false,
            was_non_latin: false,
            was_dict_only: false,
        };
    }

    // Check for English section
    if !ENGLISH_SECTION.is_match(&raw.text) {
        return ProcessedPage {
            entries: vec![],
            page_id,
            was_english: false,
            was_redirect: false,
            was_special: false,
            was_non_latin: false,
            was_dict_only: false,
        };
    }

    // Check for dict-only
    if DICT_ONLY.is_match(&raw.text) {
        return ProcessedPage {
            entries: vec![],
            page_id,
            was_english: true,
            was_redirect: false,
            was_special: false,
            was_non_latin: false,
            was_dict_only: true,
        };
    }

    // Check if English-like
    if !is_englishlike(&raw.title) {
        return ProcessedPage {
            entries: vec![],
            page_id,
            was_english: true,
            was_redirect: false,
            was_special: false,
            was_non_latin: true,
            was_dict_only: false,
        };
    }

    // Parse page
    let entries = parse_page(&raw.title, &raw.text);

    ProcessedPage {
        entries,
        page_id,
        was_english: true,
        was_redirect: false,
        was_special: false,
        was_non_latin: false,
        was_dict_only: false,
    }
}

fn update_stats_from_result(stats: &mut Stats, result: &ProcessedPage) {
    if result.was_redirect {
        stats.redirects += 1;
    } else if result.was_special {
        stats.special += 1;
    } else if !result.was_english {
        stats.non_english += 1;
    } else if result.was_dict_only {
        stats.dict_only += 1;
    } else if result.was_non_latin {
        stats.non_latin += 1;
    } else if result.entries.is_empty() {
        stats.skipped += 1;
    } else {
        stats.words_written += 1;
    }
}

/// Strategy 1: Batch-Parallel Processing using std::thread
/// Collects pages into batches, then processes each batch using a thread pool
pub fn process_batch_parallel<W: Write>(
    reader: impl BufRead,
    writer: &mut BufWriter<W>,
    config: &ParallelConfig,
    limit: Option<usize>,
) -> std::io::Result<Stats> {
    let start_time = Instant::now();
    let mut stats = Stats::default();
    let mut batch: Vec<String> = Vec::with_capacity(config.batch_size);
    let mut page_id: usize = 0;

    let mut buffer = String::new();
    let mut chunk = vec![0u8; 1024 * 1024];
    let mut reader = reader;

    loop {
        let bytes_read = reader.read(&mut chunk)?;
        if bytes_read == 0 {
            break;
        }

        buffer.push_str(&String::from_utf8_lossy(&chunk[..bytes_read]));

        // Extract complete pages into batch
        while let Some(start) = buffer.find("<page>") {
            if let Some(end_offset) = buffer[start..].find("</page>") {
                let end = start + end_offset + "</page>".len();
                let page_xml = buffer[start..end].to_string();
                buffer.drain(..end);

                batch.push(page_xml);
                page_id += 1;

                // Process batch when full
                if batch.len() >= config.batch_size {
                    let base_id = page_id - batch.len();
                    let results = process_batch_threaded(&batch, base_id, config.num_threads);
                    batch.clear();

                    for result in results {
                        stats.pages_processed += 1;
                        update_stats_from_result(&mut stats, &result);

                        for entry in result.entries {
                            if let Ok(json) = serde_json::to_string(&entry) {
                                writeln!(writer, "{}", json)?;
                                stats.senses_written += 1;

                                if let Some(l) = limit {
                                    if stats.senses_written >= l {
                                        stats.elapsed = start_time.elapsed();
                                        return Ok(stats);
                                    }
                                }
                            }
                        }
                    }
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

    // Process remaining batch
    if !batch.is_empty() {
        let base_id = page_id - batch.len();
        let results = process_batch_threaded(&batch, base_id, config.num_threads);

        for result in results {
            stats.pages_processed += 1;
            update_stats_from_result(&mut stats, &result);

            for entry in result.entries {
                if let Ok(json) = serde_json::to_string(&entry) {
                    writeln!(writer, "{}", json)?;
                    stats.senses_written += 1;
                }
            }
        }
    }

    writer.flush()?;
    stats.elapsed = start_time.elapsed();
    Ok(stats)
}

/// Process a batch of pages using multiple threads
fn process_batch_threaded(batch: &[String], base_id: usize, num_threads: usize) -> Vec<ProcessedPage> {
    if batch.is_empty() {
        return vec![];
    }

    let num_threads = num_threads.min(batch.len()).max(1);
    let chunk_size = (batch.len() + num_threads - 1) / num_threads;

    // Split batch into chunks for each thread
    let chunks: Vec<Vec<(usize, String)>> = batch
        .iter()
        .enumerate()
        .map(|(i, xml)| (base_id + i, xml.clone()))
        .collect::<Vec<_>>()
        .chunks(chunk_size)
        .map(|c| c.to_vec())
        .collect();

    // Process chunks in parallel
    let handles: Vec<JoinHandle<Vec<ProcessedPage>>> = chunks
        .into_iter()
        .map(|chunk| {
            thread::spawn(move || {
                chunk
                    .into_iter()
                    .filter_map(|(pid, xml)| {
                        extract_pages_from_xml(&xml, pid).map(process_raw_page)
                    })
                    .collect()
            })
        })
        .collect();

    // Collect results
    let mut results = Vec::with_capacity(batch.len());
    for handle in handles {
        if let Ok(chunk_results) = handle.join() {
            results.extend(chunk_results);
        }
    }

    results
}

/// Strategy 2: Channel-Pipeline Processing using std::sync::mpsc
/// Producer thread reads XML, worker threads process pages, writer collects results
pub fn process_channel_pipeline<W: Write + Send + 'static>(
    reader: impl BufRead + Send + 'static,
    writer: W,
    config: &ParallelConfig,
    limit: Option<usize>,
) -> std::io::Result<Stats> {
    let (page_tx, page_rx): (SyncSender<String>, Receiver<String>) =
        sync_channel(config.channel_buffer);
    let (result_tx, result_rx): (SyncSender<ProcessedPage>, Receiver<ProcessedPage>) =
        sync_channel(config.channel_buffer);

    let limit_reached = Arc::new(AtomicBool::new(false));
    let start_time = Instant::now();

    // Spawn reader thread
    let reader_limit_flag = Arc::clone(&limit_reached);
    let reader_handle = thread::spawn(move || {
        read_pages_to_channel(reader, page_tx, &reader_limit_flag)
    });

    // Spawn worker threads
    let num_workers = config.num_workers;
    let page_rx = Arc::new(Mutex::new(page_rx));
    let worker_handles: Vec<JoinHandle<()>> = (0..num_workers)
        .map(|_| {
            let rx = Arc::clone(&page_rx);
            let tx = result_tx.clone();
            let limit_flag = Arc::clone(&limit_reached);
            thread::spawn(move || {
                process_pages_worker(rx, tx, &limit_flag)
            })
        })
        .collect();

    // Drop extra sender so channel closes when workers finish
    drop(result_tx);

    // Writer in main thread
    let final_stats = write_results(result_rx, writer, limit, &limit_reached)?;

    // Wait for threads
    reader_handle.join().ok();
    for handle in worker_handles {
        handle.join().ok();
    }

    let mut stats = final_stats;
    stats.elapsed = start_time.elapsed();
    Ok(stats)
}

fn read_pages_to_channel(
    mut reader: impl BufRead,
    tx: SyncSender<String>,
    limit_reached: &AtomicBool,
) -> std::io::Result<usize> {
    let mut buffer = String::new();
    let mut chunk = vec![0u8; 1024 * 1024];
    let mut count = 0;

    loop {
        if limit_reached.load(Ordering::Relaxed) {
            break;
        }

        let bytes_read = reader.read(&mut chunk)?;
        if bytes_read == 0 {
            break;
        }

        buffer.push_str(&String::from_utf8_lossy(&chunk[..bytes_read]));

        while let Some(start) = buffer.find("<page>") {
            if let Some(end_offset) = buffer[start..].find("</page>") {
                let end = start + end_offset + "</page>".len();
                let page_xml = buffer[start..end].to_string();
                buffer.drain(..end);

                if tx.send(page_xml).is_err() {
                    return Ok(count);
                }
                count += 1;
            } else {
                buffer.drain(..start);
                break;
            }
        }

        if buffer.len() > 10 && !buffer.contains("<page>") {
            buffer.drain(..buffer.len().saturating_sub(10));
        }
    }

    Ok(count)
}

fn process_pages_worker(
    rx: Arc<Mutex<Receiver<String>>>,
    tx: SyncSender<ProcessedPage>,
    limit_reached: &AtomicBool,
) {
    let mut page_id = 0;
    loop {
        if limit_reached.load(Ordering::Relaxed) {
            break;
        }

        // Try to get next page from shared receiver
        let xml = {
            let lock = rx.lock().ok();
            lock.and_then(|guard| guard.recv().ok())
        };

        match xml {
            Some(xml) => {
                if let Some(raw) = extract_pages_from_xml(&xml, page_id) {
                    let result = process_raw_page(raw);
                    if tx.send(result).is_err() {
                        break;
                    }
                }
                page_id += 1;
            }
            None => break,
        }
    }
}

fn write_results<W: Write>(
    rx: Receiver<ProcessedPage>,
    writer: W,
    limit: Option<usize>,
    limit_reached: &AtomicBool,
) -> std::io::Result<Stats> {
    let mut writer = BufWriter::with_capacity(256 * 1024, writer);
    let mut stats = Stats::default();

    while let Ok(result) = rx.recv() {
        stats.pages_processed += 1;
        update_stats_from_result(&mut stats, &result);

        for entry in result.entries {
            if let Ok(json) = serde_json::to_string(&entry) {
                writeln!(writer, "{}", json)?;
                stats.senses_written += 1;

                if let Some(l) = limit {
                    if stats.senses_written >= l {
                        limit_reached.store(true, Ordering::SeqCst);
                        writer.flush()?;
                        return Ok(stats);
                    }
                }
            }
        }
    }

    writer.flush()?;
    Ok(stats)
}

/// Strategy 3: Two-Phase Processing
/// Phase 1: Read all pages into memory
/// Phase 2: Process all pages in parallel with multiple threads
pub fn process_two_phase<W: Write>(
    reader: impl BufRead,
    writer: &mut BufWriter<W>,
    config: &ParallelConfig,
    limit: Option<usize>,
) -> std::io::Result<Stats> {
    let start_time = Instant::now();

    // Phase 1: Read all pages
    eprintln!("Phase 1: Reading pages...");
    let pages = read_all_pages(reader)?;
    eprintln!("Read {} pages in {:?}", pages.len(), start_time.elapsed());

    // Phase 2: Process in parallel
    eprintln!("Phase 2: Processing in parallel with {} threads...", config.num_threads);
    let process_start = Instant::now();

    let results = process_all_pages_parallel(&pages, config.num_threads);

    eprintln!("Processed {} results in {:?}", results.len(), process_start.elapsed());

    // Phase 3: Write results
    let mut stats = Stats::default();
    for result in results {
        stats.pages_processed += 1;
        update_stats_from_result(&mut stats, &result);

        for entry in result.entries {
            if let Ok(json) = serde_json::to_string(&entry) {
                writeln!(writer, "{}", json)?;
                stats.senses_written += 1;

                if let Some(l) = limit {
                    if stats.senses_written >= l {
                        stats.elapsed = start_time.elapsed();
                        return Ok(stats);
                    }
                }
            }
        }
    }

    writer.flush()?;
    stats.elapsed = start_time.elapsed();
    Ok(stats)
}

fn read_all_pages(mut reader: impl BufRead) -> std::io::Result<Vec<String>> {
    let mut pages = Vec::new();
    let mut buffer = String::new();
    let mut chunk = vec![0u8; 1024 * 1024];

    loop {
        let bytes_read = reader.read(&mut chunk)?;
        if bytes_read == 0 {
            break;
        }

        buffer.push_str(&String::from_utf8_lossy(&chunk[..bytes_read]));

        while let Some(start) = buffer.find("<page>") {
            if let Some(end_offset) = buffer[start..].find("</page>") {
                let end = start + end_offset + "</page>".len();
                let page_xml = buffer[start..end].to_string();
                buffer.drain(..end);
                pages.push(page_xml);
            } else {
                buffer.drain(..start);
                break;
            }
        }

        if buffer.len() > 10 && !buffer.contains("<page>") {
            buffer.drain(..buffer.len().saturating_sub(10));
        }
    }

    Ok(pages)
}

/// Process all pages in parallel using std::thread
fn process_all_pages_parallel(pages: &[String], num_threads: usize) -> Vec<ProcessedPage> {
    if pages.is_empty() {
        return vec![];
    }

    let num_threads = num_threads.min(pages.len()).max(1);
    let chunk_size = (pages.len() + num_threads - 1) / num_threads;

    // Create indexed chunks
    let chunks: Vec<Vec<(usize, &String)>> = pages
        .iter()
        .enumerate()
        .collect::<Vec<_>>()
        .chunks(chunk_size)
        .map(|c| c.to_vec())
        .collect();

    // Process chunks in parallel
    // Note: We need to clone pages since threads need 'static lifetime
    let chunks_owned: Vec<Vec<(usize, String)>> = chunks
        .into_iter()
        .map(|c| c.into_iter().map(|(i, s)| (i, s.clone())).collect())
        .collect();

    let handles: Vec<JoinHandle<Vec<ProcessedPage>>> = chunks_owned
        .into_iter()
        .map(|chunk| {
            thread::spawn(move || {
                chunk
                    .into_iter()
                    .filter_map(|(pid, xml)| {
                        extract_pages_from_xml(&xml, pid).map(process_raw_page)
                    })
                    .collect()
            })
        })
        .collect();

    // Collect results preserving order
    let mut all_results: Vec<ProcessedPage> = Vec::with_capacity(pages.len());
    for handle in handles {
        if let Ok(chunk_results) = handle.join() {
            all_results.extend(chunk_results);
        }
    }

    all_results
}
