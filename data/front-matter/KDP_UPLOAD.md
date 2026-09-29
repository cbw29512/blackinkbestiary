# KDP setup for Tome I

This is the print spec. Do not change it mid-book.

## Interior

- Trim: 8.5 x 11 in
- Bleed: No bleed
- Interior: Black and white
- Paper: White
- Art files: 2550 x 3300 px, 300 DPI, grayscale PNG
- Safety margin: 0.375 in on every side (112 px at 300 DPI)
- Flux generate size: 1760 x 2272, then convert to the print PNG

No bleed is correct because the art sits inside the white margin. If we later run art to the cut edge, the PDF must become 8.75 x 11.25 and KDP must be set to Bleed.

## Book structure

Single-sided coloring pages. Marker users bleed through KDP paper.

1. Title page
2. Table of contents
3. I-01 through I-50, each followed by a blank back
4. License / attribution page

That is about 104 printed pages. Gutter stays 0.375 in.

## Cover

Separate full wrap. Not a coloring page. Do not draw it with DRAW_PAGE.ps1.

## Listing

- Price band: $9.99 to $12.99
- Categories: adult / teen fantasy coloring
- Declare AI-assisted interior when KDP asks
- Order a printed proof before going live

## What "perfect" means here

Flux cannot emit a native 2550 x 3300 file. 8.4 MP is over the 4 MP cap. We generate at the largest legal portrait, then scale line art 1.3x. Bold outlines survive that. Hairline art would not.
