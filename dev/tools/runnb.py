import sys,time,nbformat,os
from nbclient import NotebookClient
src,dst,proj=sys.argv[1],sys.argv[2],sys.argv[3]
os.environ['SEPSIS_DATA_SOURCE']=os.environ.get('SEPSIS_DATA_SOURCE','fixture')
os.environ['SEPSIS_PROJECT_ROOT']=proj
nb=nbformat.read(src,as_version=4)
t=time.time()
c=NotebookClient(nb,timeout=3600,kernel_name=os.environ.get('NB_KERNEL','sepsis312'),resources={'metadata':{'path':proj}})
try:
    c.execute()
    status='OK'
except Exception as e:
    status='FAIL: '+type(e).__name__+': '+str(e)[-3000:]
nbformat.write(nb,dst)
print(status,round(time.time()-t,1),'s')
