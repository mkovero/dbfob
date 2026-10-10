# Headless build of both case variants: freecadcmd export_all.py  (PROCS="fdm" for one only)
# Builds make_case.py once per process, prints its fit report and writes the exports next to it.
import json, os
import FreeCAD as App

CASE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
src = open(os.path.join(CASE, 'make_case.py')).read()
for proc in os.environ.get('PROCS', 'sla fdm').split():
    ns = {'__name__': 'make_case', '__file__': os.path.join(CASE, 'make_case.py'), 'PROCESS': proc}
    exec(compile(src, 'make_case.py', 'exec'), ns)
    doc, report = ns['doc'], ns['report']
    files = ns['export'](doc, CASE)
    print('REPORT', proc, json.dumps({**report, 'files': [os.path.basename(f) for f in files]}), flush=True)
    App.closeDocument(doc.Name)
