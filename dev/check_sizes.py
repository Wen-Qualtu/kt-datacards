from PIL import Image
from pathlib import Path

tokens = ['meat', 'victory-shriek', 'pechra', 'trophy', 'quick-draw']
team_dir = Path('dev/extracted-tokens/farstalker-kinband')

print('\nToken sizes after cropping and transparency:')
print('='*60)
for token in tokens:
    token_path = team_dir / f'{token}.png'
    if token_path.exists():
        img = Image.open(token_path)
        print(f'  {token:25}: {img.size[0]:4}x{img.size[1]:4} pixels  (Mode: {img.mode})')
    else:
        print(f'  {token:25}: NOT FOUND')
