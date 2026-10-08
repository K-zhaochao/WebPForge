# Third-party assets

The website self-hosts its photographs and fonts. No runtime requests to a font,
image, analytics, or conversion service are required.

## Photography

Sample photographs are provided under the [Unsplash License](https://unsplash.com/license).
They are cropped/resized for the comparison and compressed with Pillow for the
static examples. `samples.json` records original download URLs and measured sizes.

- Alpine: https://images.unsplash.com/photo-1464822759023-fed622ff2c3b
- Ocean: https://images.unsplash.com/photo-1518837695005-2083093ee35b
- Forest: https://images.unsplash.com/photo-1441974231531-c6227db76b6e

The browser comparison generates its own WebP result, whose size can differ from
the static Pillow example because the encoders and settings differ.

## Fonts

- Manrope, by Mikhail Sharanda and the Manrope Project Authors. SIL Open Font License 1.1; see `manrope-OFL.txt`.
- Noto Sans SC, by the Noto Project Authors. SIL Open Font License 1.1; see `notosanssc-OFL.txt`. Only the heading characters are included in the webfont subset.

Font sources: https://github.com/google/fonts/tree/main/ofl/manrope and
https://github.com/google/fonts/tree/main/ofl/notosanssc.

## Icons

The favicon is the existing WebPForge application icon. The GitHub mark represents
the project's GitHub repository. Windows and macOS labels identify the supported
platforms; they do not imply endorsement by their owners. Other interface icons
are simple inline SVG geometry authored for this website.
