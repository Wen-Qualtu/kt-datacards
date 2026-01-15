"""
Analyze extracted tokens and categorize them by shape.

For Kill Team tokens, there are typically two shapes:
1. Round/circular tokens (like condition markers)
2. Complex shaped tokens (like faction abilities - pentagon/hexagon shaped)

This script analyzes the extracted token images and groups them by approximate shape.
"""

import argparse
from pathlib import Path
import cv2
import numpy as np
from typing import Dict, List, Tuple
import json


class TokenShapeAnalyzer:
    """Analyze token shapes to categorize them."""
    
    def __init__(self):
        # Shape categories based on circularity
        # Circularity = 4π × area / perimeter²
        # Circle = 1.0, Square ≈ 0.785, Operative shapes < 0.7
        self.ROUND_THRESHOLD = 0.75  # Higher = more circular
        self.OPERATIVE_THRESHOLD = 0.75  # Lower = more operative shape
    
    def analyze_token(self, image_path: Path) -> Dict:
        """
        Analyze a single token image to determine its shape.
        
        Returns:
            Dict with 'shape', 'circularity', 'area', 'perimeter', 'bbox'
        """
        img = cv2.imread(str(image_path))
        if img is None:
            return None
        
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Threshold to get token shape
        _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
        
        # Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return None
        
        # Get the largest contour (should be the token)
        main_contour = max(contours, key=cv2.contourArea)
        
        # Calculate shape metrics
        area = cv2.contourArea(main_contour)
        perimeter = cv2.arcLength(main_contour, True)
        
        # Circularity: 4π × area / perimeter²
        # Perfect circle = 1.0
        if perimeter > 0:
            circularity = (4 * np.pi * area) / (perimeter ** 2)
        else:
            circularity = 0
        
        # Bounding box
        x, y, w, h = cv2.boundingRect(main_contour)
        
        # Aspect ratio
        aspect_ratio = w / h if h > 0 else 0
        
        # Determine shape category
        if circularity >= self.ROUND_THRESHOLD and 0.9 <= aspect_ratio <= 1.1:
            shape_category = "round"
        else:
            shape_category = "operative"
        
        return {
            'shape': shape_category,
            'circularity': round(circularity, 3),
            'area': int(area),
            'perimeter': round(perimeter, 1),
            'bbox': {'x': int(x), 'y': int(y), 'width': int(w), 'height': int(h)},
            'aspect_ratio': round(aspect_ratio, 3),
            'dimensions': {'width': w, 'height': h}
        }
    
    def analyze_team_tokens(self, team_dir: Path) -> Dict:
        """
        Analyze all tokens for a team and group by shape.
        
        Returns:
            Dict with 'round' and 'complex' token lists
        """
        results = {
            'team': team_dir.name,
            'tokens': {
                'round': [],
                'operative': []
            },
            'summary': {
                'total': 0,
                'round_count': 0,
                'operative_count': 0
            }
        }
        
        # Find all token PNG files (excluding debug image)
        token_files = sorted([f for f in team_dir.glob('token-*.png')])
        
        for token_file in token_files:
            analysis = self.analyze_token(token_file)
            if analysis:
                token_info = {
                    'filename': token_file.name,
                    'analysis': analysis
                }
                
                # Categorize
                shape = analysis['shape']
                results['tokens'][shape].append(token_info)
                results['summary'][f'{shape}_count'] += 1
                results['summary']['total'] += 1
                
                print(f"  {token_file.name}: {shape} (circularity={analysis['circularity']}, " 
                      f"{analysis['dimensions']['width']}x{analysis['dimensions']['height']}px)")
        
        return results


def main():
    parser = argparse.ArgumentParser(description='Analyze extracted token shapes')
    parser.add_argument('--team', type=str, help='Team name (e.g., farstalker-kinband)')
    parser.add_argument('--all', action='store_true', help='Analyze all extracted teams')
    parser.add_argument('--input-dir', type=str, default='dev/extracted-tokens',
                       help='Input directory with extracted tokens')
    parser.add_argument('--output', type=str, default='dev/token-shape-analysis.json',
                       help='Output JSON file with analysis results')
    
    args = parser.parse_args()
    
    if not args.team and not args.all:
        parser.error('Must specify --team or --all')
    
    analyzer = TokenShapeAnalyzer()
    all_results = []
    
    input_dir = Path(args.input_dir)
    
    if args.team:
        # Analyze single team
        team_dir = input_dir / args.team
        if not team_dir.exists():
            print(f"✗ Team directory not found: {team_dir}")
            exit(1)
        
        print(f"\nAnalyzing: {args.team}")
        print("=" * 60)
        results = analyzer.analyze_team_tokens(team_dir)
        all_results.append(results)
        
        # Print summary
        print(f"\nSummary:")
        print(f"  Total tokens: {results['summary']['total']}")
        print(f"  Round tokens: {results['summary']['round_count']}")
        print(f"  Complex tokens: {results['summary']['complex_count']}")
    
    elif args.all:
        # Analyze all teams
        team_dirs = [d for d in input_dir.iterdir() if d.is_dir()]
        
        for team_dir in sorted(team_dirs):
            print(f"\nAnalyzing: {team_dir.name}")
            print("=" * 60)
            results = analyzer.analyze_team_tokens(team_dir)
            all_results.append(results)
            
            # Print summary
            print(f"  Round: {results['summary']['round_count']}, " 
                  f"Operative: {results['summary']['operative_count']}")
    
    # Save results to JSON
    output_path = Path(args.output)
    output_path.parent.mkdir(exist_ok=True, parents=True)
    
    with open(output_path, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\n✓ Analysis complete!")
    print(f"  Results saved: {output_path.absolute()}")
    
    # Print overall summary
    if args.all:
        total_tokens = sum(r['summary']['total'] for r in all_results)
        total_round = sum(r['summary']['round_count'] for r in all_results)
        total_operative = sum(r['summary']['operative_count'] for r in all_results)
        
        print(f"\nOverall Summary:")
        print(f"  Teams analyzed: {len(all_results)}")
        print(f"  Total tokens: {total_tokens}")
        print(f"  Round tokens: {total_round}")
        print(f"  Operative tokens: {total_operative}")


if __name__ == '__main__':
    main()
