# קבצים לבדיקות של השירות

`protected.pdf`: עמוד ריק אחד, מוצפן בסיסמה (AES-128, סיסמת משתמש `secret`). PDFium מחזיר עליו `FPDF_ERR_PASSWORD` (4). נבנה פעם אחת ב-pypdfium2 5.13 וב-pypdf 5.4.0, שאינה תלות של הריפו:

```python
import io, pypdfium2 as pdfium
from pypdf import PdfReader, PdfWriter
src = pdfium.PdfDocument.new(); src.new_page(200, 200); buf = io.BytesIO(); src.save(buf)
w = PdfWriter(clone_from=PdfReader(io.BytesIO(buf.getvalue())))
w.encrypt(user_password="secret", owner_password="owner", algorithm="AES-128")
w.write("tests/fixtures/protected.pdf")
```
