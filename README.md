# Acme Outfitters support agent

A customer-support agent for a fictional outdoor store. It looks up customers'
orders through the store's Orders API and runs in an
[NVIDIA OpenShell](https://docs.nvidia.com/openshell/) sandbox.

This is the agent team's repo. It's delivered by the pipeline in
[`agent-delivery-demo`](https://github.com/akuity/agent-delivery-demo), which promotes
each version of the agent through dev and two production stages with Kargo.

## What's here

| Path | What it is |
|---|---|
| `agent/` | **The agent bundle.** Everything that defines what the agent does: `agent.yaml` (model, effort, limits), `system-prompt.md`, `tools.yaml`, `policy.yaml` (the OpenShell sandbox policy), and `evals.yaml` |
| `harness/` | The harness image: a generic Claude tool-use loop, configured entirely by the bundle |
| `demo/` | For maintainers: every agent version, and `demo/apply.sh`, which rebuilds the commit history from them |

## How a change ships

- **A change under `agent/`** (prompt, model, tools, policy, evals): push it to
  `main`. Kargo's Warehouse discovers the commit as a new bundle version. No
  image build is needed.
- **A change to the harness code**: publish a GitHub release. The release
  workflow builds `ghcr.io/<owner>/support-agent-demo:<version>`, and the
  Warehouse discovers the new image.
  ```sh
  gh release create v0.2.0 --title "v0.2.0" --notes "..."
  ```

Either way, the image and the bundle are promoted together as one release. At
each stage, the agent's policy must fit within that stage's boundary, and its
evals must pass against the live sandbox. The boundaries live in the platform
repo, so widening what the agent may do in a stage is a pull request there, not
here.

## Agent versions

Each commit to `agent/` on `main` is one version of the agent, so `agent/`
shows the latest one and the history holds the rest:

1. Initial support agent
2. Upgrade the support agent to Claude Opus 5.5
3. Streamline the support agent prompt
4. Let the support agent refund damaged deliveries

The [walkthrough](https://github.com/akuity/agent-delivery-demo#walkthrough) in
the platform repo promotes each one and explains what happens.

## For maintainers: recreating the demo history

Readers pick versions from this repo's history, so it must contain exactly the
commits above, in order. `demo/` holds every version, so the history can be
rebuilt from the files alone: `demo/01-initial/` is the complete version 1, and
each later scenario holds only the files that change. To recreate it in a
fresh repo, from a copy of this one without its `.git` directory:

```sh
git init -b main
# Version 1: the first commit holds the whole repo, with version 1 in agent/
demo/apply.sh 01-initial
git remote add origin <repo-url> && git push -u origin main
gh release create v0.1.0 --title "v0.1.0" --notes "Initial harness"

# Versions 2-4: each run commits one change under agent/
demo/apply.sh 02-model-upgrade
demo/apply.sh 03-prompt-regression
demo/apply.sh 04-refunds
git push
```

Keep other changes out of `agent/` afterwards: every commit there is another
agent version.

Then record the commits and the image digest in the platform repo's
`setup/kargo/freight/freight.yaml`, which defines one piece of Freight per
version, in order. From this repo, with the platform repo checked out next to
it (needs `yq` v4):

```sh
f=../agent-delivery-demo/setup/kargo/freight/freight.yaml
digest=$(docker buildx imagetools inspect ghcr.io/akuity/support-agent-demo:0.1.0 \
  --format '{{json .Manifest.Digest}}' | tr -d '"')
i=0
for sha in $(git log --reverse --format=%H -- agent/); do
  I=$i SHA=$sha DIGEST=$digest yq -i '
    (select(document_index == env(I)) | .commits[0].id) = strenv(SHA) |
    (select(document_index == env(I)) | .images[0].digest) = strenv(DIGEST)' "$f"
  i=$((i + 1))
done
```

Commit and push that file in the platform repo.
