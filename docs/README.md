# Kill Team Datacards - Project Documentation

## Overview
This project extracts and processes Kill Team datacards from PDF exports into individual PNG images for use in Tabletop Simulator (TTS).

## Current Workflow
1. **Input**: PDF files placed in `input/` (named with GUIDs or any name)
2. **Processing**: Extract text to identify team and card type
3. **Organization**: Files moved to `input/{teamname}/` folders with proper naming
4. **Extraction**: Individual cards extracted as PNG images to `output/{teamname}/{cardtype}/`
5. **URL Generation**: CSV updated with GitHub URLs for TTS reference

## Planned Features

### Status Legend
- 🔴 Not Started
- 🟡 In Progress
- 🟢 Complete

### Feature List

| Feature | Status | Document | Priority |
|---------|--------|----------|----------|
| Poetry + Task Setup | � | [00-poetry-task-setup.md](00-poetry-task-setup.md) | **Critical** |
| Project Restructuring | 🟢 | [01-project-restructuring.md](01-project-restructuring.md) | High |
| Code Refactoring | 🟢 | [02-code-refactoring.md](02-code-refactoring.md) | High |
| Enhanced Metadata | 🟢 | [03-enhanced-metadata.md](03-enhanced-metadata.md) | Medium |
| Stats Extraction | 🔴 | [04-stats-extraction.md](04-stats-extraction.md) | Medium |
| Parameterized Execution | 🟢 | [05-parameterized-execution.md](05-parameterized-execution.md) | Low |
| Execution Enhancements | 🔴 | [06-execution-enhancements.md](06-execution-enhancements.md) | Low |

## Key Documents

- **[QUESTIONS.md](QUESTIONS.md)** - All questions answered! Ready to implement.
- **[DEVELOPMENT.md](DEVELOPMENT.md)** - Development rules, conventions, and guidelines.

## Recommended Implementation Order

1. **Feature 00**: Poetry + Task Setup (foundation for multi-machine workflow)
2. **Feature 01**: Project Restructuring (clean up folder structure)
3. **Feature 02**: Code Refactoring (improve code quality and maintainability)
4. **Feature 05**: Parameterized Execution (quick usability wins)
5. **Feature 03**: Enhanced Metadata (better tracking)
6. **Feature 04**: Stats Extraction (complex, can be deferred)

## Getting Started with Changes

Start with Feature 00 (Poetry + Task Setup) to establish a solid foundation for multi-machine development. Then proceed through the features in the recommended order above.
