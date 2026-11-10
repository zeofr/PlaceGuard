set -e
cd "D:\PLACEGUARD-ZAID\PlaceGuard"
mkdir -p eval/variance_runs
for i in 1 2 3; do
  echo "=== FINAL VARIANCE RUN $i: run_eval (104 cases) ==="
  python -m eval.run_eval > eval/variance_runs/run_eval_run${i}.log 2>&1
  cp eval/placeguard_results.json eval/variance_runs/placeguard_results_run${i}.json
  echo "=== FINAL VARIANCE RUN $i: baseline_llm_only ==="
  python -m eval.baseline_llm_only > eval/variance_runs/baseline_run${i}.log 2>&1
  cp eval/baseline_llm_only_results.json eval/variance_runs/baseline_llm_only_results_run${i}.json
  echo "=== FINAL VARIANCE RUN $i DONE ==="
done
echo "=== RETRIEVAL (deterministic, run once) ==="
python -m eval.eval_retrieval > eval/variance_runs/retrieval.log 2>&1
echo "=== WITH-EXPLANATION RUN (hallucination rate, run once) ==="
python -m eval.run_eval --with-explanation > eval/variance_runs/run_eval_explanation.log 2>&1
cp eval/placeguard_results.json eval/variance_runs/placeguard_results_explanation.json
echo "=== COMPARE BASELINES ==="
python -m eval.compare_baselines > eval/variance_runs/compare_baselines.log 2>&1
echo "ALL_FINAL_VARIANCE_DONE"
