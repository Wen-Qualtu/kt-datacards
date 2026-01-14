import os
from pathlib import Path
import base64

backside_dir = Path("downloaded_backsides")
unidentified_files = []

# Find all unidentified files (those starting with dash)
for filename in sorted(os.listdir(backside_dir)):
    if filename.startswith('-backside-') and filename.endswith('.jpg'):
        unidentified_files.append(filename)

print(f"Found {len(unidentified_files)} unidentified backside images")
print("Creating visual review HTML...")

# Create HTML file
html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Identify Card Backsides</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background: #f0f0f0;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
            padding: 20px;
        }}
        .card {{
            background: white;
            border: 2px solid #ccc;
            border-radius: 8px;
            padding: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .card img {{
            width: 100%;
            height: auto;
            border-radius: 4px;
        }}
        .card .filename {{
            font-size: 10px;
            color: #666;
            margin-top: 8px;
            word-break: break-all;
        }}
        .card .label {{
            font-weight: bold;
            margin-top: 8px;
            color: #333;
        }}
        h1 {{
            text-align: center;
            color: #333;
        }}
        .instructions {{
            background: #fff;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            border-left: 4px solid #4CAF50;
        }}
    </style>
</head>
<body>
    <h1>Card Backside Identification</h1>
    <div class="instructions">
        <h2>Instructions:</h2>
        <p>Review each card backside image below. Look for team names or identifying text on the cards.</p>
        <p><strong>Note the filename</strong> of any card you can identify, and we'll rename them in a batch.</p>
        <p>Total unidentified: <strong>{len(unidentified_files)}</strong></p>
    </div>
    <div class="grid">
"""

for filename in unidentified_files:
    filepath = backside_dir / filename
    
    # Read and encode image as base64
    with open(filepath, 'rb') as f:
        img_data = base64.b64encode(f.read()).decode('utf-8')
    
    html_content += f"""
        <div class="card">
            <img src="data:image/jpeg;base64,{img_data}" alt="{filename}">
            <div class="filename">{filename}</div>
        </div>
    """

html_content += """
    </div>
</body>
</html>
"""

# Save HTML file
output_file = "backside_review.html"
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(html_content)

print(f"✅ Created {output_file}")
print(f"\nOpen this file in your browser to review all {len(unidentified_files)} images at once.")
print("\nAfter reviewing, you can tell me which files correspond to which teams,")
print("and I'll create a batch rename script for you.")
