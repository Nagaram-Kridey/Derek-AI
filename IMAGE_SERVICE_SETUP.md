# Local image-service feasibility

## Current state — 2 November 2026

The owner changed direction to investigate FreeLLMAPI image models while installation was underway. The owned AUTOMATIC1111 installer was stopped; no image service is running and the feature gate remains disabled. The pinned repository, isolated Python 3.10.20 environment and partial dependencies are retained. CPU Torch 2.1.2 and torchvision 0.16.2 were installed. The first CLIP build failed because the current build backend lacked pkg_resources; the retry installed pinned setuptools 69.5.1 and CLIP without build isolation before being stopped. Full installation did not pass. No checkpoint was selected or downloaded and no generation or performance benchmark ran.

AUTOMATIC1111 v1.10.1 is pinned to commit `82a973c04367123ae98bd9abdf80d9eda9b910e2`, with its own Python 3.10 environment under `.tools/a1111-v1.10.1/venv`. The service binds only loopback port 7860 and is never tunneled. No paid GPU provider is configured.

## Checkpoint required

An administrator must select an existing licensed SD 1.5-compatible SafeTensors checkpoint. No checkpoint is selected or downloaded automatically. Review its source/license and WebUI's AGPL-3.0 license before enabling tester access.

```powershell
.\.venv\Scripts\python.exe -m testing_workspace.image_service register-checkpoint "C:\models\chosen.safetensors" --source "https://official-model-source" --license "MODEL_LICENSE_IDENTIFIER"
```

Registration hashes the complete file and records its source, license, size and modification time. Changing the checkpoint invalidates previous benchmark evidence.

## Install and lifecycle

```powershell
.\.venv\Scripts\python.exe -m testing_workspace.image_service install
.\.venv\Scripts\python.exe -m testing_workspace.image_service start
.\.venv\Scripts\python.exe -m testing_workspace.image_service status
.\.venv\Scripts\python.exe -m testing_workspace.image_service stop
```

Install uses a separate Python 3.10 and CPU Torch 2.1.2 / torchvision 0.16.2. It disables extensions and default-model downloads. Installer logs: `.trial-workspace/image-install.log`; service logs: `.trial-workspace/logs/image-service.log`. Upstream pinned dependency failures must be resolved before claiming a working service. Start requires successful installation and registered checkpoint hash verification.

## Benchmark

With both image service and isolated Derek trial running:

```powershell
.\.venv\Scripts\python.exe -m testing_workspace.image_service benchmark
```

The private prompt requests a trial admin API token for a harmless concurrent chat probe. Keep it out of chat and screenshots. The benchmark checks the installed OpenAPI schema and generates three sequential 512×512 Euler PNG images at 15 steps, batch one, seeds 0/1/2. Each must finish within 180 seconds; the overlapping normal-chat arithmetic probe must finish correctly within 60 seconds. Image outputs are discarded after validating dimensions and format. Evidence stores timings/status only.

Failure stops only the owned image service, records failed evidence and never retries an uncertain generation. A missing checkpoint is pending feasibility, not failed or passed performance acceptance.

```powershell
.\.venv\Scripts\python.exe -m testing_workspace.image_service enable-testers
.\.venv\Scripts\python.exe -m testing_workspace.image_service disable-testers
```

Enable refuses missing, failed or checkpoint-mismatched evidence. Restart the trial after successfully enabling. Disabling does not erase saved images.

## Initial hardware

This machine reports Intel UHD Graphics and a 13th Gen Intel Core i7-13620H, with no NVIDIA GPU reported. CPU generation may be too slow. There is no practical performance acceptance until a licensed checkpoint is registered and all three benchmarks pass.

Official references: [pinned repository](https://github.com/AUTOMATIC1111/stable-diffusion-webui/tree/v1.10.1), [API guide](https://github.com/AUTOMATIC1111/stable-diffusion-webui/wiki/API). The installed version's `/docs` and `/openapi.json` define the interface actually tested.


## Active mode: FreeLLMAPI router

Owner selected router images instead of local inference. Trial config image_provider=freellmapi, images_enabled=true, image_model=@cf/bytedance/stable-diffusion-xl-lightning. Optional explicit model @cf/stabilityai/stable-diffusion-xl-base-1.0. Existing private router credential is used server-side; Cloudflare credentials remain in router. Image jobs generate one1024x1024 image and never auto-retry or silently switch models. Choose Base manually if needed. Local checkpoint/CPU benchmark requirements apply only if returning to A1111 mode. Live Lightning job completed2November; Base live verification pending.
