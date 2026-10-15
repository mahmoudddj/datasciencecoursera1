# 1. Configuration — change RUN_MODE only when you choose to launch full training.
# Paths: set PROJECT_PATH and RAW_SOURCE_PATHS here (or via the SEPSIS_* environment variables).
from pathlib import Path
import os,sys,json,time,subprocess,hashlib,shutil,re,gc,importlib.util,warnings
RUN_MODE = 'smoke'                         # 'smoke' | 'full'; never auto-escalates
DATA_SOURCE = os.environ.get('SEPSIS_DATA_SOURCE','clinical')  # 'clinical' | 'fixture'
MOUNT_GOOGLE_DRIVE = DATA_SOURCE == 'clinical' and importlib.util.find_spec('google') is not None and importlib.util.find_spec('google.colab') is not None
PROJECT_PATH = os.environ.get('SEPSIS_PROJECT_ROOT','')
RAW_SOURCE_PATHS = {'miiv':os.environ.get('SEPSIS_MIMIC_ROOT',''),
                    'eicu':os.environ.get('SEPSIS_EICU_ROOT','')}
REUSE_COHORT_ROOT = ''                     # optional existing .../cohorts_v9/<key>/sepsis
RELEASE_FINAL_HOLDOUT = False              # full only; prespecify before opening final results
ALLOW_FULL_RAW_IMPORT = False              # False = reuse the existing ricu import (verify only); stops and names any table that would need re-import
REPAIR_FROM_PHYSIONET = False              # True: download full versions of demo-sized MIMIC-IV core tables (Section 4a)
PHYSIONET_USERNAME = ''                    # your PhysioNet login; the password is asked for and never saved
MIMIC_IV_VERSION = '3.1'                   # must match the release in RAW_SOURCE_PATHS['miiv']
RUN_EXTRACTION = True
FORCE_RICU_REIMPORT = False
FORCE_YAIB_REEXTRACT = False
SMOKE_STAYS_PER_DATASET = 1200             # random candidate sample before YAIB extraction
MAX_HOURS = 120
HORIZON_HOURS = 6
RANDOM_STATE = 42
R_IMPORT_CHUNK_ROWS = 250_000
R_IMPORT_PARTITION_ROWS = 250_000
COHORT_BATCH_STAYS = 64
FEATURE_BATCH_STAYS = 32
TRAIN_BATCH_SIZE = 8
DUCKDB_MEMORY = '1GB'
PRIOR_TEST_EXPOSURE = ''                   # REQUIRED before full mode: earlier looks at MIMIC/eICU legacy results
AUTO_FIND_RAW = True
ALLOW_DEMO_DATA = False
MAX_SEARCH_DEPTH = 8
DATASETS = ['miiv','eicu']; YAIB_DATASETS = DATASETS.copy()
YAIB_COHORTS_COMMIT = '74ac699f5d4117613f9c48bdc4e0852099c42e19'
assert RUN_MODE in {'smoke','full'} and DATA_SOURCE in {'clinical','fixture'}
assert not (RUN_MODE=='smoke' and RELEASE_FINAL_HOLDOUT)
assert not (DATA_SOURCE=='fixture' and RUN_MODE=='full'), 'Fixtures are engineering smoke only.'
assert not (RUN_MODE=='full' and not PRIOR_TEST_EXPOSURE.strip()), 'Record PRIOR_TEST_EXPOSURE ("none" if truly none) before full mode.'
if MOUNT_GOOGLE_DRIVE:
    from google.colab import drive
    drive.mount('/content/drive')
DRIVE_ROOT=Path('/content/drive/MyDrive') if MOUNT_GOOGLE_DRIVE else Path.home()
PROJECT=Path(PROJECT_PATH or (DRIVE_ROOT/'sepsis_colab_project')).expanduser().resolve()
RUNTIME_ROOT=Path('/content') if MOUNT_GOOGLE_DRIVE else PROJECT/'runtime'
RUNTIME_ROOT.mkdir(parents=True,exist_ok=True)
COHORT_REPO=RUNTIME_ROOT/'YAIB-cohorts';YAIB_VENV=RUNTIME_ROOT/'yaib_py310_r422';YAIB_PYTHON=YAIB_VENV/'bin/python'
VALIDATION_ROOT=PROJECT/'validation_v10';CODE_DIR=VALIDATION_ROOT/'code'
TOOLS_ROOT=PROJECT/'tools';LOG_ROOT=PROJECT/'pipeline_logs_v10';RICU_MOUNT=RUNTIME_ROOT/'ricu_rich_mount'
COHORT_BASE=PROJECT/'cohorts_v9';COHORT_ROOT=COHORT_BASE/'sepsis'
for p in [PROJECT,CODE_DIR,TOOLS_ROOT,LOG_ROOT,RICU_MOUNT,COHORT_ROOT]:p.mkdir(parents=True,exist_ok=True)
needed={'numpy':'numpy','pandas':'pandas','torch':'torch','pyarrow':'pyarrow','duckdb':'duckdb','sklearn':'scikit-learn','psutil':'psutil','matplotlib':'matplotlib'}
missing=[v for k,v in needed.items() if importlib.util.find_spec(k) is None]
if missing:subprocess.check_call([sys.executable,'-m','pip','install','-q',*missing])
# Strict RFC CSV parsing (strict_mode) needs DuckDB >= 1.2; upgrade BEFORE duckdb is first imported.
from importlib.metadata import version as _v
if tuple(int(x) for x in _v('duckdb').split('.')[:2])<(1,2):
    if 'duckdb' in sys.modules:raise RuntimeError('DuckDB < 1.2 already imported: restart the runtime, then rerun from the top.')
    subprocess.check_call([sys.executable,'-m','pip','install','-q','duckdb>=1.2,<2'])
import numpy as np,pandas as pd,torch,psutil
from importlib.metadata import version
torch.set_num_threads(2)
RUNTIME_VERSIONS={p:version(p) for p in needed.values()}
warnings.filterwarnings('ignore',message='enable_nested_tensor is True')
print('Mode:',RUN_MODE,'| data:',DATA_SOURCE,'| full holdout released:',RELEASE_FINAL_HOLDOUT)
print('RAM available GB:',round(psutil.virtual_memory().available/1024**3,1),'| project:',PROJECT)

# Legacy-specific settings — all paths are in this visible configuration section.
LEGACY_MODE = 'reproduce'                  # 'reproduce' | 'import_original' | 'frozen'
PHYSIONET_SOURCE = os.environ.get('SEPSIS_PHYSIONET_SOURCE','')  # official PSV folder or patient-contiguous cleaned CSV
LEGACY_FEATURE_POLICY = 'original_rule'    # 'original_rule' = original scripts' column rule | 'common_core' (14 channels)
# import_original: folders the ORIGINAL scripts wrote (OSTA_SAVE_DIR=outputs/osta, PAPER1_SAVE_DIR=outputs/paper1)
ORIGINAL_OUTPUT_DIRS = {'osta':'', 'cnn':''}
HISTORICAL_SOURCE_REPRESENTATION = ''      # 'patient_forward_filled' | 'sparse_hourly'; inferred from PHYSIONET_SOURCE when set
HISTORICAL_SOURCE_UNITS = {}               # e.g. {'FiO2':'fraction'}; inferred from PHYSIONET_SOURCE when set
OSTA_HISTORICAL_SEEDS = [42,7,123]         # original OSTA_SEEDS
OSTA_HISTORICAL_ENSEMBLE = {'combine':'mean_probability','weights':None}  # original OSTA_ENSEMBLE_WEIGHTING='uniform'
HISTORICAL_BUNDLES = {'osta':'', 'cnn':''}  # frozen: complete legacy-bundle-v2 folders
assert LEGACY_MODE in {'frozen','reproduce','import_original'} and LEGACY_FEATURE_POLICY in {'original_rule','common_core'}
# Never share Notebook A's mutable module directory while both kernels run.
VALIDATION_ROOT=PROJECT/'legacy_validation_v10';CODE_DIR=VALIDATION_ROOT/'code';CODE_DIR.mkdir(parents=True,exist_ok=True)
