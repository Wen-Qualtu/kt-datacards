from PIL import Image
import numpy as np
import sys

token_name = sys.argv[1] if len(sys.argv) > 1 else 'meat'
img_path = f'dev/extracted-tokens/farstalker-kinband/{token_name}.png'

img = Image.open(img_path)
data = np.array(img)

print(f'\n{token_name.upper()} token analysis:')
print(f'  Mode: {img.mode}')
print(f'  Size: {img.size}')
print(f'  RGB range: {data[:,:,0:3].min()}-{data[:,:,0:3].max()}')
print(f'\n  Corner colors:')

h, w = data.shape[:2]
corners = {
    'Top-Left': (0, 0),
    'Top-Right': (0, w-1),
    'Bottom-Left': (h-1, 0),
    'Bottom-Right': (h-1, w-1)
}

for name, (y, x) in corners.items():
    rgb = tuple(data[y, x, 0:3])
    print(f'    {name:15}: RGB{rgb}')

# Check average corner color
corner_vals = [data[y, x, 0:3] for y, x in corners.values()]
avg_corner = np.mean(corner_vals, axis=0)
print(f'\n  Average corner: RGB({avg_corner[0]:.1f}, {avg_corner[1]:.1f}, {avg_corner[2]:.1f})')

# Check alpha channel
if img.mode == 'RGBA':
    print(f'\n  Alpha channel:')
    print(f'    Transparent: {np.sum(data[:,:,3] == 0)}')
    print(f'    Semi-trans:  {np.sum((data[:,:,3] > 0) & (data[:,:,3] < 255))}')
    print(f'    Opaque:      {np.sum(data[:,:,3] == 255)}')
