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

with pdfplumber.open(buf) as doc:
    for page_num, page in enumerate(doc.pages):
        tables = page.extract_tables()
        for table_num, table in enumerate(tables):
            if table and table[0]:
                print(f"\nPage {page_num+1}, Table {table_num+1} — header row:")
                print(table[0])
