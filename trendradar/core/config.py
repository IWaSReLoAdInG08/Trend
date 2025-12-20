# coding=utf-8
"""
Config Utility Module - Multi-account config parsing and validation

Provides parsing, validation, and limitation functions for multi-account push configurations
"""

from typing import Dict, List, Optional, Tuple


def parse_multi_account_config(config_value: str, separator: str = ";") -> List[str]:
    """
    Parse multi-account configuration, return list of accounts

    Args:
        config_value: Configuration string, multiple accounts separated by separator
        separator: Separator, defaults to ;

    Returns:
        List of accounts, empty strings are preserved (for placeholder)

    Examples:
        >>> parse_multi_account_config("url1;url2;url3")
        ['url1', 'url2', 'url3']
        >>> parse_multi_account_config(";token2")  # First account has no token
        ['', 'token2']
        >>> parse_multi_account_config("")
        []
    """
    if not config_value:
        return []
    # Preserve empty strings for placeholders (e.g. ";token2" means first account has no token)
    accounts = [acc.strip() for acc in config_value.split(separator)]
    # Filter out if all are empty
    if all(not acc for acc in accounts):
        return []
    return accounts


def validate_paired_configs(
    configs: Dict[str, List[str]],
    channel_name: str,
    required_keys: Optional[List[str]] = None
) -> Tuple[bool, int]:
    """
    Validate if paired configurations have consistent counts

    For channels requiring multiple paired config items (e.g. Telegram token and chat_id),
    validate that the number of accounts for all config items is consistent.

    Args:
        configs: Config dictionary, key is config name, value is list of accounts
        channel_name: Channel name, for log output
        required_keys: List of keys that must have values

    Returns:
        (is_valid, account_count)

    Examples:
        >>> validate_paired_configs({
        ...     "token": ["t1", "t2"],
        ...     "chat_id": ["c1", "c2"]
        ... }, "Telegram", ["token", "chat_id"])
        (True, 2)

        >>> validate_paired_configs({
        ...     "token": ["t1", "t2"],
        ...     "chat_id": ["c1"]  # Mismatched count
        ... }, "Telegram", ["token", "chat_id"])
        (False, 0)
    """
    # Filter out empty lists
    non_empty_configs = {k: v for k, v in configs.items() if v}

    if not non_empty_configs:
        return True, 0

    # Check required keys
    if required_keys:
        for key in required_keys:
            if key not in non_empty_configs or not non_empty_configs[key]:
                return True, 0  # Required key is empty, treated as not configured

    # Get lengths of all non-empty configs
    lengths = {k: len(v) for k, v in non_empty_configs.items()}
    unique_lengths = set(lengths.values())

    if len(unique_lengths) > 1:
        print(f"❌ {channel_name} Config Error: Paired config counts inconsistent, skipping this channel")
        for key, length in lengths.items():
            print(f"   - {key}: {length}")
        return False, 0

    return True, list(unique_lengths)[0] if unique_lengths else 0


def limit_accounts(
    accounts: List[str],
    max_count: int,
    channel_name: str
) -> List[str]:
    """
    Limit number of accounts

    When configured accounts exceed max limit, only first N accounts are used,
    and a warning is printed.

    Args:
        accounts: List of accounts
        max_count: Max number of accounts
        channel_name: Channel name, for log output

    Returns:
        List of accounts after limitation

    Examples:
        >>> limit_accounts(["a1", "a2", "a3"], 2, "Feishu")
        ⚠️ Feishu configured 3 accounts, exceeding limit 2, using first 2
        ['a1', 'a2']
    """
    if len(accounts) > max_count:
        print(f"⚠️ {channel_name} configured {len(accounts)} accounts, exceeding limit {max_count}, using first {max_count}")
        print(f"   ⚠️ Warning: If you are a fork user, too many accounts may cause GitHub Actions timeout or account risks")
        return accounts[:max_count]
    return accounts


def get_account_at_index(accounts: List[str], index: int, default: str = "") -> str:
    """
    Safely get account value at index

    Returns default value if index out of range or value is empty.

    Args:
        accounts: List of accounts
        index: Index
        default: Default value

    Returns:
        Account value or default

    Examples:
        >>> get_account_at_index(["a", "b", "c"], 1)
        'b'
        >>> get_account_at_index(["a", "", "c"], 1, "default")
        'default'
        >>> get_account_at_index(["a"], 5, "default")
        'default'
    """
    if index < len(accounts):
        return accounts[index] if accounts[index] else default
    return default
