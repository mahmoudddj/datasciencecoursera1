"""Protocol freeze record (protocol section 11, step 3).

Run from the repository root on the commit to be frozen, AFTER the consultants' answers, the shared physiology set and
the build decisions are written into PROTOCOL.md and the notebook, and BEFORE any full-cohort training:

    python3 dev/tools/freeze_record.py

It writes FREEZE_RECORD.md with the SHA-256 of the protocol, the stage-2 notebook, the embedded modules and the
consultant survey, the current commit, and the exact commands for the two signed tags. It changes nothing else. Commit
FREEZE_RECORD.md, then create and push the signed tags on that commit, then deposit PROTOCOL.pdf (or .docx) and the
record in the OSF registration. The following commit sets PROTOCOL_FROZEN=True and PROTOCOL_FREEZE_TAG in the notebook."""
import hashlib,subprocess,datetime,json
from pathlib import Path
R=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
files=['PROTOCOL.md','Sepsis_V11_Improved_MIMIC_eICU_14_stage2.ipynb','dev/consultants/Consultant_Survey.md','dev/stage2/STAGE2_CODE_NOTES.md']
mods=sorted(p for p in (R/'dev/work/mods').glob('v*.py'))+[R/'dev/work/mods/feature_specs.json']
commit=subprocess.run(['git','rev-parse','HEAD'],cwd=R,capture_output=True,text=True).stdout.strip()
dirty=subprocess.run(['git','status','--porcelain'],cwd=R,capture_output=True,text=True).stdout.strip()
date=datetime.date.today().isoformat();tag=f'protocol-freeze-{date}'
lines=[f'# Protocol freeze record ({date})','',f'Commit: `{commit}`'+('  **WARNING: uncommitted changes present; commit first and rerun**' if dirty else ''),'',
       '| File | SHA-256 |','|---|---|']+[f'| `{f}` | `{sha(R/f)}` |' for f in files]
lines+=['',f'Embedded modules ({len(mods)} files), combined SHA-256 of their individual hashes: `'+hashlib.sha256(''.join(sha(m) for m in mods).encode()).hexdigest()+'`','',
        '| Module | SHA-256 |','|---|---|']+[f'| `{m.relative_to(R)}` | `{sha(m)}` |' for m in mods]
lines+=['','## Signing (each signer on their own machine, same commit)','','```',
        '# one-time key set-up (SSH signing; git >= 2.34)','git config --global gpg.format ssh','git config --global user.signingkey ~/.ssh/id_ed25519.pub',
        f'git fetch origin && git checkout {commit}',f'git tag -s {tag}-candidate -m "Protocol freeze: candidate"   # the partner uses {tag}-partner',
        f'git push origin {tag}-candidate','git tag -v '+tag+'-candidate','```','',
        '## Deposit','','1. Export the protocol: `pandoc PROTOCOL.md -o dev/protocol/Study_Protocol_frozen.docx` (and a PDF from it).',
        '2. OSF: create the registration, attach the protocol file and this record, enter the commit, the two tag names and the hashes above; note the registration DOI here.',
        '3. Next commit: `PROTOCOL_FROZEN = True`, `PROTOCOL_FREEZE_TAG = "'+tag+'"` and the final `PRIOR_TEST_EXPOSURE` text in the notebook; rebuild with `dev/tools/build14.py`; the notebook refuses full-cohort training otherwise.','',
        'Registration DOI: ______________________','','Any change after this record goes to `PROTOCOL_DEVIATIONS.md` with its date and reason.']
(R/'FREEZE_RECORD.md').write_text('\n'.join(lines)+'\n');print('written',R/'FREEZE_RECORD.md','commit',commit[:12],'dirty' if dirty else 'clean')
