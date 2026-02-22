import sys
sys.path.append('.')
from debug_selectors import run_search, create_driver, get_test_data_to_search
from argparse import Namespace

# создаем аргументы
args = Namespace(
    selenium=False,
    exact=False,
    case_sensitive=False,
    all_matches=False,
    verbose=True,
    search_mode='text',
)

# получаем паттерны, сгенерированные ранее (для простоты возьмём из вывода прошлого запуска)
# но мы можем сгенерировать их, запустив run_parse. Для экономии времени используем заранее известные паттерны.
patterns = [
    {
        'type': 'xpath',
        'selector': "//*[.//th[contains(text(), 'Автор')]]//th[contains(text(), 'Автор')]/following-sibling::td",
        'attribute': 'text',
        'resource_id': 'rsl'
    },
    {
        'type': 'xpath',
        'selector': "//*[.//th[contains(text(), 'Заглавие')]]//th[contains(text(), 'Заглавие')]/following-sibling::td",
        'attribute': 'text',
        'resource_id': 'rsl'
    },
    {
        'type': 'xpath',
        'selector': "//*[.//th[contains(text(), 'Выходные данные')]]//th[contains(text(), 'Выходные данные')]/following-sibling::td",
        'attribute': 'text',
        'resource_id': 'rsl'
    },
    {
        'type': 'xpath',
        'selector': "//*[.//th[contains(text(), 'Физическое описание')]]//th[contains(text(), 'Физическое описание')]/following-sibling::td",
        'attribute': 'text',
        'resource_id': 'rsl'
    },
]

print("Running run_search with patterns...")
results = run_search(args, patterns, driver=None)
print("Extracted values:", results)