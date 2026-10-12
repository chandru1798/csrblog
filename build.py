from pathlib import Path
import re
import shutil


# =========================================================
# PATHS
# =========================================================

ROOT = Path(__file__).parent

COMPONENTS = ROOT / "components"

HEAD_FILE = COMPONENTS / "head.html"
HEADER_FILE = COMPONENTS / "header.html"
FOOTER_FILE = COMPONENTS / "footer.html"

BUILD_DIR = ROOT / "build"


# =========================================================
# GET RELATIVE PATH PREFIX
# =========================================================

def get_prefix(page):
    """
    Calculate the correct relative path for assets.

    Root page:
        index.html
        -> ""

    Subfolder page:
        blog/page.html
        -> "../"

    Deeper page:
        blog/category/page.html
        -> "../../"
    """

    relative = page.relative_to(ROOT)
    depth = len(relative.parts) - 1

    return "../" * depth


# =========================================================
# PREPARE COMPONENT PATHS
# =========================================================

def prepare_component(content, prefix):
    """
    Adjust paths inside common components when the page
    is located inside a subfolder.
    """

    if not prefix:
        return content

    # -----------------------------------------------------
    # Images
    # -----------------------------------------------------

    content = re.sub(
        r'(?<=["\(])img/',
        prefix + "img/",
        content
    )

    # -----------------------------------------------------
    # CSS
    # -----------------------------------------------------

    content = re.sub(
        r'(?<=["\(])css/',
        prefix + "css/",
        content
    )

    # -----------------------------------------------------
    # JavaScript
    # -----------------------------------------------------

    content = re.sub(
        r'(?<=["\(])js/',
        prefix + "js/",
        content
    )

    # -----------------------------------------------------
    # PHPMailer
    # -----------------------------------------------------

    content = re.sub(
        r'(?<=["\(])phpmailer/',
        prefix + "phpmailer/",
        content
    )

    # -----------------------------------------------------
    # HTML links
    # -----------------------------------------------------

    content = re.sub(
        r'(?<=")(?!https?://|#|/|\.\./)([A-Za-z0-9_-]+\.html)',
        prefix + r"\1",
        content
    )

    return content


# =========================================================
# REPLACE HEAD
# =========================================================

def extract_page_seo(html):
    """
    Extract page-specific SEO elements that must remain
    unique for each page.

    Keeps:
      - <title>
      - meta description
      - meta keywords

    Also keeps page-specific JSON-LD schema blocks.
    """

    seo_parts = []

    # -----------------------------------------------------
    # Title
    # -----------------------------------------------------

    title_match = re.search(
        r'<title\b[^>]*>.*?</title>',
        html,
        flags=re.DOTALL | re.IGNORECASE
    )

    if title_match:
        seo_parts.append(title_match.group(0).strip())

    # -----------------------------------------------------
    # Meta description
    # -----------------------------------------------------

    description_match = re.search(
        r'<meta\b[^>]*name\s*=\s*["\']description["\'][^>]*>',
        html,
        flags=re.IGNORECASE
    )

    if description_match:
        seo_parts.append(description_match.group(0).strip())

    # -----------------------------------------------------
    # Meta keywords
    # -----------------------------------------------------

    keywords_match = re.search(
        r'<meta\b[^>]*name\s*=\s*["\']keywords["\'][^>]*>',
        html,
        flags=re.IGNORECASE
    )

    if keywords_match:
        seo_parts.append(keywords_match.group(0).strip())

    # -----------------------------------------------------
    # Page-specific JSON-LD schema
    # -----------------------------------------------------

    schema_matches = re.findall(
        r'<script\b[^>]*type\s*=\s*["\']application/ld\+json["\'][^>]*>.*?</script>',
        html,
        flags=re.DOTALL | re.IGNORECASE
    )

    for schema in schema_matches:
        schema = schema.strip()
        if schema not in seo_parts:
            seo_parts.append(schema)

    if not seo_parts:
        return ""

    return "\n\n    ".join(seo_parts)


def replace_head(html, head):
    """
    Replace the page head.

    CASE 1:
        If <!-- COMMON_HEAD --> exists inside <head>,
        replace that placeholder with components/head.html.

    CASE 2:
        If the old full <head> exists, replace the common
        head code while preserving:
          - title
          - meta description
          - meta keywords
          - JSON-LD schema

        This allows old pages to be migrated gradually.

    Returns:
        html, found, type
    """

    # -----------------------------------------------------
    # CASE 1 - COMMON_HEAD placeholder
    # -----------------------------------------------------

    if "<!-- COMMON_HEAD -->" in html:

        html = html.replace(
            "<!-- COMMON_HEAD -->",
            head
        )

        return html, True, "placeholder"

    # -----------------------------------------------------
    # CASE 2 - Existing <head>
    # -----------------------------------------------------

    head_match = re.search(
        r'<head\b[^>]*>(.*?)</head>',
        html,
        flags=re.DOTALL | re.IGNORECASE
    )

    if not head_match:
        return html, False, "not_found"

    old_head = head_match.group(1)

    # Preserve page-specific SEO/schema.
    page_seo = extract_page_seo(html)

    if page_seo:
        new_head = "\n    " + page_seo + "\n\n    " + head + "\n"
    else:
        new_head = "\n    " + head + "\n"

    html = (
        html[:head_match.start(1)]
        + new_head
        + html[head_match.end(1):]
    )

    return html, True, "old"


# =========================================================
# REPLACE HEADER
# =========================================================

def replace_header(html, header):
    """
    Replace either:

    1. Existing COMMON_HEADER placeholder

    OR

    2. Old website header:
       <header class="reveal_header">
       ...
       </header>

       <div class="nav_panel">
       ...
       </div>

       <main>

    The page-specific <main> content is preserved.
    """

    # -----------------------------------------------------
    # CASE 1
    # COMMON_HEADER already exists
    # -----------------------------------------------------

    if "<!-- COMMON_HEADER -->" in html:

        html = html.replace(
            "<!-- COMMON_HEADER -->",
            header
        )

        return html, True, "placeholder"

    # -----------------------------------------------------
    # CASE 2
    # OLD HEADER
    # -----------------------------------------------------

    old_header_pattern = (
        r'<header\b'
        r'[^>]*'
        r'class\s*=\s*["\'][^"\']*\breveal_header\b[^"\']*["\']'
        r'[^>]*>'
        r'.*?'
        r'(?=<main\b)'
    )

    html, count = re.subn(
        old_header_pattern,
        header + "\n",
        html,
        count=1,
        flags=re.DOTALL | re.IGNORECASE
    )

    if count:
        return html, True, "old"

    # -----------------------------------------------------
    # HEADER NOT FOUND
    # -----------------------------------------------------

    return html, False, "not_found"


# =========================================================
# REPLACE FOOTER
# =========================================================

def replace_footer(html, footer):
    """
    Replace either:

    1. Existing COMMON_FOOTER placeholder

    OR

    2. Old footer:
       <footer class="revealed">
       ...
       </footer>
    """

    # -----------------------------------------------------
    # CASE 1
    # COMMON_FOOTER placeholder
    # -----------------------------------------------------

    if "<!-- COMMON_FOOTER -->" in html:

        html = html.replace(
            "<!-- COMMON_FOOTER -->",
            footer
        )

        return html, True, "placeholder"

    # -----------------------------------------------------
    # CASE 2
    # OLD FOOTER
    # -----------------------------------------------------

    old_footer_pattern = (
        r'<footer\b'
        r'[^>]*'
        r'class\s*=\s*["\'][^"\']*\brevealed\b[^"\']*["\']'
        r'[^>]*>'
        r'.*?'
        r'</footer>'
    )

    html, count = re.subn(
        old_footer_pattern,
        footer,
        html,
        count=1,
        flags=re.DOTALL | re.IGNORECASE
    )

    if count:
        return html, True, "old"

    # -----------------------------------------------------
    # FOOTER NOT FOUND
    # -----------------------------------------------------

    return html, False, "not_found"


# =========================================================
# BUILD ONE HTML PAGE
# =========================================================

def build_page(page):

    print("\n----------------------------------------")
    print(f"Processing: {page.name}")
    print("----------------------------------------")

    # -----------------------------------------------------
    # READ SOURCE HTML
    # -----------------------------------------------------

    html = page.read_text(
        encoding="utf-8"
    )

    # -----------------------------------------------------
    # READ COMPONENTS
    # -----------------------------------------------------

    head = HEAD_FILE.read_text(
        encoding="utf-8"
    )

    header = HEADER_FILE.read_text(
        encoding="utf-8"
    )

    footer = FOOTER_FILE.read_text(
        encoding="utf-8"
    )

    # -----------------------------------------------------
    # PREPARE RELATIVE PATHS
    # -----------------------------------------------------

    prefix = get_prefix(page)

    head = prepare_component(
        head,
        prefix
    )

    header = prepare_component(
        header,
        prefix
    )

    footer = prepare_component(
        footer,
        prefix
    )

    # =====================================================
    # HEAD
    # =====================================================

    html, head_found, head_type = replace_head(
        html,
        head
    )

    if head_found:

        if head_type == "old":
            print("HEAD: old head replaced; SEO/schema preserved")

        elif head_type == "placeholder":
            print("HEAD: common placeholder replaced")

    else:

        print("WARNING: HEAD NOT FOUND")

    # =====================================================
    # HEADER
    # =====================================================

    html, header_found, header_type = replace_header(
        html,
        header
    )

    if header_found:

        if header_type == "old":
            print("HEADER: old header replaced")

        elif header_type == "placeholder":
            print("HEADER: common placeholder replaced")

    else:

        print("WARNING: HEADER NOT FOUND")

    # =====================================================
    # FOOTER
    # =====================================================

    html, footer_found, footer_type = replace_footer(
        html,
        footer
    )

    if footer_found:

        if footer_type == "old":
            print("FOOTER: old footer replaced")

        elif footer_type == "placeholder":
            print("FOOTER: common placeholder replaced")

    else:

        print("WARNING: FOOTER NOT FOUND")

    # =====================================================
    # CREATE BUILD PATH
    # =====================================================

    relative = page.relative_to(ROOT)

    destination = BUILD_DIR / relative

    destination.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # -----------------------------------------------------
    # WRITE GENERATED PAGE
    # -----------------------------------------------------

    destination.write_text(
        html,
        encoding="utf-8"
    )

    print(f"BUILT: {relative}")


# =========================================================
# COPY WEBSITE ASSETS
# =========================================================

def copy_assets():

    print("\n========================================")
    print("COPYING WEBSITE ASSETS")
    print("========================================")

    folders = [
        "css",
        "js",
        "img",
        "video",
        "phpmailer"
    ]

    for folder in folders:

        source = ROOT / folder
        destination = BUILD_DIR / folder

        if not source.exists():

            print(f"SKIPPED: {folder}/ not found")

            continue

        shutil.copytree(
            source,
            destination,
            dirs_exist_ok=True
        )

        print(f"COPIED: {folder}/")


# =========================================================
# BUILD WEBSITE
# =========================================================

def main():

    print("\n========================================")
    print("CSR LANDMARK WEBSITE BUILD")
    print("========================================")

    # -----------------------------------------------------
    # Check components
    # -----------------------------------------------------

    if not HEAD_FILE.exists():

        print("ERROR: components/head.html not found")

        return

    if not HEADER_FILE.exists():

        print("ERROR: components/header.html not found")

        return

    if not FOOTER_FILE.exists():

        print("ERROR: components/footer.html not found")

        return

    # -----------------------------------------------------
    # Create build folder
    # -----------------------------------------------------

    BUILD_DIR.mkdir(
        exist_ok=True
    )

    # -----------------------------------------------------
    # Build all root HTML pages
    # -----------------------------------------------------

    pages = list(
        ROOT.glob("*.html")
    )

    print(f"\nHTML pages found: {len(pages)}")

    for page in pages:

        build_page(page)

    # -----------------------------------------------------
    # Copy assets
    # -----------------------------------------------------

    copy_assets()

    # -----------------------------------------------------
    # Finished
    # -----------------------------------------------------

    print("\n========================================")
    print("BUILD COMPLETE")
    print("========================================")

    print("\nGenerated website:")
    print(BUILD_DIR)


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    main()
