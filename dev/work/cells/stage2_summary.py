# Concise summary; patient-level files stay under RESULTS_ROOT. No winner selection, no test retuning.
print('Stage 2 run',RUN_KEY,'|',RUN_MODE,'|',DATA_SOURCE,'| frozen:',PROTOCOL_FROZEN)
print('Rows returned:',len(RESULTS),'| conditions:',sorted(RESULTS.condition.unique().tolist()))
print('Arms with results:',sorted(RESULTS.arm.unique().tolist()))
if not PROTOCOL_FROZEN:
    print('Test-split rows are sealed on disk (test_rows_sealed.json per arm) and were not printed. They are released by a run with PROTOCOL_FROZEN=True after the signed tag.')
print('Folders: results',RESULTS_ROOT,'| team summary',RESULTS_ROOT/'team_summary','| data',DATA_ROOT)
