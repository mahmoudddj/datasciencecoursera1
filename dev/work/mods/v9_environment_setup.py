# ============================================================
# SECTION 4A — YAIB extraction environment (unified conda env)
# Colab-safe: Python 3.10 + R 4.2.2 in ONE environment
# ============================================================

from pathlib import Path
import os, sys, time, json, shutil, hashlib, subprocess, re
import numpy as np
import pandas as pd

need_extract = (
    RUN_EXTRACTION
    and any((not cohort_complete(ds)) or FORCE_YAIB_REEXTRACT for ds in YAIB_DATASETS)
)
print("Need YAIB extraction:", need_extract)


def run_logged(cmd,log_name,cwd=None,env=None):
    return guarded_run(cmd,LOG_ROOT/log_name,cwd=cwd,env=env)

_COLAB_ENV_BEFORE=os.environ.copy()
os.environ.update({'MAKEFLAGS':'-j1','CMAKE_BUILD_PARALLEL_LEVEL':'1','RENV_CONFIG_INSTALL_PARALLEL':'FALSE'})


if not need_extract:
    print("Extraction environment setup skipped because cohorts already exist or RUN_EXTRACTION=False.")

else:
    print("\n" + "=" * 72)
    print("STEP 1 — SYSTEM BUILD DEPENDENCIES")
    print("=" * 72)
    subprocess.check_call(["apt-get", "update", "-qq"])
    subprocess.check_call([
        "apt-get", "install", "-y", "-qq",
        "build-essential", "gfortran", "cmake", "ninja-build", "git", "wget",
        "pkg-config", "libcurl4-openssl-dev", "libssl-dev", "libxml2-dev",
        "libudunits2-dev", "libgit2-dev", "libfontconfig1-dev",
        "libharfbuzz-dev", "libfribidi-dev", "libfreetype6-dev",
        "libpng-dev", "libjpeg-dev", "libtiff-dev",
        "libbz2-dev", "liblzma-dev", "libzstd-dev", "liblz4-dev",
    ])

    print("\n" + "=" * 72)
    print("STEP 2 — MINIFORGE")
    print("=" * 72)
    MINIFORGE = Path("/content/miniforge3")
    CONDA = MINIFORGE / "bin" / "conda"
    if not CONDA.is_file():
        installer = Path("/content/Miniforge3-Linux-x86_64.sh")
        subprocess.check_call([
            "wget", "-q", "-O", str(installer),
            "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh",
        ])
        subprocess.check_call(["bash", str(installer), "-b", "-p", str(MINIFORGE)])
    subprocess.check_call([str(CONDA), "config", "--set", "channel_priority", "strict"])

    print("\n" + "=" * 72)
    print("STEP 3 — UNIFIED YAIB PYTHON 3.10 + R 4.2.2 ENVIRONMENT")
    print("=" * 72)
    YAIB_ENV = Path("/content/yaib_py310_r422")
    YAIB_VENV = YAIB_ENV
    YAIB_PYTHON = YAIB_ENV / "bin" / "python"
    YAIB_R = YAIB_ENV / "bin" / "R"
    YAIB_RSCRIPT = YAIB_ENV / "bin" / "Rscript"

    def unified_env_ok():
        if not (YAIB_PYTHON.is_file() and YAIB_R.is_file() and YAIB_RSCRIPT.is_file()):
            return False
        try:
            pyver = subprocess.check_output(
                [str(YAIB_PYTHON), "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
                text=True,
            ).strip()
            rver = subprocess.check_output(
                [str(YAIB_RSCRIPT), "--vanilla", "-e", "cat(as.character(getRversion()))"],
                text=True,
            ).strip()
            return pyver == "3.10" and rver.startswith("4.2.2")
        except Exception:
            return False

    if not unified_env_ok():
        if YAIB_ENV.exists():
            shutil.rmtree(YAIB_ENV)
        subprocess.check_call([
            str(CONDA), "create", "-y", "-p", str(YAIB_ENV),
            "-c", "conda-forge", "--solver", "libmamba",
            "python=3.10", "r-base=4.2.2", "pip", "setuptools", "wheel",
            "c-compiler", "cxx-compiler", "fortran-compiler",
            "make", "cmake", "ninja", "pkg-config", "git", "curl",
            "libcurl", "openssl", "libxml2", "udunits2",
        ])
    if not unified_env_ok():
        raise RuntimeError("Unified YAIB conda environment failed version validation.")

    # --------------------------------------------------------
    # Pin an era-compatible compiler toolchain for the 2022-23
    # YAIB renv lockfile. Current conda-forge defaults can install
    # GCC 14+, while locked fstcore 0.9.14 relies on standard-library
    # transitive includes that changed in GCC 14. Keep R/Python and
    # all R package versions unchanged; only pin the compiler.
    # --------------------------------------------------------
    print("\n" + "=" * 72)
    print("STEP 3B — PIN GCC/G++/GFORTRAN 12 BUILD TOOLCHAIN")
    print("=" * 72)

    subprocess.check_call([
        str(CONDA), "install", "-y", "-p", str(YAIB_ENV),
        "-c", "conda-forge", "--solver", "libmamba",
        "gcc_linux-64=12",
        "gxx_linux-64=12",
        "gfortran_linux-64=12",
        "binutils_linux-64",
        "pkg-config",
        "lz4-c",
        "zstd",
    ])

    YAIB_CC = YAIB_ENV / "bin" / "x86_64-conda-linux-gnu-cc"
    YAIB_CXX = YAIB_ENV / "bin" / "x86_64-conda-linux-gnu-c++"
    YAIB_FC = YAIB_ENV / "bin" / "x86_64-conda-linux-gnu-gfortran"

    for compiler in [YAIB_CC, YAIB_CXX, YAIB_FC]:
        if not compiler.is_file():
            raise FileNotFoundError(f"Pinned compiler missing: {compiler}")

    cxx_banner = subprocess.check_output(
        [str(YAIB_CXX), "--version"], text=True
    ).splitlines()[0]
    print("YAIB C++ compiler:", cxx_banner)

    m = re.search(r"(?:gcc|g\+\+|GCC).*?([0-9]+)\.", cxx_banner, re.I)
    if m and int(m.group(1)) != 12:
        raise RuntimeError(
            f"Expected GCC/G++ 12 toolchain for YAIB restore, got: {cxx_banner}"
        )

    python_version = subprocess.check_output(
        [str(YAIB_PYTHON), "-c", "import sys; print(sys.version.split()[0])"], text=True
    ).strip()
    R_HOME = subprocess.check_output([str(YAIB_R), "RHOME"], text=True).strip()
    r_version = subprocess.check_output(
        [str(YAIB_RSCRIPT), "--vanilla", "-e", "cat(R.version.string)"], text=True
    ).strip()

    print("Colab/runtime Python:", sys.version.split()[0])
    print("YAIB Python:", python_version)
    print("YAIB R:", r_version)
    print("YAIB R_HOME:", R_HOME)

    if not python_version.startswith("3.10."):
        raise RuntimeError(f"Expected YAIB Python 3.10, got {python_version}")
    if "4.2.2" not in r_version:
        raise RuntimeError(f"Expected YAIB R 4.2.2, got {r_version}")

    env_bin = str(YAIB_ENV / "bin")
    old_path = os.environ.get("PATH", "")
    os.environ["PATH"] = env_bin + ":" + ":".join(p for p in old_path.split(":") if p and p != env_bin)
    old_ld = os.environ.get("LD_LIBRARY_PATH", "")
    os.environ["LD_LIBRARY_PATH"] = str(YAIB_ENV / "lib") + ((":" + old_ld) if old_ld else "")
    os.environ["R_HOME"] = R_HOME
    os.environ["CONDA_PREFIX"] = str(YAIB_ENV)
    os.environ["CC"] = str(YAIB_CC)
    os.environ["CXX"] = str(YAIB_CXX)
    os.environ["CXX11"] = str(YAIB_CXX)
    os.environ["CXX14"] = str(YAIB_CXX)
    os.environ["CXX17"] = str(YAIB_CXX)
    os.environ["CXX20"] = str(YAIB_CXX)
    os.environ["FC"] = str(YAIB_FC)
    os.environ["F77"] = str(YAIB_FC)
    _pc = [str(YAIB_ENV / "lib" / "pkgconfig"), str(YAIB_ENV / "share" / "pkgconfig")]
    _old_pc = os.environ.get("PKG_CONFIG_PATH", "")
    os.environ["PKG_CONFIG_PATH"] = ":".join(_pc + ([_old_pc] if _old_pc else []))

    if Path(shutil.which("Rscript")).resolve() != YAIB_RSCRIPT.resolve():
        raise RuntimeError(f"Rscript PATH mismatch: {shutil.which('Rscript')}")

    print("\n" + "=" * 72)
    print("STEP 4 — PINNED YAIB-COHORTS SOURCE")
    print("=" * 72)

    if COHORT_REPO.exists():
        shutil.rmtree(COHORT_REPO)
    subprocess.check_call(["git", "init", str(COHORT_REPO)])
    subprocess.check_call(["git", "-C", str(COHORT_REPO), "remote", "add", "origin",
                           "https://github.com/rvandewater/YAIB-cohorts.git"])
    subprocess.check_call(["git", "-C", str(COHORT_REPO), "fetch", "--depth", "1", "origin",
                           YAIB_COHORTS_COMMIT])
    subprocess.check_call(["git", "-C", str(COHORT_REPO), "checkout", "--detach", "FETCH_HEAD"])
    actual_commit = subprocess.check_output(
        ["git", "-C", str(COHORT_REPO), "rev-parse", "HEAD"], text=True
    ).strip()

    if actual_commit != YAIB_COHORTS_COMMIT:
        raise RuntimeError(f"Wrong YAIB commit. Expected {YAIB_COHORTS_COMMIT}, got {actual_commit}")
    print("YAIB-cohorts commit:", actual_commit)

    print("\n" + "=" * 72)
    print("STEP 5 — OUTCOME WINDOW PATCH")
    print("=" * 72)

    util_path = COHORT_REPO / "Python" / "src" / "ricu_utils.py"
    upstream = util_path.read_text()
    old_code = "x.groupby('stay_id')[outc_name].ffill(limit=window).bfill(limit=window).fillna(0)"
    new_code = (
        "x.groupby('stay_id', sort=False)[outc_name]"
        ".transform(lambda s: s.ffill(limit=window).bfill(limit=window)).fillna(0)"
    )
    if upstream.count(old_code) != 1:
        raise RuntimeError(
            "Pinned YAIB source changed; expected outcome-window expression not found exactly once."
        )
    corrected = upstream.replace(old_code, new_code, 1)
    util_path.write_text(corrected)

    patch_record = {
        "base_commit": actual_commit,
        "patch": "grouped_outcome_fill_v1",
        "before_sha256": hashlib.sha256(upstream.encode()).hexdigest(),
        "after_sha256": hashlib.sha256(corrected.encode()).hexdigest(),
    }
    COHORT_BASE.mkdir(parents=True, exist_ok=True)
    (COHORT_BASE / "extraction_patch.json").write_text(json.dumps(patch_record, indent=2))

    fixture = pd.DataFrame({"stay_id": [1,1,2,2], "label": [np.nan,np.nan,1.0,np.nan]})
    fixture_y = (
        fixture.groupby("stay_id", sort=False)["label"]
        .transform(lambda s: s.ffill(limit=6).bfill(limit=6))
        .fillna(0)
    )
    assert fixture_y.tolist() == [0.0,0.0,1.0,1.0]
    print("Patient/stay boundary regression test: PASS")

    print("\n" + "=" * 72)
    print("STEP 6 — PYTHON DEPENDENCIES / RPY2")
    print("=" * 72)

    renv_cache = PROJECT / "renv_cache_r422_unified"
    pip_cache = PROJECT / "pip_cache"
    renv_cache.mkdir(parents=True, exist_ok=True)
    pip_cache.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.update({
        "PATH": os.environ["PATH"],
        "LD_LIBRARY_PATH": os.environ["LD_LIBRARY_PATH"],
        "R_HOME": R_HOME,
        "CONDA_PREFIX": str(YAIB_ENV),
        "CC": str(YAIB_CC),
        "CXX": str(YAIB_CXX),
        "CXX11": str(YAIB_CXX),
        "CXX14": str(YAIB_CXX),
        "CXX17": str(YAIB_CXX),
        "CXX20": str(YAIB_CXX),
        "FC": str(YAIB_FC),
        "F77": str(YAIB_FC),
        "PKG_CONFIG_PATH": os.environ["PKG_CONFIG_PATH"],
        "RENV_PATHS_CACHE": str(renv_cache),
        "PIP_CACHE_DIR": str(pip_cache),
        "RENV_CONFIG_PROMPT_ENABLED": "FALSE",
        "CI": "true",
        "PYTHONUNBUFFERED": "1",
        "LIBARROW_BINARY": "true",
        "RPY2_CFFI_MODE": "API",
    })

    subprocess.run([
        str(YAIB_PYTHON), "-m", "pip", "uninstall", "-y",
        "rpy2", "rpy2-rinterface", "rpy2-robjects"
    ], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    run_logged(
        [YAIB_PYTHON, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"],
        "yaib_pip_bootstrap.log",
        env=env,
    )
    # rpy2 3.6.7+ requires R >= 4.5.0. YAIB is pinned to R 4.2.2,
    # so use the last compatible 3.5.x bridge and build it against this exact R.
    run_logged(
        [YAIB_PYTHON, "-m", "pip", "install",
         "--no-cache-dir", "--no-binary=rpy2",
         "rpy2==3.5.11", "numpy<2", "pandas<3", "pyarrow", "PyYAML"],
        "yaib_python_deps.log",
        env=env,
    )

    libR = Path(R_HOME) / "lib" / "libR.so"
    if not libR.is_file():
        raise FileNotFoundError(f"R shared library not found: {libR}")

    run_logged(
        [YAIB_PYTHON, "-c",
         f"import ctypes; ctypes.CDLL({str(libR)!r}); print('libR.so load: OK')"],
        "yaib_libR_check.log",
        env=env,
    )

    rpy2_code = '''import os, sys
from importlib.metadata import version
print("Python:", sys.version)
print("R_HOME env:", os.environ.get("R_HOME"))
print("CONDA_PREFIX:", os.environ.get("CONDA_PREFIX"))
print("LD_LIBRARY_PATH:", os.environ.get("LD_LIBRARY_PATH"))
print("rpy2 package version:", version("rpy2"))
import rpy2.robjects as ro
print("rpy2 import: OK")
print("R version:", ro.r("R.version.string")[0])
print("R home:", ro.r("R.home()")[0])
result = ro.r("1 + 1")[0]
assert result == 2
print("R evaluation test: OK")
'''
    run_logged(
        [YAIB_PYTHON, "-c", rpy2_code],
        "yaib_rpy2_bridge_check.log",
        env=env,
    )

    bridge_version = subprocess.check_output(
        [str(YAIB_PYTHON), "-c",
         "import rpy2.robjects as ro; print(ro.r('R.version.string')[0])"],
        env=env,
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()
    if "4.2.2" not in bridge_version:
        raise RuntimeError("rpy2 is not connected to R 4.2.2. Got:\n" + bridge_version)

    print("\n" + "=" * 72)
    print("STEP 7 — RESTORE YAIB R ENVIRONMENT")
    print("=" * 72)

    py_dir = COHORT_REPO / "Python"
    activate_script = py_dir / "renv" / "activate.R"
    lockfile = py_dir / "renv.lock"
    if not activate_script.is_file():
        raise FileNotFoundError(f"Missing {activate_script}")
    if not lockfile.is_file():
        raise FileNotFoundError(f"Missing {lockfile}")

    restore_expression = '''options(renv.config.prompt.enabled = FALSE)
Sys.setenv(RENV_CONFIG_PROMPT_ENABLED="FALSE", CI="true", LIBARROW_BINARY="true")
cat("R version:", R.version.string, "\n")
cat("R home:", R.home(), "\n")
cat("Working directory:", getwd(), "\n")
source("renv/activate.R")
cat("renv version:", as.character(packageVersion("renv")), "\n")
cat("Starting renv::restore(prompt = FALSE)...\n")
renv::restore(project=getwd(), lockfile="renv.lock", prompt=FALSE)
cat("\nRENV_RESTORE_COMPLETE\n")
'''

    run_logged(
        [YAIB_RSCRIPT, "--vanilla", "-e", restore_expression],
        "yaib_renv_restore_r422_unified.log",
        cwd=py_dir,
        env=env,
    )

    print("\n" + "=" * 72)
    print("STEP 8 — VERIFY YAIB R PACKAGES")
    print("=" * 72)

    verify_expression = '''options(renv.config.prompt.enabled = FALSE)
Sys.setenv(RENV_CONFIG_PROMPT_ENABLED="FALSE", CI="true")
source("renv/activate.R")
required <- c("ricu", "arrow", "data.table", "readr", "yaml")
for (pkg in required) {
  if (!requireNamespace(pkg, quietly=TRUE)) stop(paste0("Required R package missing: ", pkg))
  cat(pkg, " = ", as.character(packageVersion(pkg)), "\n", sep="")
}
cat("YAIB_R_PACKAGES_OK\n")
'''

    run_logged(
        [YAIB_RSCRIPT, "--vanilla", "-e", verify_expression],
        "yaib_r_package_check_r422_unified.log",
        cwd=py_dir,
        env=env,
    )

    print("\n" + "=" * 72)
    print("STEP 9 — FINAL PYTHON/R SANITY CHECK")
    print("=" * 72)

    sanity_code = '''import rpy2.robjects as ro
from rpy2.robjects.packages import importr
print("R:", ro.r("R.version.string")[0])
print("R_HOME:", ro.r("R.home()")[0])
ro.r('source("renv/activate.R")')
importr("ricu"); print("ricu import: OK")
importr("arrow"); print("arrow import: OK")
importr("data.table"); print("data.table import: OK")
print("YAIB Python/R environment: READY")
'''

    run_logged(
        [YAIB_PYTHON, "-c", sanity_code],
        "yaib_final_environment_check_r422_unified.log",
        cwd=py_dir,
        env=env,
    )

    VALIDATION_ROOT.mkdir(parents=True, exist_ok=True)
    rpy2_version = subprocess.check_output(
        [str(YAIB_PYTHON), "-c",
         "from importlib.metadata import version; print(version('rpy2'))"],
        env=env,
        text=True,
    ).strip()

    environment_manifest = {
        "yaib_cohorts_commit": actual_commit,
        "colab_python": sys.version.split()[0],
        "yaib_env": str(YAIB_ENV),
        "yaib_python": python_version,
        "yaib_python_path": str(YAIB_PYTHON),
        "R_version": r_version,
        "R_binary": str(YAIB_R),
        "Rscript": str(YAIB_RSCRIPT),
        "R_HOME": R_HOME,
        "rpy2": rpy2_version,
        "C_compiler": str(YAIB_CC),
        "CXX_compiler": str(YAIB_CXX),
        "Fortran_compiler": str(YAIB_FC),
        "CXX_banner": cxx_banner,
        "renv_project": str(py_dir),
        "renv_lockfile": str(lockfile),
        "renv_cache": str(renv_cache),
        "outcome_patch": patch_record,
    }
    manifest_path = VALIDATION_ROOT / "yaib_environment_manifest.json"
    manifest_path.write_text(json.dumps(environment_manifest, indent=2))

    print("\n" + "=" * 72)
    print("YAIB ENVIRONMENT READY")
    print("=" * 72)
    print("YAIB commit :", actual_commit)
    print("YAIB env    :", YAIB_ENV)
    print("YAIB Python :", YAIB_PYTHON)
    print("Python ver. :", python_version)
    print("YAIB R      :", r_version)
    print("Rscript     :", YAIB_RSCRIPT)
    print("rpy2        :", rpy2_version)
    print("Manifest    :", manifest_path)
    print("=" * 72)

# Retain the unified environment for the import/extraction workers, then restore Colab.
YAIB_RUNTIME_ENV=dict(env) if need_extract else {}
for k in list(os.environ):
    if k not in _COLAB_ENV_BEFORE:os.environ.pop(k,None)
os.environ.update(_COLAB_ENV_BEFORE)