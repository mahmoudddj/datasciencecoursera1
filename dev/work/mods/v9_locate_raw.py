# 3. Recover dataset paths, then check the required raw tables.
# This cell reads folder names and small path manifests, not patient records.
# It can replace Section 3 in an existing v9 Colab session.
from pathlib import Path
from collections import deque
import os, json, time

RAW_REQUIRED = {
    'miiv': ['hosp/admissions', 'hosp/patients', 'hosp/labevents',
             'icu/icustays', 'icu/chartevents', 'icu/outputevents'],
    'eicu': ['patient', 'lab', 'vitalPeriodic', 'intakeOutput'],
}
RAW_OPTIONAL = {
    'miiv': ['hosp/microbiologyevents', 'hosp/prescriptions',
             'hosp/diagnoses_icd', 'icu/inputevents', 'icu/procedureevents'],
    'eicu': ['microLab', 'medication', 'infusionDrug', 'diagnosis',
             'treatment', 'apachePatientResult', 'respiratoryCare'],
}

def _table(root, stem):
    """Use the same CSV/gzip layout and filename matching as the raw extractor."""
    root, stem = Path(root), Path(stem)
    parent = root / stem.parent
    for ext in ('.csv.gz', '.csv'):
        p = parent / (stem.name + ext)
        if p.is_file():
            return p
    if parent.is_dir():
        wanted = {stem.name.lower() + '.csv', stem.name.lower() + '.csv.gz'}
        return next((p for p in parent.iterdir()
                     if p.is_file() and p.name.lower() in wanted), None)
    return None

def _manifest_paths(document):
    """Read both older {dataset: path} and newer {sources: {...}} records."""
    if not isinstance(document, dict):
        return {}
    sources = document.get('sources', document)
    if not isinstance(sources, dict):
        return {}
    paths = {}
    for ds in DATASETS:
        entry = sources.get(ds)
        if isinstance(entry, dict):
            entry = entry.get('raw_source') or entry.get('path') or entry.get('root')
        if isinstance(entry, str) and entry.strip():
            paths[ds] = entry.strip()
    return paths

def _atomic_path_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.partial')
    temporary.write_text(json.dumps(data, indent=2))
    os.replace(temporary, path)

def recover_raw_sources(previous=None):
    """Resolve visible folders without changing datasets, imports or labels."""
    if ALLOW_DEMO_DATA and globals().get('RUN_MODE', 'smoke') != 'smoke':
        raise ValueError('Demo data can be used only in smoke mode, not a full study run.')
    report = {'status': 'checking', 'scan_roots': [], 'top_level': {},
              'folders_scanned': 0, 'depth_limit': int(MAX_SEARCH_DEPTH),
              'max_folders': 20000, 'depth_cutoffs': [], 'access_errors': [],
              'manifests': [], 'candidates': [], 'selected': {}}
    global RAW_DISCOVERY_REPORT
    RAW_DISCOVERY_REPORT = report
    records, selected, seen_paths = {}, {}, set()
    seeds = {ds: [] for ds in DATASETS}
    explicit = {ds: str(RAW_SOURCE_PATHS.get(ds, '')).strip() for ds in DATASETS}
    scan_queue = []

    def inspect(ds, candidate, origin, force_record=False):
        p = Path(candidate).expanduser()
        try:
            real = p.resolve()
            key = (ds, str(real))
            if key in records:
                return records[key]
            record = {'dataset': ds, 'path': str(p), 'real_path': str(real),
                      'origin': origin, 'present': [], 'missing': [], 'usable': False}
            if not p.is_dir():
                record['reason'] = 'Folder is unavailable or is a broken link'
                if force_record:
                    records[key] = record
                return record
            present = {s: str(_table(p, s)) for s in RAW_REQUIRED[ds]
                       if _table(p, s) is not None}
            record['present'] = list(present)
            record['missing'] = [s for s in RAW_REQUIRED[ds] if s not in present]
            record['demo_marked'] = 'demo' in str(p).lower() or 'demo' in str(real).lower()
            if record['demo_marked'] and not ALLOW_DEMO_DATA:
                record['reason'] = 'Demo-named path excluded because ALLOW_DEMO_DATA=False'
            elif record['missing']:
                record['reason'] = 'Required raw CSV tables missing from the expected layout'
            else:
                record['usable'] = True
                record['reason'] = 'Required CSV/gzip tables found'
            name_hint = ('mimic' in p.name.lower() or p.name.lower() == 'miiv') if ds == 'miiv' else 'eicu' in p.name.lower()
            if present or name_hint or force_record:
                records[key] = record
            return record
        except (OSError, RuntimeError) as exc:
            report['access_errors'].append({'path': str(p), 'error': str(exc)})
            return {'dataset': ds, 'path': str(p), 'present': [], 'usable': False,
                    'reason': 'Folder could not be inspected: ' + str(exc)}

    # Prefer the user's explicit choice, followed by state retained in this session.
    for ds in DATASETS:
        if explicit[ds]:
            seeds[ds].append((explicit[ds], 'explicit RAW_SOURCE_PATHS'))
        value = (previous or {}).get(ds)
        if value:
            seeds[ds].append((str(value), 'current Colab session'))

    manifests = [VALIDATION_ROOT / 'resolved_raw_sources.json',
                 PROJECT / 'resolved_raw_sources.json',
                 PROJECT / 'validation_rich_v1' / 'resolved_raw_sources.json',
                 PROJECT / 'validation_folder_v2' / 'miiv_eicu' / 'resolved_raw_sources.json']
    # Older notebooks wrote their manifest one or two levels below validation_*.
    if PROJECT.is_dir():
        for folder in PROJECT.iterdir():
            if folder.is_dir() and folder.name.startswith('validation'):
                manifests.append(folder / 'resolved_raw_sources.json')
                manifests.extend(p / 'resolved_raw_sources.json' for p in folder.iterdir() if p.is_dir())
    read_manifests = set()
    for manifest in manifests:
        if str(manifest) in read_manifests or not manifest.is_file():
            continue
        read_manifests.add(str(manifest))
        try:
            if manifest.stat().st_size > 2 * 1024**2:
                raise ValueError('Path manifest unexpectedly exceeds 2 MB')
            paths = _manifest_paths(json.loads(manifest.read_text()))
            report['manifests'].append({'path': str(manifest), 'datasets': list(paths)})
            for ds, p in paths.items():
                # Relative paths, if any, are relative to the manifest location.
                p = Path(p).expanduser()
                if not p.is_absolute():
                    p = manifest.parent / p
                seeds[ds].append((str(p), 'saved manifest: ' + str(manifest)))
        except (OSError, ValueError) as exc:
            report['access_errors'].append({'path': str(manifest), 'error': str(exc)})

    # Previous notebook revisions used different link directories.
    mounts = [RICU_MOUNT, Path('/content/ricu_data_mount'), Path('/content/ricu_folder_mount')]
    for ds in DATASETS:
        for mount in mounts:
            link = mount / ds
            if link.exists() or link.is_symlink():
                seeds[ds].append((str(link), 'existing ricu source link'))
        for candidate, origin in seeds[ds]:
            row = inspect(ds, candidate, origin, True)
            if row.get('usable') and (not explicit[ds] or origin == 'explicit RAW_SOURCE_PATHS'):
                selected[ds] = Path(row['real_path'])
                print(f'{ds}: recovered from {origin} -> {selected[ds]}')
                break
            if Path(candidate).is_dir():
                scan_queue.append((Path(candidate), {ds}, origin))

    def scan(top, wanted, origin):
        top = Path(top)
        if not top.is_dir() or not wanted:
            return
        report['scan_roots'].append(str(top))
        queue = deque([(top, 0)])
        last_update = time.monotonic()
        while queue and report['folders_scanned'] < report['max_folders']:
            root, depth = queue.popleft()
            try:
                real = str(root.resolve())
                # Track dataset as well as directory: a previous scoped scan may
                # have searched this directory for only one of the two sources.
                search_here = {ds for ds in wanted if (ds, real) not in seen_paths}
                if not search_here:
                    continue
                seen_paths.update((ds, real) for ds in search_here)
                entries = sorted(root.iterdir(), key=lambda p: p.name.lower())
                report['folders_scanned'] += 1
                if depth == 0:
                    report['top_level'][str(top)] = [p.name + ('/' if p.is_dir() else '') for p in entries[:40]]
                found_here = set()
                for ds in search_here:
                    row = inspect(ds, root, origin)
                    if row.get('usable'):
                        found_here.add(ds)
                children = [p for p in entries if p.is_dir() and p.name not in
                            {'.git', '__pycache__', 'node_modules', '.ipynb_checkpoints'}]
                if depth >= int(MAX_SEARCH_DEPTH):
                    if children:
                        report['depth_cutoffs'].append(str(root))
                    continue
                # Do not enter a source's ricu partition directories once its
                # raw root has been recognized. Continue seeking other sources.
                if found_here == search_here:
                    continue
                for child in children:
                    queue.append((child, depth + 1))
                if time.monotonic() - last_update >= 15:
                    print(f"Folder scan: {report['folders_scanned']:,} checked; current: {root}", flush=True)
                    last_update = time.monotonic()
            except (OSError, RuntimeError) as exc:
                report['access_errors'].append({'path': str(root), 'error': str(exc)})

    def choose(ds, origin_prefix=None):
        candidates = [r for r in records.values() if r['dataset'] == ds and r.get('usable')]
        if explicit[ds]:
            parent = Path(explicit[ds]).expanduser().resolve()
            candidates = [r for r in candidates if Path(r['real_path']) == parent or parent in Path(r['real_path']).parents]
        if len(candidates) == 1:
            selected[ds] = Path(candidates[0]['real_path'])
        return candidates

    for top, wanted, origin in scan_queue:
        scan(top, wanted - set(selected), origin)
    for ds in DATASETS:
        if ds not in selected:
            choose(ds)

    remaining = set(DATASETS) - set(selected)
    # An explicit path may name a parent folder. Search beneath that folder,
    # but never silently substitute a different dataset copy elsewhere.
    auto_wanted = {ds for ds in remaining if not explicit[ds]}
    if auto_wanted and AUTO_FIND_RAW:
        roots = [DRIVE_ROOT]
        if PROJECT.resolve() != DRIVE_ROOT.resolve() and DRIVE_ROOT.resolve() not in PROJECT.resolve().parents:
            roots.append(PROJECT)
        shared = DRIVE_ROOT.parent / 'Shareddrives'
        if shared.is_dir():
            roots.append(shared)
        for root in roots:
            scan(root, auto_wanted, 'folder scan')
    for ds in DATASETS:
        if ds not in selected:
            choose(ds)

    report['selected'] = {ds: str(p) for ds, p in selected.items()}
    report['candidates'] = list(records.values())
    unresolved = [ds for ds in DATASETS if ds not in selected]
    report['status'] = 'needs_paths' if unresolved else 'resolved'
    report['unresolved'] = unresolved
    report_path = VALIDATION_ROOT / 'raw_discovery_report.json'
    _atomic_path_json(report_path, report)
    if unresolved:
        print('\nRAW-DATA DIAGNOSTIC — folder access and table names only')
        print('Mounted MyDrive path:', DRIVE_ROOT, '| readable folder:', DRIVE_ROOT.is_dir())
        print('Scanned folders:', report['folders_scanned'], '| scan roots:', report['scan_roots'])
        for path, names in report['top_level'].items():
            print('Visible entries in', path, ':', ', '.join(names) or '(empty)')
        for ds in unresolved:
            candidates = sorted((r for r in records.values() if r['dataset'] == ds),
                                key=lambda r: (-len(r.get('present', [])), r['path']))
            print('\n' + ds + ':')
            if not candidates:
                print('  No recognizable raw table layout was visible in the searched folders.')
            for row in candidates[:8]:
                print(' ', row['path'], '->', row['reason'])
                if row.get('missing'):
                    print('   Missing:', ', '.join(s + '.csv(.gz)' for s in row['missing']))
                if row.get('usable'):
                    print('   Multiple copies: select one with RAW_SOURCE_PATHS["' + ds + '"] = ' + repr(row['path']))
            print('  Expected:', ', '.join(RAW_REQUIRED[ds]))
        for entry in report['access_errors'][:6]:
            print('Access problem:', entry['path'], entry['error'])
        if report['depth_cutoffs']:
            print('Search depth reached at:', report['depth_cutoffs'][:5], '; increase MAX_SEARCH_DEPTH if needed.')
        if report['folders_scanned'] >= report['max_folders']:
            print('Folder scan limit reached; set the exact RAW_SOURCE_PATHS to avoid a broad scan.')
        print('\nSet RAW_SOURCE_PATHS in THIS cell before rerunning, using the actual folder path from Colab Files.')
        print('For miiv, select the parent of hosp/ and icu/. For eicu, select the folder containing patient.csv(.gz).')
        print('If expected folders are absent, check that Colab mounted the Google account containing your upload.')
        print('If only a demo is listed, it is excluded from full-data runs; do not relabel it as a full database.')
        print('A complete diagnostic was saved to:', report_path)
        raise FileNotFoundError('Raw folder resolution is incomplete for ' + ', '.join(unresolved) + '. See RAW-DATA DIAGNOSTIC above.')
    return selected

# Optional manual recovery: uncomment and enter a path copied from Colab Files.
# RAW_SOURCE_PATHS['miiv'] = '/content/drive/MyDrive/ACTUAL_MIMIC_FOLDER'
# RAW_SOURCE_PATHS['eicu'] = '/content/drive/MyDrive/ACTUAL_EICU_FOLDER'

resolved_raw = recover_raw_sources(globals().get('resolved_raw', {}))

# Check every target before changing any links. Never overwrite a real folder.
RICU_MOUNT.mkdir(parents=True, exist_ok=True)
for ds, source in resolved_raw.items():
    target = RICU_MOUNT / ds
    if target.exists() and not target.is_symlink() and target.resolve() != source.resolve():
        raise FileExistsError(f'{target} is a real folder; it has been left unchanged.')
for ds, source in resolved_raw.items():
    target = RICU_MOUNT / ds
    if target.is_symlink() and target.resolve(strict=False) != source.resolve():
        target.unlink()
    if not target.exists():
        target.symlink_to(source, target_is_directory=True)
    print(f'{ds}: {source} -> required raw table layout verified')

source_manifest = {'resolver_version': 'v9_source_recovery_3',
                   'discovery_root': str(DRIVE_ROOT), 'allow_demo_data': ALLOW_DEMO_DATA,
                   'sources': {ds: {'raw_source': str(root), 'ricu_link': str(RICU_MOUNT / ds),
                                   'required_tables': {s: str(_table(root, s)) for s in RAW_REQUIRED[ds]},
                                   'optional_tables_present': [s for s in RAW_OPTIONAL[ds] if _table(root, s)],
                                   'validated': True} for ds, root in resolved_raw.items()}}
_atomic_path_json(VALIDATION_ROOT / 'resolved_raw_sources.json', source_manifest)
print('Folder recovery complete. Continue to the next cell. Existing imports were left in place.')
