# Tryna crack?

## Category 
Forensics

## Description
Easy peasy

## Challenge Content
A single encrypted ZIP file containing a PNG called `quackquackquack.png`

## Analyzing the File

![Analyze](img/analyze.png)

The ZIP file is encrypted but not deflated, making it vulnerable to a known plaintext attack.

## Extracting the PNG

Reference: https://wiki.anter.dev/misc/plaintext-attack-zipcrypto/#executing-the-plaintext-attack

Using `bkcrack` with knowledge of the PNG header and footer structure:

![PNG Header](img/png_header.png)

![Extracting the PNG](img/extracting_the_png.png)
![Flag](img/flag.png)

## Analyzing the PNG

![Analyze PNG](img/analyze_png.png)

The user comment field contains what appears to be a password:

`D4mn_br0_H0n3y_p07_7yp3_5h1d`

Wrapping it as `v1t{D4mn_br0_H0n3y_p07_7yp3_5h1d}` yields an incorrect flag.

One of the organizers mentioned "breaking the limits" - suggesting we should check for out-of-bounds data.

## Finding Hidden Data

Using a Python script to check for false width/height values in the PNG:

![Fix PNG](img/fix_png.png)

Morse code appears at the bottom of the corrected image, which decodes to: **SHA512**

## Solution

The flag is the SHA512 hash of the password:
```
v1t{7083748baa3a42dc0a93811e4f5150e7ae1a050a0929f8c304f707c8c44fc95d86c476d11c9e56709edc30eba5f2d82396f426d93870b56b1a9573eaac8d0373}
```