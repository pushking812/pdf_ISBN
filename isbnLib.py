import isbnlib

def get_book_info_simple(isbn):
    """
    Получает информацию о книге по ISBN через isbnlib.
    """
    try:
        # Очищаем ISBN от дефисов
        clean_isbn = isbnlib.canonical(isbn)
        
        # Получаем метаданные
        meta = isbnlib.meta(clean_isbn)
        if meta:
            return {
                'title': meta.get('Title', 'Нет названия'),
                'authors': meta.get('Authors', ['Неизвестный автор'])
            }
        else:
            print(f"Книга с ISBN {isbn} не найдена.")
            return None
    except Exception as e:
        print(f"Ошибка: {e}")
        return None

# Пример использования
isbn = "9785907144521"  # Пример ISBN русской книги
book = get_book_info_simple(isbn)
if book:
    print(f"Название: {book['title']}")
    print(f"Автор(ы): {', '.join(book['authors'])}")