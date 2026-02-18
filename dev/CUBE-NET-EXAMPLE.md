# Cube Net Box Texture - Manual Testing Example

## Files in this folder:

- **box-cube-net-example.obj** - 3D box model with UV mapping for cube net layout
- **box-cube-net-template.png** - Template showing the layout (create manually)

## Cube Net Layout

The texture layout follows this pattern:

```
                 top (512x512)
    left (512) | front (512) | right (512) | back (512)
                 bottom (512x512)
```

**Total texture size**: 2048 x 1536 pixels

## UV Mapping in OBJ

The OBJ file maps each face of the box to these regions:

- **Front**: x=[0.25, 0.5], y=[0.333, 0.667] (512px square, middle row, 2nd column)
- **Back**: x=[0.75, 1.0], y=[0.333, 0.667] (512px square, middle row, 4th column)
- **Left**: x=[0.0, 0.25], y=[0.333, 0.667] (512px square, middle row, 1st column)
- **Right**: x=[0.5, 0.75], y=[0.333, 0.667] (512px square, middle row, 3rd column)
- **Top**: x=[0.25, 0.5], y=[0.667, 1.0] (512px square, top row, 2nd column)
- **Bottom**: x=[0.25, 0.5], y=[0.0, 0.333] (512px square, bottom row, 2nd column)

## How to Create a Test Texture

1. Create a 2048 x 1536 image (white background)
2. Place your artwork in the face regions:
   - **For wraparound art** (left-front-right from one image):
     - Use a wide image (1536x512) spanning columns 1-3
   - **For individual faces**:
     - Create separate 512x512 images per face
3. Save as PNG or JPG

## Testing in TTS

1. Upload `box-cube-net-example.obj` to your hosting
2. Upload your test texture
3. In TTS, set:
   - MeshURL: URL to the OBJ file
   - DiffuseURL: URL to your texture file
4. The box dimensions are 2cm x 5cm x 3.5cm (width x length x height)

## Notes

- White background fills areas not covered by faces
- You can use one continuous image for left+front+right sides
- Top can have team icon + name overlay
- Bottom can be generic background
