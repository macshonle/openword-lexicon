"""
Standalone WordNet enrichment tests - minimal dependencies.

Simple baseline tests that document current NLTK WordNet behavior without
complex imports or fixtures.

Run with: python tests/test_wordnet_standalone.py
Or: pytest tests/test_wordnet_standalone.py -v
"""

import json
import sys
import traceback
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_imports():
    """Test that we can import required modules."""
    print("\n=== Testing Imports ===")

    try:
        import nltk
        print(f"✓ NLTK version: {nltk.__version__}")
    except ImportError as e:
        print(f"✗ NLTK import failed: {e}")
        return False

    try:
        from openword.wordnet_enrich import (
            get_concreteness,
            get_wordnet_pos,
            enrich_entry,
            ensure_wordnet_data
        )
        print("✓ WordNet enrichment functions imported")

        # Ensure data
        ensure_wordnet_data()
        print("✓ WordNet data available")

        return {
            "get_concreteness": get_concreteness,
            "get_wordnet_pos": get_wordnet_pos,
            "enrich_entry": enrich_entry
        }
    except ImportError as e:
        print(f"✗ openword.wordnet_enrich import failed: {e}")
        return False
    except Exception as e:
        print(f"✗ WordNet data check failed: {e}")
        return False


def test_concreteness(funcs):
    """Test concreteness classification."""
    print("\n=== Testing Concreteness ===")

    get_concreteness = funcs["get_concreteness"]

    test_cases = {
        "concrete": ["castle", "apple", "hammer", "dog"],
        "abstract": ["freedom", "justice", "happiness", "love"],
        "mixed": ["paper", "bank", "light"],
    }

    results = {}

    for expected, words in test_cases.items():
        results[expected] = []
        for word in words:
            try:
                actual = get_concreteness(word)
                status = "✓" if actual == expected or actual is None else "?"
                results[expected].append({
                    "word": word,
                    "expected": expected,
                    "actual": actual,
                    "status": status
                })
                print(f"  {status} {word:15} expected={expected:10} actual={actual}")
            except Exception as e:
                print(f"  ✗ {word:15} ERROR: {e}")
                results[expected].append({
                    "word": word,
                    "error": str(e)
                })

    return results


def test_pos_tagging(funcs):
    """Test POS tagging."""
    print("\n=== Testing POS Tagging ===")

    get_wordnet_pos = funcs["get_wordnet_pos"]

    test_cases = {
        "noun": ["castle", "dog", "table"],
        "verb": ["run", "think", "eat"],
        "adjective": ["happy", "red", "big"],
        "adverb": ["quickly", "slowly", "happily"],
    }

    results = {}

    for expected_pos, words in test_cases.items():
        results[expected_pos] = []
        for word in words:
            try:
                pos_tags = get_wordnet_pos(word)
                has_expected = expected_pos in pos_tags if pos_tags else False
                status = "✓" if has_expected else "?"
                results[expected_pos].append({
                    "word": word,
                    "expected": expected_pos,
                    "actual": pos_tags,
                    "status": status
                })
                print(f"  {status} {word:15} expected={expected_pos:10} actual={pos_tags}")
            except Exception as e:
                print(f"  ✗ {word:15} ERROR: {e}")
                results[expected_pos].append({
                    "word": word,
                    "error": str(e)
                })

    return results


def test_edge_cases(funcs):
    """Test edge cases."""
    print("\n=== Testing Edge Cases ===")

    get_concreteness = funcs["get_concreteness"]
    get_wordnet_pos = funcs["get_wordnet_pos"]

    edge_words = [
        "nonexistentword12345",  # Not in WordNet
        "a",  # Single letter
        "selfie",  # Modern neologism
        "cryptocurrency",  # Modern compound
        "café",  # Accented
    ]

    results = []

    for word in edge_words:
        try:
            pos = get_wordnet_pos(word)
            conc = get_concreteness(word)
            results.append({
                "word": word,
                "pos": pos,
                "concreteness": conc,
                "status": "✓"
            })
            print(f"  ✓ {word:20} pos={pos}, concreteness={conc}")
        except Exception as e:
            print(f"  ✗ {word:20} ERROR: {e}")
            results.append({
                "word": word,
                "error": str(e),
                "traceback": traceback.format_exc()
            })

    return results


def test_full_enrichment(funcs):
    """Test full entry enrichment."""
    print("\n=== Testing Full Enrichment ===")

    enrich_entry = funcs["enrich_entry"]

    # Test entry without POS
    entry1 = {
        "word": "castle",
        "pos": [],
        "labels": {},
        "is_phrase": False,
        "lemma": None,
        "sources": ["test"]
    }

    print(f"  Input: {json.dumps(entry1, indent=4)}")

    try:
        enriched1 = enrich_entry(entry1.copy())
        print(f"  Output: {json.dumps(enriched1, indent=4)}")

        # Check enrichment
        pos_added = len(enriched1.get("pos", [])) > 0
        has_wordnet_source = "wordnet" in enriched1.get("sources", [])

        print(f"  ✓ POS added: {pos_added}")
        print(f"  ✓ WordNet source tracked: {has_wordnet_source}")

    except Exception as e:
        print(f"  ✗ ERROR: {e}")
        print(f"  Traceback: {traceback.format_exc()}")

    # Test multi-word (should skip)
    entry2 = {
        "word": "give up",
        "pos": [],
        "labels": {},
        "is_phrase": True,
        "word_count": 2,
        "lemma": None,
        "sources": ["test"]
    }

    print(f"\n  Multi-word input: {entry2['word']}")

    try:
        enriched2 = enrich_entry(entry2.copy())
        unchanged = enriched2 == entry2
        print(f"  ✓ Skipped (unchanged): {unchanged}")
    except Exception as e:
        print(f"  ✗ ERROR: {e}")


def main():
    """Run all tests."""
    print("="*60)
    print("WordNet Enrichment Baseline Tests")
    print("="*60)

    # Test imports
    funcs = test_imports()
    if not funcs:
        print("\n✗ FATAL: Could not import required modules")
        print("Run: uv run python tests/test_wordnet_standalone.py")
        sys.exit(1)

    # Run tests
    concreteness_results = test_concreteness(funcs)
    pos_results = test_pos_tagging(funcs)
    edge_results = test_edge_cases(funcs)
    test_full_enrichment(funcs)

    # Save results
    all_results = {
        "concreteness": concreteness_results,
        "pos_tagging": pos_results,
        "edge_cases": edge_results
    }

    output_file = Path(__file__).parent / "wordnet_baseline_results.json"
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print("\n" + "="*60)
    print(f"✓ Results saved to: {output_file}")
    print("="*60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
