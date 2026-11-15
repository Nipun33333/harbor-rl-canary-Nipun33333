# Harbor RL Internship Project

This repository is publishing the full source tree from the submission bundle. The first GitHub Actions run expands the archive into normal folders, runs the reward-verifier checks, and commits the complete project to main.

After that run finishes, use the Actions tab:

1. Open Harbor LLM trials (FREE Groq model only).
2. Add GROQ_API_KEY under Settings > Secrets and variables > Actions. Never commit or paste the key into chat.
3. Run the workflow manually. It uses only groq/openai/gpt-oss-20b and checks model access before the six trials start.

The Groq API key should remain on the Free plan. Do not enable paid billing or upgrade. The project includes the complete local verifier, Harbor task, setup guide, reward design, anti-cheat canary, and submission checklist.
