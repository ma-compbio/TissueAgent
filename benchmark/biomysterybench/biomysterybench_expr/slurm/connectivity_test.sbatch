#!/usr/bin/env bash
#SBATCH --job-name=bmb-conntest
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --output=/work/magroup/wenduoc/TissueAgent/benchmark/biomysterybench/biomysterybench_expr/slurm/logs/conntest-%j.out
# Verify a compute node can reach the LLM + data endpoints TissueAgent needs.
set -uo pipefail
echo "host: $(hostname)   date: $(date)"
echo "OPENAI_API_KEY present: ${OPENAI_API_KEY:+yes}"
echo "ANTHROPIC_API_KEY present: ${ANTHROPIC_API_KEY:+yes}"
echo "HF_TOKEN present: ${HF_TOKEN:+yes}"
for url in https://api.openai.com/v1/models https://api.anthropic.com/v1/models https://huggingface.co; do
  code=$(curl -s -o /dev/null -m 15 -w '%{http_code}' "$url" || echo "curl-failed")
  echo "reach $url -> $code"
done
echo "DONE"
