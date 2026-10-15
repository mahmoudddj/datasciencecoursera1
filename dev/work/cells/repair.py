# 4a. Optional one-step repair: replace core raw tables that the audit flags as demo-sized
#     with the official full files from PhysioNet (your credentialed login; nothing is stored).
if DATA_SOURCE=='clinical' and REPAIR_FROM_PHYSIONET:
    import getpass
    from v10_preflight import repair_from_physionet
    if not PHYSIONET_USERNAME:raise ValueError('Set PHYSIONET_USERNAME in Section 1.')
    _pw=getpass.getpass('PhysioNet password (used for this download only, never saved): ')
    try:
        REPAIR_ACTIONS=repair_from_physionet('miiv',resolved_raw['miiv'],PHYSIONET_USERNAME,_pw,MIMIC_IV_VERSION)
    finally:
        del _pw
    if REPAIR_ACTIONS:
        atomic_json(PROJECT/'physionet_repair_log.json',REPAIR_ACTIONS);display(pd.DataFrame(REPAIR_ACTIONS))
        print('Replaced tables will be re-imported into ricu once; keep ALLOW_FULL_RAW_IMPORT=True for this run.')
else:
    print('PhysioNet repair not requested (REPAIR_FROM_PHYSIONET=False).')
