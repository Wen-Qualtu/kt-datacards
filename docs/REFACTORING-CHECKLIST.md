# Refactoring Checklist

Quick reference for implementing the refactoring plan.

---

## 🔴 Phase 1: Critical Fixes (Day 1)

### ☐ Task 1.1: Create config.py
- [ ] Create `script/config.py` with all paths and constants
- [ ] Update `run_pipeline.py` to use config
- [ ] Update `pipeline/pipeline.py` to use config
- [ ] Update `managers.py` to use config
- [ ] Update all generators to use config
- [ ] Test: Run pipeline on test team
- [ ] Commit: "Add central config.py for paths and constants"

### ☐ Task 1.2: Fix Logging
- [ ] Replace print() in `image_extractor.py` with self.logger.debug()
- [ ] Replace print() in `generators/objects/urls.py` with self.logger.debug()
- [ ] Search for remaining print() statements in script/
- [ ] Test: Run with --verbose, verify debug output
- [ ] Test: Run without --verbose, verify clean output
- [ ] Commit: "Replace print statements with proper logging"

### ☐ Task 1.3: Consolidate URL Generation
- [ ] Move `generators/objects/urls.py` → `generators/urls.py`
- [ ] Update URLGenerator to use config paths
- [ ] Simplify `generators/metadata/urls.py` to wrapper
- [ ] Delete or refactor `pipeline/v2_output_processor.py`
- [ ] Update `pipeline/pipeline.py` imports
- [ ] Test: Generate URLs via pipeline
- [ ] Test: Generate URLs via CLI
- [ ] Compare outputs - must be identical
- [ ] Commit: "Consolidate URL generation into single implementation"

### ☐ Task 1.4: Rename cardboxes.py
- [ ] Rename `generators/objects/cardboxes.py` → `tts_objects.py`
- [ ] Update imports in `pipeline/pipeline.py`
- [ ] Update imports in `generators/generate.py`
- [ ] Update imports in `generators/objects/generate.py`
- [ ] Search codebase for remaining references
- [ ] Test: Generate TTS objects
- [ ] Commit: "Rename cardboxes.py to tts_objects.py for clarity"

---

## 🟡 Phase 2: Structure (Day 2)

### ☐ Task 2.1: Consolidate CLIs
- [ ] Delete `pipeline/process_pdfs_cli.py`
- [ ] Delete `pipeline/extract_images_cli.py`
- [ ] Decide: Keep one or both generate.py CLIs
- [ ] Update README with correct CLI commands
- [ ] Test: All pipeline steps work via run_pipeline.py
- [ ] Test: All generation tasks work
- [ ] Commit: "Remove redundant CLI scripts"

### ☐ Task 2.2: Organize Generators
- [ ] Move key files up from objects/ and metadata/
- [ ] Create `generators/helpers/` directory
- [ ] Move GUID helpers to `helpers/guid.py`
- [ ] Update all imports
- [ ] Test: All generation tasks
- [ ] Commit: "Reorganize generators directory structure"

---

## 🟢 Phase 3: Code Quality (Day 3)

### ☐ Task 3.1: Break Up Long Functions
- [ ] Refactor `ImageExtractor._analyze_pages()`
- [ ] Create helper methods for page analysis
- [ ] Create AnalysisContext class if needed
- [ ] Add docstrings to new methods
- [ ] Test: Extract images from various PDFs
- [ ] Commit: "Refactor _analyze_pages into smaller functions"

### ☐ Task 3.2: Improve Error Handling
- [ ] Define custom exceptions in models.py
- [ ] Update pipeline error handling
- [ ] Update generator error handling
- [ ] Add specific exception types
- [ ] Test with corrupt PDFs and missing files
- [ ] Commit: "Improve error handling with specific exceptions"

### ☐ Task 3.3: Add Docstrings
- [ ] Add docstrings to all public methods in models.py
- [ ] Add docstrings to pipeline public methods
- [ ] Add docstrings to generator public functions
- [ ] Add docstrings to utils.py
- [ ] Run pydocstyle to check coverage
- [ ] Commit: "Add comprehensive docstrings"

---

## 🟢 Phase 4: Documentation (Day 4)

### ☐ Task 4.1: Update DEVELOPMENT.md
- [ ] Remove confusing cls/card_type_class rule
- [ ] Add import guidelines section
- [ ] Document actual project structure
- [ ] Update with config.py information
- [ ] Review and fix any other outdated info
- [ ] Commit: "Update DEVELOPMENT.md to reflect current codebase"

### ☐ Task 4.2: Create ARCHITECTURE.md
- [ ] Create docs/ARCHITECTURE.md
- [ ] Add data flow diagram
- [ ] Document core components
- [ ] Explain design decisions
- [ ] Add component responsibilities
- [ ] Commit: "Add ARCHITECTURE.md documentation"

### ☐ Task 4.3: Add Test Suite
- [ ] Create tests/ directory structure
- [ ] Write test_models.py
- [ ] Write test_team_identifier.py
- [ ] Create test fixtures
- [ ] Run tests and verify passing
- [ ] Commit: "Add initial test suite"

---

## Testing Checklist (After Each Phase)

### Quick Smoke Test
```bash
# Process one team through full pipeline
python script/run_pipeline.py --step all --teams kasrkin

# Check outputs exist
ls output_v2/imperium/kasrkin/
ls tts_objects/

# Verify URLs
head output_v2/datacards-urls.json
```

### Full Test
```bash
# Run on multiple teams
python script/run_pipeline.py --step all --teams kasrkin blooded pathfinders

# Check TTS objects
ls tts_objects/*.json

# Verify metadata
cat output_v2/tts-metadata.json
```

### Regression Test
```bash
# Before making changes
python script/run_pipeline.py --step all --teams kasrkin > before.log 2>&1
ls -R output_v2/imperium/kasrkin/ > before_files.txt

# After making changes  
python script/run_pipeline.py --step all --teams kasrkin > after.log 2>&1
ls -R output_v2/imperium/kasrkin/ > after_files.txt

# Compare
diff before_files.txt after_files.txt  # Should be identical (or minor diffs)
```

---

## Git Workflow

### Before Starting
```bash
# Create feature branch
git checkout -b refactor/phase-1-critical-fixes

# Ensure clean state
git status
```

### After Each Task
```bash
# Stage changes
git add script/config.py
git add script/run_pipeline.py
# etc.

# Commit with clear message
git commit -m "Add config.py: Centralize paths and constants

- Created script/config.py with all directory paths
- Updated run_pipeline.py to use config
- Updated pipeline.py to use config
- Tested on kasrkin team - all outputs correct"

# Push regularly
git push origin refactor/phase-1-critical-fixes
```

### Phase Complete
```bash
# Tag the completion
git tag refactor-phase-1-complete
git push --tags

# Merge to main (if using branches)
git checkout main
git merge refactor/phase-1-critical-fixes
git push
```

---

## Common Issues & Solutions

### Issue: Import Errors After Moving Files
**Solution:** Search entire codebase for old imports
```bash
grep -r "from generators.objects.cardboxes" script/
# Update each found file
```

### Issue: Paths Not Resolving
**Solution:** Check config.py is being imported
```python
# Add debug print temporarily
print(f"Using OUTPUT_V2_DIR: {OUTPUT_V2_DIR}")
```

### Issue: Tests Failing After Refactor
**Solution:** Update test fixtures and mocks
- Check if paths changed
- Update fixture paths in tests
- Verify test expectations match new behavior

### Issue: TTS Objects Not Generated
**Solution:** 
1. Check URLs in datacards-urls.json are correct
2. Verify team config has all required fields
3. Check tts_objects directory permissions
4. Review logs for errors

---

## Quality Checks

### Before Committing
- [ ] Code formatted with Black: `black script/`
- [ ] Imports sorted: `isort script/`
- [ ] No syntax errors: `python -m py_compile script/**/*.py`
- [ ] Tests pass: `pytest script/tests/`
- [ ] Pipeline runs successfully on test data

### Before Merging Phase
- [ ] All tasks in phase completed
- [ ] All tests passing
- [ ] Documentation updated
- [ ] No print() statements (except generated code)
- [ ] No hardcoded paths
- [ ] Git history is clean and clear

---

## Progress Tracking

### Overall Progress
- [ ] Phase 1: Critical Fixes (4 tasks)
- [ ] Phase 2: Structure (2 tasks)
- [ ] Phase 3: Code Quality (3 tasks)
- [ ] Phase 4: Documentation (3 tasks)

### Completion Metrics
- **Files Refactored:** __ / 32 total Python files
- **Print Statements Removed:** __ / ~15
- **Functions Refactored:** __ / ~5 long functions
- **Test Coverage:** __%
- **Documentation Coverage:** __%

---

## Daily Standup Template

### What I Did Yesterday
- Completed: [task name]
- Made progress on: [task name]
- Committed: [number] commits

### What I'm Doing Today
- Focus: [task name]
- Goal: Complete Phase [number]

### Blockers
- None / [describe blocker]

---

## Rollback Commands (If Needed)

### Undo Last Commit (Keep Changes)
```bash
git reset --soft HEAD~1
```

### Undo Last Commit (Discard Changes)
```bash
git reset --hard HEAD~1
```

### Return to Tag
```bash
git reset --hard refactor-phase-1-complete
```

### Create Backup Before Major Change
```bash
# Create archive
tar -czf backup-before-phase2.tar.gz .

# Or just copy
cp -r ../kt-datacards ../kt-datacards-backup
```

---

## Success Indicators

### You'll Know Phase 1 is Complete When:
✅ No hardcoded paths in any file  
✅ All print() replaced with logging  
✅ Single URL generation implementation  
✅ All files properly named  
✅ Pipeline runs without errors  

### You'll Know Entire Refactor is Complete When:
✅ All phases checked off  
✅ Test coverage > 50%  
✅ Documentation up to date  
✅ Code passes linting  
✅ Can onboard new dev in < 1 hour  
✅ Can add new team in < 10 minutes  

---

**Last Updated:** January 25, 2026  
**Next Review:** After Phase 1 completion
