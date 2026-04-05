import sys, os, io
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pikepdf
import pdfplumber

pdf_path = sys.argv[1]
password = sys.argv[2] if len(sys.argv) > 2 else ""

pdf = pikepdf.open(pdf_path, password=password)
buf = io.BytesIO()
pdf.save(buf)
buf.seek(0)

MAX_PAGES = 4   # inspect first N pages only

with pdfplumber.open(buf) as doc:
    for page_num, page in enumerate(doc.pages[:MAX_PAGES]):

        # --- tables ---
        tables = page.extract_tables()
        if tables:
            for table_num, table in enumerate(tables):
                if table and table[0]:
                    print(f"\n[Page {page_num+1}] Table {table_num+1} — header row:")
                    print("  ", table[0])
                    print(f"  Sample rows (up to 3):")
                    for row in table[1:4]:
                        print("  ", row)
        else:
            print(f"\n[Page {page_num+1}] No tables detected.")

        # --- raw text (first 3000 chars per page) ---
        text = page.extract_text() or ""
        if text.strip():
            print(f"\n[Page {page_num+1}] Raw text (first 3000 chars):")
            print("-" * 60)
            print(text[:3000])
            print("-" * 60)
