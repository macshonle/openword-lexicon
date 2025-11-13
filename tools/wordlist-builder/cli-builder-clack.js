#!/usr/bin/env node
/**
 * OpenWord Lexicon - Interactive CLI Word List Builder (with Clack UI)
 *
 * Enhanced version using @clack/prompts for better UX.
 * Falls back to basic CLI if @clack/prompts is not installed.
 *
 * Usage:
 *   npm install  # Install @clack/prompts
 *   node cli-builder-clack.js [--preset <name>] [--output <file>]
 */

import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Try to load @clack/prompts
let clack;
try {
  clack = await import('@clack/prompts');
} catch (e) {
  console.error('Error: @clack/prompts not installed.');
  console.error('Please run: npm install');
  console.error('\nFalling back to basic CLI builder...\n');
  // Fall back to basic CLI
  await import('./cli-builder.js');
  process.exit(0);
}

// Load builder modules
const { SpecBuilder, CAPABILITIES, helpers } = await import('./spec-builder.js');

// Parse command line arguments
const args = process.argv.slice(2);
const presetArg = args.indexOf('--preset') !== -1 ? args[args.indexOf('--preset') + 1] : null;
const outputArg = args.indexOf('--output') !== -1 ? args[args.indexOf('--output') + 1] : null;

/**
 * Main builder workflow with Clack UI
 */
async function buildSpec() {
  const builder = new SpecBuilder();

  console.clear();

  clack.intro('OpenWord Lexicon - Interactive Word List Builder');

  // Check for preset
  if (presetArg) {
    const preset = helpers.getPreset(presetArg);
    if (preset) {
      clack.note(`${preset.name}\n${preset.description}`, 'Loading preset');
      builder.loadPreset(presetArg);

      const usePreset = await clack.confirm({
        message: 'Use this preset as-is?',
        initialValue: true
      });

      if (clack.isCancel(usePreset) || usePreset) {
        return await finishSpec(builder);
      }

      clack.log.info('You can modify the preset below');
    } else {
      clack.log.warn(`Preset '${presetArg}' not found. Starting from scratch.`);
    }
  }

  // Step 1: Distribution selection
  const dist = await clack.select({
    message: 'Choose distribution',
    options: [
      {
        value: 'core',
        label: 'Core',
        hint: '208K words, ultra-permissive licenses'
      },
      {
        value: 'plus',
        label: 'Plus',
        hint: '1M words, includes Wiktionary (CC BY-SA)'
      }
    ],
    initialValue: 'core'
  });

  if (clack.isCancel(dist)) {
    clack.cancel('Operation cancelled');
    process.exit(0);
  }

  builder.setDistribution(dist);

  // Step 2: Name and description
  const name = await clack.text({
    message: 'Name for this word list (optional)',
    placeholder: 'My Word List'
  });

  if (!clack.isCancel(name) && name) {
    const description = await clack.text({
      message: 'Description (optional)',
      placeholder: 'Custom filtered word list'
    });

    if (!clack.isCancel(description)) {
      builder.setMetadata(name || null, description || null);
    }
  }

  // Step 3: Preset selection
  if (!presetArg) {
    const presets = helpers.getPresets();
    const availablePresets = presets.filter(name => {
      const preset = helpers.getPreset(name);
      return preset.distribution === dist;
    });

    if (availablePresets.length > 0) {
      const usePreset = await clack.select({
        message: 'Start from a preset?',
        options: [
          { value: null, label: 'No preset', hint: 'Build from scratch' },
          ...availablePresets.map(name => {
            const preset = helpers.getPreset(name);
            return {
              value: name,
              label: preset.name,
              hint: preset.description
            };
          })
        ]
      });

      if (!clack.isCancel(usePreset) && usePreset) {
        builder.loadPreset(usePreset);
        clack.log.success(`Loaded preset: ${usePreset}`);
      }
    }
  }

  // Step 4: Add filters
  await addFilters(builder, dist);

  // Step 5: Configure output
  await configureOutput(builder);

  // Step 6: Finish
  return await finishSpec(builder);
}

/**
 * Filter configuration with Clack multi-select
 */
async function addFilters(builder, dist) {
  const s = clack.spinner();
  s.start('Loading filter options');

  const categories = helpers.getFilterCategories(dist);
  const filterOptions = categories.map(cat => {
    const capability = helpers.getFilterCapability(cat);
    const coverage = typeof capability.coverage === 'object'
      ? capability.coverage[dist]
      : capability.coverage;

    const coverageHint = coverage !== null ? ` (${coverage}% coverage)` : '';

    return {
      value: cat,
      label: capability.name,
      hint: capability.description + coverageHint
    };
  });

  s.stop('Ready');

  const selectedFilters = await clack.multiselect({
    message: 'Select filter categories to configure',
    options: filterOptions,
    required: false
  });

  if (clack.isCancel(selectedFilters)) {
    return;
  }

  for (const category of selectedFilters) {
    await configureFilter(builder, category);
  }
}

/**
 * Configure a specific filter
 */
async function configureFilter(builder, category) {
  const capability = helpers.getFilterCapability(category);

  clack.log.step(capability.name);

  if (category === 'character') {
    const exactLength = await clack.text({
      message: 'Exact length (e.g., 5 for Wordle)',
      placeholder: 'Leave empty for range',
      validate: (value) => {
        if (value && isNaN(parseInt(value))) return 'Must be a number';
      }
    });

    if (!clack.isCancel(exactLength) && exactLength) {
      builder.addFilter('character', 'exact_length', parseInt(exactLength));
    } else if (!clack.isCancel(exactLength)) {
      // Ask for range
      const group = await clack.group({
        min: () => clack.text({
          message: 'Minimum length',
          placeholder: '3',
          validate: (value) => {
            if (value && isNaN(parseInt(value))) return 'Must be a number';
          }
        }),
        max: () => clack.text({
          message: 'Maximum length',
          placeholder: '15',
          validate: (value) => {
            if (value && isNaN(parseInt(value))) return 'Must be a number';
          }
        })
      });

      if (group.min) builder.addFilter('character', 'min_length', parseInt(group.min));
      if (group.max) builder.addFilter('character', 'max_length', parseInt(group.max));
    }
  } else if (category === 'frequency') {
    const tiers = await clack.multiselect({
      message: 'Select frequency tiers',
      options: [
        { value: 'top10', label: 'top10', hint: 'Ultra-common (1-10)' },
        { value: 'top100', label: 'top100', hint: 'Core vocabulary (11-100)' },
        { value: 'top300', label: 'top300', hint: 'Early reader (101-300)' },
        { value: 'top500', label: 'top500', hint: 'Simple vocabulary (301-500)' },
        { value: 'top1k', label: 'top1k', hint: 'Everyday words (501-1K)' },
        { value: 'top3k', label: 'top3k', hint: 'Conversational fluency (1K-3K)' },
        { value: 'top10k', label: 'top10k', hint: 'Educated vocabulary (3K-10K)' },
        { value: 'top25k', label: 'top25k', hint: 'Extended vocabulary (10K-25K)' },
        { value: 'top50k', label: 'top50k', hint: 'Rare/technical (25K-50K)' },
        { value: 'rare', label: 'rare', hint: 'Very rare (>50K)' }
      ],
      initialValues: ['top1k', 'top3k', 'top10k']
    });

    if (!clack.isCancel(tiers) && tiers.length > 0 && tiers.length < 10) {
      builder.addFilter('frequency', 'tiers', tiers);
    }
  } else if (category === 'policy') {
    const policies = await clack.multiselect({
      message: 'Select policy filters',
      options: [
        { value: 'family_friendly', label: 'Family-friendly', hint: 'Exclude profanity' },
        { value: 'modern_only', label: 'Modern only', hint: 'Exclude archaic words' },
        { value: 'no_jargon', label: 'No jargon', hint: 'Exclude technical terms' }
      ]
    });

    if (!clack.isCancel(policies)) {
      policies.forEach(policy => builder.setPolicyFilter(policy, true));
    }
  }

  // Add other filter types as needed...
}

/**
 * Output configuration
 */
async function configureOutput(builder) {
  const format = await clack.select({
    message: 'Output format',
    options: [
      { value: 'text', label: 'Plain Text', hint: 'One word per line' },
      { value: 'json', label: 'JSON', hint: 'JSON array' },
      { value: 'jsonl', label: 'JSON Lines', hint: 'One JSON object per line' },
      { value: 'csv', label: 'CSV', hint: 'Comma-separated values' },
      { value: 'tsv', label: 'TSV', hint: 'Tab-separated values' }
    ],
    initialValue: 'text'
  });

  if (!clack.isCancel(format)) {
    builder.setOutput({ format });
  }

  const sortBy = await clack.select({
    message: 'Sort by',
    options: [
      { value: 'alphabetical', label: 'Alphabetical' },
      { value: 'frequency', label: 'Frequency', hint: 'Most frequent first' },
      { value: 'length', label: 'Length', hint: 'Shortest first' },
      { value: 'score', label: 'Score', hint: 'Highest score first' }
    ],
    initialValue: 'alphabetical'
  });

  if (!clack.isCancel(sortBy)) {
    builder.setOutput({ sort_by: sortBy });
  }
}

/**
 * Finish and save spec
 */
async function finishSpec(builder) {
  const s = clack.spinner();
  s.start('Validating specification');

  try {
    const { spec, validation } = builder.build();

    s.stop('Validation complete');

    // Display warnings
    if (validation.warnings.length > 0) {
      clack.log.warn('Warnings:');
      validation.warnings.forEach(w => clack.log.message(`  • ${w}`));
    }

    // Show spec
    clack.note(JSON.stringify(spec, null, 2), 'Generated Specification');

    // Estimate
    const estimate = helpers.estimateResultCount(spec);
    clack.log.info(`Estimated results: ~${estimate.toLocaleString()} words`);

    // Save to file
    const defaultOutput = outputArg || 'wordlist-spec.json';
    const outputFile = await clack.text({
      message: 'Save to file',
      placeholder: defaultOutput,
      defaultValue: defaultOutput
    });

    if (clack.isCancel(outputFile)) {
      clack.cancel('Operation cancelled');
      process.exit(1);
    }

    const outputPath = path.resolve(outputFile);
    fs.writeFileSync(outputPath, JSON.stringify(spec, null, 2));

    clack.outro(`Specification saved to: ${outputPath}\n\nTo generate the word list, run:\n  owlex filter ${outputPath}`);

    return spec;
  } catch (error) {
    s.stop('Validation failed');
    clack.log.error(`Error: ${error.message}`);
    throw error;
  }
}

/**
 * Main entry point
 */
async function main() {
  try {
    await buildSpec();
    process.exit(0);
  } catch (error) {
    if (!clack.isCancel(error)) {
      clack.log.error(`Fatal error: ${error.message}`);
      console.error(error);
    }
    process.exit(1);
  }
}

main();
