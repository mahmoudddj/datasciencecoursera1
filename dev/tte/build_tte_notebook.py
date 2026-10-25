"""Assemble TTE_Feasibility_MIMIC_eICU.ipynb from tte_feasibility_cells.py."""
import json,ast,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent));from tte_feasibility_cells import CELLS
cells=[]
for kind,src in CELLS:
    if kind=='code':ast.parse(src)
    cells.append({'cell_type':kind,'metadata':{},'source':src.rstrip('\n'),**({'execution_count':None,'outputs':[]} if kind=='code' else {})})
nb={'cells':cells,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python'}},'nbformat':4,'nbformat_minor':5}
out=Path(__file__).parent/'TTE_Feasibility_MIMIC_eICU.ipynb';out.write_text(json.dumps(nb,indent=1));print('written',out,len(cells),'cells')
