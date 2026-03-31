"""
Image optimization: convert oversized PNGs/JPGs to WebP, fix favicon.

Run manually via: python agent.py --optimize-images
Not included in daily cron — one-time operation per image batch.
"""

import os
import re


def optimize_images(repo_root, threshold_kb=100):
    """
    Find images over threshold_kb and convert to WebP.
    Returns list of {original, optimized, saved_kb} dicts.

    Requires Pillow: pip install Pillow
    """
    from PIL import Image

    changes = []

    for f in os.listdir(repo_root):
        if not f.lower().endswith((".png", ".jpg", ".jpeg")):
            continue
        if f == "favicon.jpg":
            continue  # Handled separately

        filepath = os.path.join(repo_root, f)
        size_kb = os.path.getsize(filepath) / 1024

        if size_kb <= threshold_kb:
            continue

        webp_name = os.path.splitext(f)[0] + ".webp"
        webp_path = os.path.join(repo_root, webp_name)

        # Skip if WebP already exists
        if os.path.isfile(webp_path):
            continue

        img = Image.open(filepath)
        img.save(webp_path, "WEBP", quality=80)

        new_size_kb = os.path.getsize(webp_path) / 1024
        changes.append({
            "original": f,
            "optimized": webp_name,
            "original_kb": round(size_kb),
            "optimized_kb": round(new_size_kb),
            "saved_kb": round(size_kb - new_size_kb),
        })
        print(f"   ✓ {f} ({size_kb:.0f}KB) → {webp_name} ({new_size_kb:.0f}KB)")

    return changes


def fix_favicon(repo_root):
    """
    Create an optimized 32x32 favicon.png from the existing favicon.jpg.
    Returns the new filename or None.
    """
    from PIL import Image

    src = os.path.join(repo_root, "favicon.jpg")
    if not os.path.exists(src):
        return None

    img = Image.open(src)
    img = img.resize((32, 32), Image.LANCZOS)
    dst = os.path.join(repo_root, "favicon.png")
    img.save(dst, "PNG", optimize=True)

    old_kb = os.path.getsize(src) / 1024
    new_kb = os.path.getsize(dst) / 1024
    print(f"   ✓ favicon.jpg ({old_kb:.0f}KB) → favicon.png ({new_kb:.0f}KB)")
    return "favicon.png"


def update_html_references(repo_root, image_changes, new_favicon=None):
    """
    Update HTML files to reference new WebP images and favicon.
    Returns count of files modified.
    """
    modified = 0

    for f in os.listdir(repo_root):
        if not f.endswith(".html"):
            continue

        filepath = os.path.join(repo_root, f)
        with open(filepath, "r", encoding="utf-8") as fh:
            content = fh.read()

        original = content

        # Replace image references
        for change in image_changes:
            content = content.replace(change["original"], change["optimized"])

        # Replace favicon reference
        if new_favicon:
            content = content.replace('href="favicon.jpg"', f'href="{new_favicon}"')
            content = content.replace('type="image/jpeg"', 'type="image/png"')

        if content != original:
            with open(filepath, "w", encoding="utf-8") as fh:
                fh.write(content)
            modified += 1

    return modified


def run_full_optimization(repo_root):
    """Run all image optimizations and update HTML references."""
    print("\n🖼 Optimizing images...")

    changes = optimize_images(repo_root)
    print(f"   → {len(changes)} images converted to WebP")

    new_favicon = fix_favicon(repo_root)

    if changes or new_favicon:
        modified = update_html_references(repo_root, changes, new_favicon)
        print(f"   → {modified} HTML files updated with new references")

        total_saved = sum(c["saved_kb"] for c in changes)
        print(f"   → Total savings: {total_saved}KB")
    else:
        print("   → No images need optimization")

    return changes
