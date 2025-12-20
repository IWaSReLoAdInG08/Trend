# coding=utf-8
"""
Frequency Word Configuration Loading Module

Responsible for loading frequency word rules from configuration files, supporting:
- Normal word groups
- Required words (+ prefix)
- Filter words (! prefix)
- Global filter words ([GLOBAL_FILTER] section)
- Maximum display count (@ prefix)
"""

import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional


def load_frequency_words(
    frequency_file: Optional[str] = None,
) -> Tuple[List[Dict], List[str], List[str]]:
    """
    Load frequency word configuration

    Configuration file format description:
    - Each word group is separated by a blank line
    - [GLOBAL_FILTER] section defines global filter words
    - [WORD_GROUPS] section defines word groups (default)

    Word group syntax:
    - Normal word: Written directly, matches anywhere
    - +Word: Required word, all required words must match
    - !Word: Filter word, excludes if matched
    - @Number: Max display count for this group

    Args:
        frequency_file: Frequency word config file path, defaults to FREQUENCY_WORDS_PATH env var or config/frequency_words.txt

    Returns:
        (Word group list, In-group filter words, Global filter words)

    Raises:
        FileNotFoundError: Frequency word file not found
    """
    if frequency_file is None:
        frequency_file = os.environ.get(
            "FREQUENCY_WORDS_PATH", "config/frequency_words.txt"
        )

    frequency_path = Path(frequency_file)
    if not frequency_path.exists():
        raise FileNotFoundError(f"Frequency word file {frequency_file} not found")

    with open(frequency_path, "r", encoding="utf-8") as f:
        content = f.read()

    word_groups = [group.strip() for group in content.split("\n\n") if group.strip()]

    processed_groups = []
    filter_words = []
    global_filters = []

    # Default section (backward compatibility)
    current_section = "WORD_GROUPS"

    for group in word_groups:
        lines = [line.strip() for line in group.split("\n") if line.strip()]

        if not lines:
            continue

        # Check if it is a section marker
        if lines[0].startswith("[") and lines[0].endswith("]"):
            section_name = lines[0][1:-1].upper()
            if section_name in ("GLOBAL_FILTER", "WORD_GROUPS"):
                current_section = section_name
                lines = lines[1:]  # Remove marker line

        # Process global filter section
        if current_section == "GLOBAL_FILTER":
            # Directly add all non-empty lines to global filter list
            for line in lines:
                # Ignore special syntax prefixes, only extract plain text
                if line.startswith(("!", "+", "@")):
                    continue  # Global filter section does not support special syntax
                if line:
                    global_filters.append(line)
            continue

        # Process word group section
        words = lines

        group_required_words = []
        group_normal_words = []
        group_filter_words = []
        group_max_count = 0  # Default no limit

        for word in words:
            if word.startswith("@"):
                # Parse max display count (only accepts positive integers)
                try:
                    count = int(word[1:])
                    if count > 0:
                        group_max_count = count
                except (ValueError, IndexError):
                    pass  # Ignore invalid @number format
            elif word.startswith("!"):
                filter_words.append(word[1:])
                group_filter_words.append(word[1:])
            elif word.startswith("+"):
                group_required_words.append(word[1:])
            else:
                group_normal_words.append(word)

        if group_required_words or group_normal_words:
            if group_normal_words:
                group_key = " ".join(group_normal_words)
            else:
                group_key = " ".join(group_required_words)

            processed_groups.append(
                {
                    "required": group_required_words,
                    "normal": group_normal_words,
                    "group_key": group_key,
                    "max_count": group_max_count,
                }
            )

    return processed_groups, filter_words, global_filters


def matches_word_groups(
    title: str,
    word_groups: List[Dict],
    filter_words: List[str],
    global_filters: Optional[List[str]] = None
) -> bool:
    """
    Check if title matches word group rules

    Args:
        title: Title text
        word_groups: Word group list
        filter_words: Filter words list
        global_filters: Global filter words list

    Returns:
        Whether it matches
    """
    # Defensive type check: ensure title is a valid string
    if not isinstance(title, str):
        title = str(title) if title is not None else ""
    if not title.strip():
        return False

    title_lower = title.lower()

    # Global filter check (highest priority)
    if global_filters:
        if any(global_word.lower() in title_lower for global_word in global_filters):
            return False

    # If no word groups configured, match all titles (support showing all news)
    if not word_groups:
        return True

    # Filter words check
    if any(filter_word.lower() in title_lower for filter_word in filter_words):
        return False

    # Word group matching check
    for group in word_groups:
        required_words = group["required"]
        normal_words = group["normal"]

        # Required words check
        if required_words:
            all_required_present = all(
                req_word.lower() in title_lower for req_word in required_words
            )
            if not all_required_present:
                continue

        # Normal words check
        if normal_words:
            any_normal_present = any(
                normal_word.lower() in title_lower for normal_word in normal_words
            )
            if not any_normal_present:
                continue

        return True

    return False
