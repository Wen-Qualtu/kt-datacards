# Step 1: PDF Scraping from Warhammer Community

## Purpose

Download Kill Team rules PDFs from the official Warhammer Community downloads page. Uses browser automation to handle JavaScript-rendered content and collapsible sections.

---

## Script

`pipelines/warcom/steps/1_scrape_warcom_killteam_downloads.py`

---

## Input

- **Source**: Warhammer Community downloads page
- **Default URL**: <https://www.warhammer-community.com/en-gb/downloads/kill-team/>

---

## Output

- **Directory**: `layers/warcom/staging/*.pdf`
- **Files**: Team rules PDFs (e.g., `Imperium_AngelsOfDeath_OnlineRules.pdf`)

---

## Execution Order

### 1. Launch Headless Browser

Uses Playwright (Chromium) to render JavaScript content.

**Why browser automation?**
- Warcom uses JavaScript to load collapsible sections
- PDF links are not in initial HTML source
- Need to expand sections to access all download links

### 2. Load Downloads Page

```python
await page.goto(url, wait_until='networkidle')
await page.wait_for_timeout(2000)  # Wait 2 seconds for initial load
```

**Waits:**
- `networkidle`: Ensures all network requests complete
- Additional 2s timeout: Allows JavaScript execution

### 3. Handle Cookie Banner

```python
await page.evaluate("document.getElementById('onetrust-consent-sdk')?.remove()")
```

**Why?**
- Cookie banner can overlap clickable elements
- Removed via DOM manipulation (no user interaction)

### 4. Extract PDF Links from DOM

**Initial extraction:**
```python
pdf_links = await page.locator('a[href*=".pdf"]').all()
```

Finds all `<a>` tags with `.pdf` in href attribute.

**URL normalization:**
- Absolute URLs (`http://...`): Use as-is
- Root-relative (`/downloads/...`): Prepend `https://www.warhammer-community.com`
- Relative (`assets/...`): Prepend `https://assets.warhammer-community.com`

### 5. Expand Team Rules Section

**Selector priority:**

Tries multiple selectors to find the "Team Rules" section:

```python
selectors_to_try = [
    'h2:has-text("Team Rules")',
    'h3:has-text("Team Rules")',
    'button:has-text("Team Rules")',
    'summary:has-text("Team Rules")',
    '[aria-label*="Team Rules"]'
]
```

**Expansion logic:**
- Check `aria-expanded` attribute
- If `false`, click to expand
- Wait 2 seconds for content to load

**Container detection:**
- Navigate up DOM tree to find parent section
- Look for `<section>`, `<div class="accordion">`, or `<details>` tags
- Extract all PDF links within container

### 6. Filter Team Rules PDFs

**Inclusion criteria:**
- Filename contains `team_rules`, `teamrules`, or `_online_rules`

**Exclusion criteria:**
- Contains `key_download` (core rules index)
- Contains `mission_pack` (not team-specific)
- Contains `ctesiphus_expedition` (campaign supplement)
- Contains `core_rules` (general rules)

**Example filenames:**
- ✅ `Imperium_AngelsOfDeath_OnlineRules.pdf`
- ✅ `Chaos_Legionaries_TeamRules.pdf`
- ❌ `KillTeam_Core_Rules.pdf`
- ❌ `Mission_Pack_Season_1.pdf`

### 7. Deduplicate URLs

```python
pdf_urls = list(dict.fromkeys(pdf_urls))  # Preserves order
```

Same PDF can appear multiple times in DOM (different links to same file).

### 8. Download PDFs

**For each PDF:**

1. **Check if exists**:
   - If `output_dir/{filename}` exists → skip
   - Prevents re-downloading on reruns

2. **Download with streaming**:
   ```python
   response = requests.get(url, headers=headers, stream=True)
   for chunk in response.iter_content(chunk_size=8192):
       f.write(chunk)
   ```

3. **Log file size**:
   - Display size in MB for verification
   - Typical team PDF: 2-5 MB

4. **Delay between downloads**:
   - Default: 1 second
   - Be respectful of server resources

**User-Agent header:**
```python
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}
```

Identifies as a standard browser (some servers block default Python user-agent).

---

## Output Structure

```
layers/warcom/staging/
├── Chaos_Legionaries_OnlineRules.pdf
├── Imperium_AngelsOfDeath_OnlineRules.pdf
├── Imperium_Kasrkin_TeamRules.pdf
├── Xenos_Kommandos_TeamRules.pdf
└── ...
```

**Filename format:**
- From warcom: `{Faction}_{TeamName}_{Type}.pdf`
- Not normalized (exact names from website)

---

## Command Line Options

```bash
# Default (all options)
python pipelines/warcom/steps/1_scrape_warcom_killteam_downloads.py

# Custom output directory
python ... --output layers/my-pdfs

# Custom URL
python ... --url https://www.warhammer-community.com/...

# Longer delay between downloads
python ... --delay 2.0
```

---

## Success Criteria

**Returns:**
```python
{
    'success': True,  # False if any downloads failed
    'downloaded': 12,
    'skipped': 34,   # Already existed
    'failed': 0
}
```

**Exit code:**
- `0`: Success (all downloads completed or skipped)
- `1`: Failure (one or more downloads failed)

---

## Error Handling

### Browser Launch Failure

**Symptom:**
```
Error extracting PDF URLs: ...
```

**Causes:**
- Playwright not installed: `poetry run playwright install chromium`
- Chromium binary missing
- Insufficient permissions

### No PDFs Found

**Symptom:**
```
No team PDFs found!
```

**Causes:**
- Page structure changed (update selectors)
- Network timeout (try higher wait times)
- URL incorrect

### Download Failures

**Symptom:**
```
x Error: HTTPError 404
```

**Causes:**
- PDF removed from server
- Temporary server issue
- Network connectivity problem

**Recovery:**
- Rerun script (skips successful downloads)
- Check URL in browser manually

---

## Design Decisions

### Why Playwright Instead of Requests/BeautifulSoup?

**Problem:** Warcom uses JavaScript to render collapsible sections.

**Alternative approaches:**
1. Parse static HTML → Won't find PDFs in collapsed sections
2. Manually expand sections via API → No public API available
3. Use browser automation → ✅ Reliable, mimics user behavior

### Why Stream Downloads?

**Problem:** Team PDFs can be 2-5 MB each.

**Solution:** Stream in 8 KB chunks instead of loading entire file into memory.

**Benefits:**
- Lower memory usage
- Can show progress for large files
- Handles network interruptions better

### Why 1 Second Delay?

**Problem:** Rapid automated requests can:
- Trigger rate limiting
- Look like a DoS attack
- Violate server ToS

**Solution:** 1 second delay = 60 PDFs/minute (respectful, reliable).

---

## Maintenance

### If Page Structure Changes

**Check these selectors:**
1. PDF link selector: `a[href*=".pdf"]`
2. Team Rules section: `h2:has-text("Team Rules")`
3. Container parent: `section`, `div.accordion`, `details`

**To debug:**
- Set `headless=False` in browser launch
- Add screenshot: `await page.screenshot(path='debug.png')`
- Inspect DOM structure manually

### If Filename Patterns Change

**Update filters in Step 6:**
```python
if ('team_rules' in filename or 'new_pattern' in filename) and \
   'exclude_this' not in filename:
```

---

## Dependencies

| Package | Purpose | Installation |
|---------|---------|--------------|
| `playwright` | Browser automation | `poetry add playwright` |
| | | `poetry run playwright install chromium` |
| `requests` | HTTP downloads | `poetry add requests` |

---

## Performance

**Typical runtime:**
- Page load + scraping: ~5-10 seconds
- Downloads (46 teams, all new): ~2-3 minutes
- Downloads (all existing): ~5 seconds

**Bottleneck:** Network speed (downloads are sequential with 1s delay)

---

**Last Updated**: February 16, 2026
