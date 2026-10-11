import json, os, sys

REQUIRED_FIELDS = {'id','topic','subtopic','difficulty','prompt','options','correct_index','explanation','source'}
files = [
  'data/mcq/mcq_ar_easy.json','data/mcq/mcq_ar_medium.json','data/mcq/mcq_ar_hard.json',
  'data/mcq/mcq_qu_easy.json','data/mcq/mcq_qu_medium.json','data/mcq/mcq_qu_hard.json',
  'data/mcq/mcq_gr_easy.json','data/mcq/mcq_gr_medium.json','data/mcq/mcq_gr_hard.json',
]
total = 0
errors = []
for f in files:
    data = json.load(open(f, encoding='utf-8'))
    n = len(data)
    total += n
    if n != 40:
        errors.append(f'{f}: expected 40, got {n}')
    for i, item in enumerate(data):
        missing = REQUIRED_FIELDS - set(item.keys())
        if missing:
            errors.append(f'{f}[{i}]: missing fields {missing}')
        if not isinstance(item.get('options'), list) or len(item['options']) != 4:
            errors.append(f'{f}[{i}]: options must be list of 4')
        ci = item.get('correct_index')
        if ci not in [0,1,2,3]:
            errors.append(f'{f}[{i}]: correct_index={ci} invalid')
        if item.get('source') != 'custom_mcq':
            errors.append(f'{f}[{i}]: source={item.get("source")} expected custom_mcq')
    print(f'OK  {f}: {n} items, topic={data[0]["topic"]}, difficulty={data[0]["difficulty"]}')
print(f'TOTAL: {total}')
if errors:
    print('ERRORS:')
    for e in errors:
        print(' ', e)
    sys.exit(1)
else:
    print('All files valid. No structural errors.')
