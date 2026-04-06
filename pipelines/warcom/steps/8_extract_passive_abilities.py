#!/usr/bin/env python3
"""
Step 8: Extract Passive Abilities from KT-App Datacards

Extracts passive abilities from the kt-app processed datacards PDF.
These are abilities shown on the back-side of operative cards.

Input:  layers/kt-app/processed/{team}/{team}-datacards.pdf  
Output: Updates output/{team}/statlines/roster.json with passive_abilities

Architecture:
- KT-app datacards PDF has front and back pages
- Even pages (front): Operative name, stats, weapons
- Odd pages (back): Passive abilities (colon format)
-Pattern: "Ability Name: Description text..."
