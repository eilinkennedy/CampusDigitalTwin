'''import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','campus_twin.settings')

import importlib
views = importlib.import_module('dashboard.views')
print('loaded', views)
print('has visitor', hasattr(views,'visitor'))
print('dir entries containing visitor', [x for x in dir(views) if 'visitor' in x.lower()])'''
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','campus_twin.settings')

import importlib
views = importlib.import_module('dashboard.views')
print('loaded', views)
print('has visitor', hasattr(views,'visitor'))
print('dir entries containing visitor', [x for x in dir(views) if 'visitor' in x.lower()])