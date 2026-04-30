import re

test = '21.04.2026     18:40     Bon-Nr.:9406'

treffer = re.search(r'\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}', test)

print(treffer.group())