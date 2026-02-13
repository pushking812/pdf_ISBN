import sys
import re
import fitz  # PyMuPDF

def validate_isbn10(isbn: str) -> bool:
    if len(isbn) != 10:
        return False
    total = 0
    for i in range(9):
        if not isbn[i].isdigit():
            return False
        total += int(isbn[i]) * (10 - i)
    last = isbn[9]
    if last == 'X':
        total += 10
    elif last.isdigit():
        total += int(last)
    else:
        return False
    return total % 11 == 0

def validate_isbn13(isbn: str) -> bool:
    if len(isbn) != 13 or not isbn.isdigit():
        return False
    total = 0
    for i in range(12):
        digit = int(isbn[i])
        total += digit * (1 if i % 2 == 0 else 3)
    check = (10 - (total % 10)) % 10
    return int(isbn[12]) == check

def find_isbn_in_text(text: str) -> str | None:
    patterns = [
        r'(?:ISBN(?:-10)?:?\s*)?((?:\d[-\s]?){9}[\dX])',
        r'(?:ISBN(?:-13)?:?\s*)?((?:97[89])[-\s]?(?:\d[-\s]?){9}\d)'
    ]
    for pat in patterns:
        for match in re.finditer(pat, text, re.IGNORECASE):
            candidate = match.group(1)
            clean = re.sub(r'[^\dX]', '', candidate)
            if len(clean) == 10 and validate_isbn10(clean):
                return clean
            if len(clean) == 13 and validate_isbn13(clean):
                return clean
    return None

def extract_isbn_from_pdf(pdf_path: str, pages_to_check: int = 5) -> str | None:
    doc = fitz.open(pdf_path)
    total_pages = len(doc)

    # Индексы страниц для проверки
    page_indices = set()
    for i in range(min(pages_to_check, total_pages)):
        page_indices.add(i)
    for i in range(max(0, total_pages - pages_to_check), total_pages):
        page_indices.add(i)

    for idx in sorted(page_indices):
        page = doc.load_page(idx)           # загружается только эта страница
        text = page.get_text("text")        # быстрое извлечение текста
        if text:
            isbn = find_isbn_in_text(text)
            if isbn:
                doc.close()
                return isbn
    doc.close()
    return None

def main():
    if len(sys.argv) < 2:
        print("Использование: python find_isbn.py <путь_к_pdf>")
        sys.exit(1)

    pdf_file = sys.argv[1]
    isbn = extract_isbn_from_pdf(pdf_file)
    if isbn:
        print(isbn)
    else:
        print("ISBN не найден")

if __name__ == '__main__':
    # import cProfile

    # pr = cProfile.Profile()
    # pr.enable()
    main()
    # pr.disable()
    # pr.dump_stats("output.prof")