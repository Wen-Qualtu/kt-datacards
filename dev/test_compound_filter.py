#!/usr/bin/env python3
"""Test the compound word filtering"""
text_lower = "angel of death"
team_name = "angels-of-death"

# Current logic
text_parts = text_lower.split('-')
team_parts = team_name.lower().split('-')

print(f"Text: '{text_lower}'")
print(f"Team: '{team_name}'")
print(f"Text parts: {text_parts}")
print(f"Team parts: {team_parts}")
print(f"Lengths match: {len(text_parts) == len(team_parts)}")
print(f"Length > 1: {len(text_parts) > 1}")

# The issue: "angel of death" doesn't have dashes, so split('-') gives ["angel of death"]
# We need to split on spaces AND dashes

import re
text_parts = re.split(r'[-\s]+', text_lower.strip())
team_parts = re.split(r'[-\s]+', team_name.lower().strip())

print(f"\nWith proper split:")
print(f"Text parts: {text_parts}")
print(f"Team parts: {team_parts}")
print(f"First parts: '{text_parts[0]}' vs '{team_parts[0]}'")
print(f"Rest equal: {text_parts[1:] == team_parts[1:]}")
print(f"Match: {text_parts[0] + 's' == team_parts[0] and text_parts[1:] == team_parts[1:]}")
