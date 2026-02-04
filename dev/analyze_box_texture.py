"""
Analyze box texture images to understand layout for script generation.
"""
import cv2
import numpy as np
from pathlib import Path

# Load images
box_example = cv2.imread('config/teams/angels-of-death/box/card-box-texture - Copy.jpg')
box_template = cv2.imread('dev/examples/box-side.png')
landscape_icon = cv2.imread('layers/warcom/extracted/angels-of-death/icons/angels-of-death-icon-landscape.jpg')
portrait_icon = cv2.imread('layers/warcom/extracted/angels-of-death/icons/angels-of-death-icon-portrait.jpg')

print("=== Image Dimensions ===")
print(f"Box example:     {box_example.shape[1]}x{box_example.shape[0]}")
print(f"Box template:    {box_template.shape[1]}x{box_template.shape[0]}")
print(f"Landscape icon:  {landscape_icon.shape[1]}x{landscape_icon.shape[0]}")
print(f"Portrait icon:   {portrait_icon.shape[1]}x{portrait_icon.shape[0]}")

# Save template for inspection
cv2.imwrite('dev/box_template_check.jpg', box_template)
print("\nSaved template to dev/box_template_check.jpg")
