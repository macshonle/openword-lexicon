/**
 * OpenWord Lexicon - Word List Specification Builder
 *
 * Core decision engine for building word list filter specifications.
 * Works in both Node.js and browser environments.
 *
 * @module spec-builder
 */

/**
 * Filter capabilities metadata
 */
const CAPABILITIES = {
  distributions: {
    core: {
      name: 'Core',
      license: 'Ultra-permissive (Public Domain, UKACD)',
      sources: ['enable', 'eowl', 'wordnet', 'frequency'],
      totalWords: 208201,
      description: 'Best for commercial projects requiring permissive licensing'
    },
    plus: {
      name: 'Plus',
      license: 'Includes CC BY-SA 4.0 (requires attribution)',
      sources: ['enable', 'eowl', 'wikt', 'wordnet', 'frequency'],
      totalWords: 1039950,
      description: 'Maximum vocabulary coverage with label-based filtering'
    }
  },

  filters: {
    character: {
      name: 'Character-level filters',
      availableOn: ['core', 'plus'],
      coverage: 100,
      requiresMetadata: false,
      description: 'Filter by word length, patterns, regex',
      fields: {
        min_length: { type: 'integer', description: 'Minimum character count' },
        max_length: { type: 'integer', description: 'Maximum character count' },
        exact_length: { type: 'integer', description: 'Exact character count (e.g., 5 for Wordle)' },
        pattern: { type: 'string', description: 'Regular expression pattern' },
        starts_with: { type: 'string', description: 'Must start with this string' },
        ends_with: { type: 'string', description: 'Must end with this string' },
        contains: { type: 'string', description: 'Must contain this substring' },
        exclude_pattern: { type: 'string', description: 'Exclude if matches this pattern' }
      }
    },

    phrase: {
      name: 'Multi-word phrase filters',
      availableOn: ['core', 'plus'],
      coverage: 100,
      requiresMetadata: false,
      description: 'Filter by word count, single words vs phrases',
      fields: {
        min_words: { type: 'integer', description: 'Minimum word count' },
        max_words: { type: 'integer', description: 'Maximum word count (1=single words, 3=with idioms)' },
        is_phrase: { type: 'boolean', description: 'true=only phrases, false=only single words' }
      },
      note: 'Current dataset has very few multi-word phrases (~17 total)'
    },

    frequency: {
      name: 'Frequency tier filters',
      availableOn: ['core', 'plus'],
      coverage: 100,
      requiresMetadata: false,
      description: 'Filter by word commonality based on OpenSubtitles corpus',
      fields: {
        tiers: {
          type: 'array',
          options: ['top10', 'top100', 'top300', 'top500', 'top1k', 'top3k', 'top10k', 'top25k', 'top50k', 'rare'],
          description: 'Include only these frequency tiers'
        },
        min_tier: {
          type: 'enum',
          options: ['top10', 'top100', 'top300', 'top500', 'top1k', 'top3k', 'top10k', 'top25k', 'top50k', 'rare'],
          description: 'Minimum frequency (more common)'
        },
        max_tier: {
          type: 'enum',
          options: ['top10', 'top100', 'top300', 'top500', 'top1k', 'top3k', 'top10k', 'top25k', 'top50k', 'rare'],
          description: 'Maximum frequency (rarer)'
        },
        min_score: { type: 'integer', description: 'Minimum frequency score (0-100)' }
      },
      tiers: {
        top10: { rank: '1-10', description: 'Ultra-common function words', score: 100 },
        top100: { rank: '11-100', description: 'Core vocabulary for basic communication', score: 95 },
        top300: { rank: '101-300', description: 'Early reader / sight word level', score: 90 },
        top500: { rank: '301-500', description: 'Simple children\'s book vocabulary', score: 85 },
        top1k: { rank: '501-1,000', description: 'High-frequency everyday words', score: 80 },
        top3k: { rank: '1,001-3,000', description: 'Conversational fluency (~95% coverage)', score: 70 },
        top10k: { rank: '3,001-10,000', description: 'Standard educated vocabulary', score: 60 },
        top25k: { rank: '10,001-25,000', description: 'Extended vocabulary with specialized terms', score: 40 },
        top50k: { rank: '25,001-50,000', description: 'Rare words, technical terms, variants', score: 20 },
        rare: { rank: '>50,000', description: 'Very rare/specialized (not in dataset)', score: 5 }
      }
    },

    pos: {
      name: 'Part-of-speech filters',
      availableOn: ['core', 'plus'],
      coverage: 52.5,
      requiresMetadata: true,
      metadataSource: 'WordNet enrichment',
      description: 'Filter by grammatical role',
      fields: {
        include: {
          type: 'array',
          options: ['noun', 'verb', 'adjective', 'adverb', 'pronoun', 'preposition',
                   'conjunction', 'interjection', 'determiner', 'particle', 'auxiliary'],
          description: 'Include only these POS tags'
        },
        exclude: {
          type: 'array',
          options: ['noun', 'verb', 'adjective', 'adverb', 'pronoun', 'preposition',
                   'conjunction', 'interjection', 'determiner', 'particle', 'auxiliary'],
          description: 'Exclude these POS tags'
        },
        require_pos: { type: 'boolean', description: 'Exclude words without POS data' }
      },
      note: '~47.5% of entries lack POS data'
    },

    concreteness: {
      name: 'Noun concreteness filters',
      availableOn: ['core', 'plus'],
      coverage: { core: 34.5, plus: 8.8 },
      requiresMetadata: true,
      metadataSource: 'WordNet enrichment',
      description: 'Filter concrete vs abstract nouns',
      fields: {
        values: {
          type: 'array',
          options: ['concrete', 'abstract', 'mixed'],
          description: 'Include only these concreteness values'
        },
        require_concreteness: { type: 'boolean', description: 'Exclude words without concreteness data' }
      },
      values: {
        concrete: 'Physical, tangible objects (cat, table, rock)',
        abstract: 'Ideas, qualities, concepts (freedom, love, theory)',
        mixed: 'Both concrete and abstract senses (paper, face, bank)'
      },
      note: 'Core has better coverage (34.5%) than Plus (8.8%)'
    },

    labels: {
      name: 'Wiktionary label filters',
      availableOn: ['plus'],
      coverage: { register: 3.2, temporal: 5.0, domain: 3.3, region: 1.9 },
      requiresMetadata: true,
      metadataSource: 'Wiktionary',
      description: 'Filter by register, domain, temporal, regional labels',
      fields: {
        register: {
          include: {
            type: 'array',
            options: ['formal', 'informal', 'colloquial', 'slang', 'vulgar',
                     'offensive', 'derogatory', 'euphemistic', 'humorous', 'literary'],
            description: 'Include only these register labels'
          },
          exclude: {
            type: 'array',
            options: ['formal', 'informal', 'colloquial', 'slang', 'vulgar',
                     'offensive', 'derogatory', 'euphemistic', 'humorous', 'literary'],
            description: 'Exclude these register labels'
          }
        },
        region: {
          include: {
            type: 'array',
            options: ['en-US', 'en-GB'],
            description: 'Include only these regional variants'
          },
          exclude: {
            type: 'array',
            options: ['en-US', 'en-GB'],
            description: 'Exclude these regional variants'
          }
        },
        temporal: {
          include: {
            type: 'array',
            options: ['archaic', 'obsolete', 'dated', 'historical', 'modern'],
            description: 'Include only these temporal labels'
          },
          exclude: {
            type: 'array',
            options: ['archaic', 'obsolete', 'dated', 'historical', 'modern'],
            description: 'Exclude these temporal labels'
          }
        },
        domain: {
          include: {
            type: 'array',
            options: ['medical', 'legal', 'technical', 'scientific', 'military',
                     'nautical', 'botanical', 'zoological', 'computing', 'mathematics',
                     'music', 'art', 'religion', 'culinary', 'sports', 'business', 'finance'],
            description: 'Include only these domain labels'
          },
          exclude: {
            type: 'array',
            options: ['medical', 'legal', 'technical', 'scientific', 'military',
                     'nautical', 'botanical', 'zoological', 'computing', 'mathematics',
                     'music', 'art', 'religion', 'culinary', 'sports', 'business', 'finance'],
            description: 'Exclude these domain labels'
          }
        }
      },
      note: 'Only ~11.2% of Plus entries have ANY labels. Manual review recommended for profanity filtering.'
    },

    policy: {
      name: 'Policy-level filters',
      availableOn: ['plus'],
      coverage: null,
      requiresMetadata: true,
      description: 'Convenience filters that combine multiple criteria',
      fields: {
        family_friendly: {
          type: 'boolean',
          description: 'Exclude vulgar, offensive, derogatory words',
          expands: { 'labels.register.exclude': ['vulgar', 'offensive', 'derogatory'] }
        },
        modern_only: {
          type: 'boolean',
          description: 'Exclude archaic, obsolete, dated words',
          expands: { 'labels.temporal.exclude': ['archaic', 'obsolete', 'dated'] }
        },
        no_jargon: {
          type: 'boolean',
          description: 'Exclude technical, medical, legal, scientific domains',
          expands: { 'labels.domain.exclude': ['medical', 'legal', 'technical', 'scientific'] }
        }
      }
    },

    syllables: {
      name: 'Syllable count filters',
      availableOn: [],
      coverage: null,
      requiresMetadata: true,
      description: 'NOT YET IMPLEMENTED - Future feature',
      fields: {
        min: { type: 'integer', description: 'Minimum syllable count' },
        max: { type: 'integer', description: 'Maximum syllable count' },
        exact: { type: 'integer', description: 'Exact syllable count' },
        require_syllables: { type: 'boolean', description: 'Exclude words without syllable data' }
      },
      note: 'Analysis complete, implementation pending. Would provide ~18.79% coverage on Plus.'
    }
  },

  presets: {
    'wordle': {
      name: 'Wordle Word List',
      distribution: 'core',
      description: '5-letter common words for Wordle-style games',
      filters: {
        character: { exact_length: 5, pattern: '^[a-z]+$' },
        phrase: { max_words: 1 },
        frequency: { min_tier: 'top10k' }
      }
    },
    'kids-nouns': {
      name: 'Kids Game Words',
      distribution: 'core',
      description: 'Concrete nouns appropriate for children',
      filters: {
        character: { min_length: 3, max_length: 10 },
        phrase: { max_words: 1 },
        frequency: { tiers: ['top1k', 'top10k'] },
        pos: { include: ['noun'] },
        concreteness: { values: ['concrete'] },
        policy: { family_friendly: true, modern_only: true }
      }
    },
    'scrabble': {
      name: 'Scrabble Words',
      distribution: 'core',
      description: 'Single words for Scrabble',
      filters: {
        phrase: { max_words: 1 },
        frequency: { min_tier: 'top100k' }
      }
    },
    'profanity-blocklist': {
      name: 'Profanity Blocklist',
      distribution: 'plus',
      description: 'Flagged vulgar, offensive, and derogatory words',
      filters: {
        labels: {
          register: { include: ['vulgar', 'offensive', 'derogatory'] }
        }
      }
    },
    'crossword': {
      name: 'Crossword Puzzle Words',
      distribution: 'plus',
      description: 'Single words of varying difficulty',
      filters: {
        phrase: { max_words: 1 },
        character: { min_length: 3 }
      }
    }
  }
};

/**
 * Specification builder class
 */
class SpecBuilder {
  constructor() {
    this.spec = {
      version: '1.0',
      distribution: 'core',
      filters: {},
      output: {}
    };
  }

  /**
   * Set distribution
   */
  setDistribution(dist) {
    if (!CAPABILITIES.distributions[dist]) {
      throw new Error(`Invalid distribution: ${dist}`);
    }
    this.spec.distribution = dist;
    return this;
  }

  /**
   * Set name and description
   */
  setMetadata(name, description) {
    if (name) this.spec.name = name;
    if (description) this.spec.description = description;
    return this;
  }

  /**
   * Add a filter
   */
  addFilter(category, field, value) {
    if (!this.spec.filters[category]) {
      this.spec.filters[category] = {};
    }

    // Handle nested fields (e.g., 'labels.register.exclude')
    if (field.includes('.')) {
      const parts = field.split('.');
      let current = this.spec.filters[category];
      for (let i = 0; i < parts.length - 1; i++) {
        if (!current[parts[i]]) {
          current[parts[i]] = {};
        }
        current = current[parts[i]];
      }
      current[parts[parts.length - 1]] = value;
    } else {
      this.spec.filters[category][field] = value;
    }

    return this;
  }

  /**
   * Set policy filter (expands to multiple filters)
   */
  setPolicyFilter(policyName, enabled) {
    if (!enabled) return this;

    const policy = CAPABILITIES.filters.policy.fields[policyName];
    if (!policy || !policy.expands) {
      throw new Error(`Invalid policy: ${policyName}`);
    }

    for (const [path, value] of Object.entries(policy.expands)) {
      const parts = path.split('.');
      this.addFilter(parts[0], parts.slice(1).join('.'), value);
    }

    return this;
  }

  /**
   * Set output options
   */
  setOutput(options) {
    this.spec.output = { ...this.spec.output, ...options };
    return this;
  }

  /**
   * Load a preset
   */
  loadPreset(presetName) {
    const preset = CAPABILITIES.presets[presetName];
    if (!preset) {
      throw new Error(`Invalid preset: ${presetName}`);
    }

    this.spec.distribution = preset.distribution;
    if (preset.name) this.spec.name = preset.name;
    if (preset.description) this.spec.description = preset.description;
    this.spec.filters = JSON.parse(JSON.stringify(preset.filters)); // Deep clone

    return this;
  }

  /**
   * Validate the specification
   */
  validate() {
    const errors = [];
    const warnings = [];

    // Check distribution
    if (!this.spec.distribution) {
      errors.push('Distribution is required');
    }

    // Check filter availability
    for (const [category, filters] of Object.entries(this.spec.filters)) {
      const capability = CAPABILITIES.filters[category];

      if (!capability) {
        warnings.push(`Unknown filter category: ${category}`);
        continue;
      }

      // Check if filter is available on this distribution
      if (!capability.availableOn.includes(this.spec.distribution)) {
        errors.push(
          `Filter '${category}' is not available on '${this.spec.distribution}' distribution. ` +
          `Available on: ${capability.availableOn.join(', ')}`
        );
      }

      // Warn about low coverage
      if (capability.coverage !== null && capability.coverage < 50) {
        const coverage = typeof capability.coverage === 'object'
          ? capability.coverage[this.spec.distribution]
          : capability.coverage;

        if (coverage < 50) {
          warnings.push(
            `Filter '${category}' has low coverage (${coverage}%) - many words may lack this metadata`
          );
        }
      }
    }

    return { valid: errors.length === 0, errors, warnings };
  }

  /**
   * Get the final specification
   */
  build() {
    const validation = this.validate();

    if (!validation.valid) {
      throw new Error(
        `Invalid specification:\n${validation.errors.join('\n')}`
      );
    }

    // Clean up empty objects
    const spec = JSON.parse(JSON.stringify(this.spec));
    if (Object.keys(spec.filters).length === 0) {
      delete spec.filters;
    }
    if (Object.keys(spec.output).length === 0) {
      delete spec.output;
    }

    return {
      spec,
      validation
    };
  }

  /**
   * Export as JSON string
   */
  toJSON(pretty = true) {
    const { spec } = this.build();
    return pretty ? JSON.stringify(spec, null, 2) : JSON.stringify(spec);
  }
}

/**
 * Helper functions
 */
const helpers = {
  /**
   * Get all available filter categories
   */
  getFilterCategories(distribution = null) {
    if (!distribution) {
      return Object.keys(CAPABILITIES.filters);
    }

    return Object.entries(CAPABILITIES.filters)
      .filter(([_, cap]) => cap.availableOn.includes(distribution))
      .map(([name, _]) => name);
  },

  /**
   * Get filter capability details
   */
  getFilterCapability(category) {
    return CAPABILITIES.filters[category] || null;
  },

  /**
   * Get distribution details
   */
  getDistribution(name) {
    return CAPABILITIES.distributions[name] || null;
  },

  /**
   * Get all presets
   */
  getPresets() {
    return Object.keys(CAPABILITIES.presets);
  },

  /**
   * Get preset details
   */
  getPreset(name) {
    return CAPABILITIES.presets[name] || null;
  },

  /**
   * Check if a filter requires Plus distribution
   */
  requiresPlus(category) {
    const cap = CAPABILITIES.filters[category];
    return cap && cap.availableOn.includes('plus') && !cap.availableOn.includes('core');
  },

  /**
   * Estimate result count based on filters
   * (Very rough estimation based on coverage percentages)
   */
  estimateResultCount(spec) {
    const dist = CAPABILITIES.distributions[spec.distribution];
    let estimate = dist.totalWords;

    // Apply rough multipliers based on filters
    if (spec.filters.frequency) {
      if (spec.filters.frequency.tiers) {
        // Rough tier percentages
        const tierPercentages = {
          top10: 0.000048, top100: 0.00048, top1k: 0.0048,
          top10k: 0.048, top100k: 0.48, rare: 0.52
        };
        const tierMultiplier = spec.filters.frequency.tiers
          .reduce((sum, tier) => sum + tierPercentages[tier], 0);
        estimate *= tierMultiplier;
      }
    }

    if (spec.filters.pos && spec.filters.pos.require_pos) {
      estimate *= 0.525; // 52.5% coverage
    }

    if (spec.filters.concreteness && spec.filters.concreteness.require_concreteness) {
      const coverage = spec.distribution === 'core' ? 0.345 : 0.088;
      estimate *= coverage;
    }

    if (spec.filters.character) {
      if (spec.filters.character.exact_length) {
        estimate *= 0.05; // Rough guess for specific length
      }
    }

    return Math.round(estimate);
  }
};

/**
 * Export for Node.js and browser
 */
if (typeof module !== 'undefined' && module.exports) {
  // Node.js
  module.exports = {
    SpecBuilder,
    CAPABILITIES,
    helpers
  };
} else {
  // Browser
  window.SpecBuilder = SpecBuilder;
  window.CAPABILITIES = CAPABILITIES;
  window.specBuilderHelpers = helpers;
}
