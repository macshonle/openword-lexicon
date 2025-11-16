#!/usr/bin/env node
/**
 * OpenWord Lexicon - Interactive CLI Word List Builder
 *
 * Interactive command-line tool for creating word list filter specifications.
 *
 * Usage:
 *   node cli-builder.js [--preset <name>] [--output <file>]
 */

import readline from 'readline';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { dirname } from 'path';
import { SpecBuilder, CAPABILITIES, helpers } from './spec-builder.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// ANSI color codes
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  dim: '\x1b[2m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m',
  cyan: '\x1b[36m'
};

// Parse command line arguments
const args = process.argv.slice(2);
const presetArg = args.indexOf('--preset') !== -1 ? args[args.indexOf('--preset') + 1] : null;
const outputArg = args.indexOf('--output') !== -1 ? args[args.indexOf('--output') + 1] : null;

// Create readline interface
const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

/**
 * Prompt helpers
 */
function question(prompt) {
  return new Promise(resolve => rl.question(prompt, resolve));
}

function print(text, color = 'reset') {
  console.log(colors[color] + text + colors.reset);
}

function printSection(title) {
  console.log();
  print('═'.repeat(70), 'cyan');
  print(`  ${title}`, 'bright');
  print('═'.repeat(70), 'cyan');
  console.log();
}

function printOption(key, label, description) {
  print(`  ${colors.bright}[${key}]${colors.reset} ${label}`, 'cyan');
  if (description) {
    print(`      ${description}`, 'dim');
  }
}

/**
 * Main builder workflow
 */
async function buildSpec() {
  const builder = new SpecBuilder();

  print('\n╔═══════════════════════════════════════════════════════════════════╗', 'cyan');
  print('║     OpenWord Lexicon - Interactive Word List Builder             ║', 'bright');
  print('╚═══════════════════════════════════════════════════════════════════╝', 'cyan');

  console.log();
  print('This tool will guide you through creating a word list filter specification.', 'dim');
  print('The specification can be used with the `owlex` command to generate filtered word lists.\n', 'dim');

  // Check for preset
  if (presetArg) {
    const preset = helpers.getPreset(presetArg);
    if (preset) {
      print(`Loading preset: ${preset.name}`, 'green');
      print(`  ${preset.description}\n`, 'dim');
      builder.loadPreset(presetArg);

      const usePreset = await question('Use this preset as-is? (y/n): ');
      if (usePreset.toLowerCase() === 'y') {
        return await finishSpec(builder);
      }
      print('\nOk, you can modify the preset below.\n', 'dim');
    } else {
      print(`Warning: Preset '${presetArg}' not found. Starting from scratch.\n`, 'yellow');
    }
  }

  // Step 1: Distribution selection
  await selectDistribution(builder);

  // Step 2: Name and description
  await setMetadata(builder);

  // Step 3: Select preset or build from scratch
  if (!presetArg) {
    // Show available presets first
    const presets = helpers.getPresets();
    const currentDist = builder.spec.distribution;
    const availablePresets = presets.filter(name => {
      const preset = helpers.getPreset(name);
      return preset.distribution === currentDist;
    });

    if (availablePresets.length > 0) {
      print('\nAvailable presets for ' + currentDist + ':', 'cyan');
      availablePresets.forEach(name => {
        const preset = helpers.getPreset(name);
        print(`  • ${preset.name}: ${preset.description}`, 'dim');
      });
      console.log();
    }

    const usePreset = await question('Start from a preset? (y/n) [n]: ');
    if (usePreset.toLowerCase() === 'y') {
      await selectPreset(builder);
    }
  }

  // Step 4: Add filters
  await addFilters(builder);

  // Step 5: Configure output
  await configureOutput(builder);

  // Step 6: Finish
  return await finishSpec(builder);
}

/**
 * Distribution selection
 */
async function selectDistribution(builder) {
  printSection('1. Distribution Selection');

  print('Choose which distribution to filter:\n');

  for (const [key, dist] of Object.entries(CAPABILITIES.distributions)) {
    print(`  ${colors.bright}[${key}]${colors.reset} ${dist.name}`, 'cyan');
    print(`      License: ${dist.license}`, 'dim');
    print(`      Words: ${dist.totalWords.toLocaleString()}`, 'dim');
    print(`      ${dist.description}`, 'dim');
    console.log();
  }

  const choice = await question('Distribution (core/plus) [core]: ');
  const dist = choice.trim().toLowerCase() || 'core';

  if (!CAPABILITIES.distributions[dist]) {
    print('Invalid distribution, using core', 'yellow');
    builder.setDistribution('core');
  } else {
    builder.setDistribution(dist);
    print(`✓ Using ${dist} distribution\n`, 'green');
  }
}

/**
 * Name and description
 */
async function setMetadata(builder) {
  printSection('2. Word List Information');

  const name = await question('Name for this word list (optional): ');
  const description = await question('Description (optional): ');

  if (name || description) {
    builder.setMetadata(name.trim() || null, description.trim() || null);
    print('✓ Metadata set\n', 'green');
  }
}

/**
 * Preset selection
 */
async function selectPreset(builder) {
  printSection('Available Presets');

  const presets = helpers.getPresets();
  const currentDist = builder.spec.distribution;

  const availablePresets = presets.filter(name => {
    const preset = helpers.getPreset(name);
    return preset.distribution === currentDist;
  });

  if (availablePresets.length === 0) {
    print(`No presets available for ${currentDist} distribution.\n`, 'yellow');
    return;
  }

  printOption('0', 'Skip preset', 'Start with no filters');
  availablePresets.forEach((name, idx) => {
    const preset = helpers.getPreset(name);
    printOption(String(idx + 1), preset.name, preset.description);
  });

  const choice = await question('\nSelect preset (0-' + availablePresets.length + ') [0]: ');
  const idx = parseInt(choice) || 0;

  if (idx > 0 && idx <= availablePresets.length) {
    const presetName = availablePresets[idx - 1];
    builder.loadPreset(presetName);
    print(`✓ Loaded preset: ${presetName}\n`, 'green');
  }
}

/**
 * Filter configuration
 */
async function addFilters(builder) {
  printSection('3. Filter Configuration');

  print('Add filters to narrow down your word list.\n');
  print('Filters are applied in combination (AND logic).\n', 'dim');

  let addingFilters = true;

  while (addingFilters) {
    print('\n' + '─'.repeat(70) + '\n', 'dim');
    print('Available filter categories:\n');

    const categories = helpers.getFilterCategories(builder.spec.distribution);

    printOption('0', 'Done adding filters', 'Proceed to output configuration');
    categories.forEach((cat, idx) => {
      const capability = helpers.getFilterCapability(cat);
      const coverage = typeof capability.coverage === 'object'
        ? capability.coverage[builder.spec.distribution]
        : capability.coverage;

      const coverageStr = coverage !== null ? ` [${coverage}% coverage]` : '';
      printOption(String(idx + 1), capability.name + coverageStr, capability.description);
    });

    const choice = await question('\nSelect filter category (0-' + categories.length + ') [0]: ');
    const idx = parseInt(choice) || 0;

    if (idx === 0) {
      addingFilters = false;
    } else if (idx > 0 && idx <= categories.length) {
      const category = categories[idx - 1];
      await configureFilter(builder, category);
    }
  }
}

/**
 * Configure a specific filter
 */
async function configureFilter(builder, category) {
  const capability = helpers.getFilterCapability(category);

  console.log();
  print(`Configuring: ${capability.name}`, 'bright');
  print(`${capability.description}\n`, 'dim');

  if (capability.note) {
    print(`Note: ${capability.note}\n`, 'yellow');
  }

  if (category === 'character') {
    await configureCharacterFilter(builder);
  } else if (category === 'phrase') {
    await configurePhraseFilter(builder);
  } else if (category === 'frequency') {
    await configureFrequencyFilter(builder);
  } else if (category === 'pos') {
    await configurePOSFilter(builder);
  } else if (category === 'concreteness') {
    await configureConcretenessFilter(builder);
  } else if (category === 'labels') {
    await configureLabelsFilter(builder);
  } else if (category === 'policy') {
    await configurePolicyFilter(builder);
  }

  print('✓ Filter configured\n', 'green');
}

async function configureCharacterFilter(builder) {
  const exact = await question('Exact length (e.g., 5 for Wordle) [none]: ');
  if (exact) {
    builder.addFilter('character', 'exact_length', parseInt(exact));
  } else {
    const min = await question('Minimum length [none]: ');
    if (min) builder.addFilter('character', 'min_length', parseInt(min));

    const max = await question('Maximum length [none]: ');
    if (max) builder.addFilter('character', 'max_length', parseInt(max));
  }

  const pattern = await question('Regex pattern (e.g., ^[a-z]+$) [none]: ');
  if (pattern) builder.addFilter('character', 'pattern', pattern);
}

async function configurePhraseFilter(builder) {
  const maxWords = await question('Maximum word count (1=single words, 3=with idioms) [none]: ');
  if (maxWords) {
    builder.addFilter('phrase', 'max_words', parseInt(maxWords));
  }
}

async function configureFrequencyFilter(builder) {
  print('\nFrequency tiers:');
  for (const [tier, info] of Object.entries(CAPABILITIES.filters.frequency.tiers)) {
    print(`  ${tier}: ${info.description} (rank ${info.rank})`, 'dim');
  }

  const tiers = await question('\nInclude tiers (comma-separated, e.g., top1k,top10k) [all]: ');
  if (tiers) {
    const tierList = tiers.split(',').map(t => t.trim());
    builder.addFilter('frequency', 'tiers', tierList);
  }
}

async function configurePOSFilter(builder) {
  print('\nAvailable POS tags:');
  const options = CAPABILITIES.filters.pos.fields.include.options;
  print(`  ${options.join(', ')}\n`, 'dim');

  const include = await question('Include POS (comma-separated, e.g., noun,verb) [all]: ');
  if (include) {
    const posList = include.split(',').map(p => p.trim());
    builder.addFilter('pos', 'include', posList);
  }

  const requirePOS = await question('Exclude words without POS data? (y/n) [n]: ');
  if (requirePOS.toLowerCase() === 'y') {
    builder.addFilter('pos', 'require_pos', true);
  }
}

async function configureConcretenessFilter(builder) {
  print('\nConcreteness values:');
  for (const [value, desc] of Object.entries(CAPABILITIES.filters.concreteness.values)) {
    print(`  ${value}: ${desc}`, 'dim');
  }

  const values = await question('\nInclude values (comma-separated) [all]: ');
  if (values) {
    const valueList = values.split(',').map(v => v.trim());
    builder.addFilter('concreteness', 'values', valueList);
  }

  const require = await question('Exclude words without concreteness data? (y/n) [n]: ');
  if (require.toLowerCase() === 'y') {
    builder.addFilter('concreteness', 'require_concreteness', true);
  }
}

async function configureLabelsFilter(builder) {
  print('\nLabel filtering allows filtering by sociolinguistic properties (Plus only).');
  print('Available categories:', 'dim');
  print('  • register: vulgar, offensive, slang, formal, etc.', 'dim');
  print('  • temporal: archaic, obsolete, dated, modern', 'dim');
  print('  • domain: medical, legal, technical, computing, etc.', 'dim');
  print('  • region: en-US, en-GB, etc.\n', 'dim');

  let configuringLabels = true;

  while (configuringLabels) {
    print('\n' + '─'.repeat(50), 'dim');
    const category = await question('\nConfigure which category? (register/temporal/domain/region) [done to skip]: ');

    if (!category || category.toLowerCase() === 'done') {
      configuringLabels = false;
      continue;
    }

    const cat = category.trim().toLowerCase();
    if (!['register', 'temporal', 'domain', 'region'].includes(cat)) {
      print('Invalid category. Choose: register, temporal, domain, or region', 'yellow');
      continue;
    }

    const action = await question(`Include or exclude ${cat} labels? (include/exclude) [exclude]: `) || 'exclude';

    const options = cat === 'region'
      ? ['en-US', 'en-GB']
      : CAPABILITIES.filters.labels.fields[cat][action].options;

    print(`\nAvailable ${cat} labels:`, 'dim');
    print(`  ${options.join(', ')}\n`, 'dim');

    const labels = await question(`Labels to ${action} (comma-separated): `);
    if (labels) {
      const labelList = labels.split(',').map(l => l.trim());
      builder.addFilter('labels', `${cat}.${action}`, labelList);
      print(`✓ Added ${cat} ${action} filter`, 'green');
    }

    const more = await question('\nConfigure another label category? (y/n) [n]: ');
    if (more.toLowerCase() !== 'y') {
      configuringLabels = false;
    }
  }
}

async function configurePolicyFilter(builder) {
  print('\nPolicy filters are convenient shortcuts that combine multiple label filters.');
  print('(Requires Plus distribution for full effect)\n', 'dim');

  const familyFriendly = await question('Family-friendly? (excludes vulgar, offensive, derogatory words) (y/n) [n]: ');
  if (familyFriendly.toLowerCase() === 'y') {
    builder.setPolicyFilter('family_friendly', true);
    print('  ✓ Will exclude profanity and offensive language', 'green');
  }

  const modernOnly = await question('\nModern words only? (excludes archaic, obsolete, dated words) (y/n) [n]: ');
  if (modernOnly.toLowerCase() === 'y') {
    builder.setPolicyFilter('modern_only', true);
    print('  ✓ Will exclude old-fashioned words', 'green');
  }

  const noJargon = await question('\nNo technical jargon? (excludes medical, legal, technical, scientific) (y/n) [n]: ');
  if (noJargon.toLowerCase() === 'y') {
    builder.setPolicyFilter('no_jargon', true);
    print('  ✓ Will exclude specialized terminology', 'green');
  }
}

/**
 * Output configuration
 */
async function configureOutput(builder) {
  printSection('4. Output Configuration');

  const format = await question('Output format (text/json/csv/tsv) [text]: ') || 'text';
  builder.setOutput({ format });

  const limit = await question('Maximum number of words [unlimited]: ');
  if (limit) {
    builder.setOutput({ limit: parseInt(limit) });
  }

  const sortBy = await question('Sort by (alphabetical/score/frequency/length) [alphabetical]: ') || 'alphabetical';
  builder.setOutput({ sort_by: sortBy });

  print('✓ Output configured\n', 'green');
}

/**
 * Finish and save spec
 */
async function finishSpec(builder) {
  printSection('5. Review and Save');

  try {
    const { spec, validation } = builder.build();

    // Display validation warnings
    if (validation.warnings.length > 0) {
      print('\nWarnings:', 'yellow');
      validation.warnings.forEach(w => print(`  ⚠ ${w}`, 'yellow'));
      console.log();
    }

    // Display spec
    print('Generated specification:\n', 'bright');
    console.log(JSON.stringify(spec, null, 2));
    console.log();

    // Estimate result count
    const estimate = helpers.estimateResultCount(spec);
    print(`Estimated results: ~${estimate.toLocaleString()} words\n`, 'dim');

    // Save to file
    const defaultOutput = outputArg || 'wordlist-spec.json';
    const outputFile = await question(`Save to file [${defaultOutput}]: `) || defaultOutput;

    const outputPath = path.resolve(outputFile);
    fs.writeFileSync(outputPath, JSON.stringify(spec, null, 2));

    print(`\n✓ Specification saved to: ${outputPath}\n`, 'green');

    // Usage instructions
    print('To generate the word list, run:', 'bright');
    print(`  owlex filter ${outputPath}\n`, 'cyan');

    return spec;
  } catch (error) {
    print(`\nError: ${error.message}\n`, 'red');
    throw error;
  }
}

/**
 * Main entry point
 */
async function main() {
  try {
    await buildSpec();
    rl.close();
    process.exit(0);
  } catch (error) {
    print(`\nFatal error: ${error.message}`, 'red');
    console.error(error);
    rl.close();
    process.exit(1);
  }
}

// Run if executed directly
if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}

export { buildSpec };
