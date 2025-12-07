"""Pytest configuration and shared fixtures."""
import pytest
import tempfile
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_words():
    """Sample word list for testing (small dataset)."""
    return [
        "cat",
        "dog",
        "bird",
        "fish",
        "snake",
        "horse",
        "cow",
        "pig",
        "sheep",
        "goat",
        "chicken",
        "duck",
        "goose",
        "turkey",
        "rabbit",
        "mouse",
        "rat",
        "fox",
        "wolf",
        "bear",
        "lion",
        "tiger",
        "elephant",
        "giraffe",
        "zebra",
        "monkey",
        "gorilla",
        "kangaroo",
        "koala",
        "panda",
        "penguin",
        "owl",
        "eagle",
        "hawk",
        "crow",
        "parrot",
        "swan",
        "peacock",
        "flamingo",
        "pelican",
        "heron",
        "dolphin",
        "whale",
        "shark",
        "octopus",
        "starfish",
        "crab",
        "lobster",
        "shrimp",
        "oyster",
        "clam",
        "snail",
        "butterfly",
        "bee",
        "ant",
        "spider",
        "beetle",
        "cricket",
        "grasshopper",
        "dragonfly",
        "firefly",
        "moth",
        "mosquito",
        "fly",
        "flea",
        "tick",
        "worm",
        "slug",
        "leech",
        "scorpion",
        "centipede",
        "millipede",
        "lizard",
        "turtle",
        "frog",
        "toad",
        "salamander",
        "alligator",
        "crocodile",
        "iguana",
        "chameleon",
        "gecko",
        "python",
        "cobra",
        "viper",
        "rattlesnake",
        "boa",
        "anaconda",
        "mamba",
        "coral",
        "seahorse",
        "jellyfish",
        "squid",
        "eel",
        "salmon",
        "trout",
        "bass",
        "tuna",
        "swordfish",
        "marlin",
        "barracuda",
        "pike",
        "perch",
    ]


@pytest.fixture
def sample_metadata(sample_words):
    """Sample metadata entries for testing."""
    entries = []
    pos_options = [["noun"], ["verb"], ["adjective"], ["noun", "verb"]]

    for i, word in enumerate(sample_words):
        entry = {
            "id": word,
            "pos": pos_options[i % len(pos_options)],
            "labels": {},
            "is_phrase": False,
            "lemma": None,
            "sources": ["test"]
        }
        entries.append(entry)

    return entries
