from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderAdapter:
    id: str
    label: str
    prompt_filename: str
    supported: bool
    requires_reference_image: bool


DEFAULT_PROVIDER = "universal"
RUNWAY_PROVIDER = "runway.gen4_image_refs"
GROK_PROVIDER = "grok.imagine"

PROVIDER_REGISTRY = {
    DEFAULT_PROVIDER: ProviderAdapter(
        id=DEFAULT_PROVIDER,
        label="Universal",
        prompt_filename="prompts/shot_prompts.md",
        supported=True,
        requires_reference_image=False,
    ),
    RUNWAY_PROVIDER: ProviderAdapter(
        id=RUNWAY_PROVIDER,
        label="Runway Gen-4 References",
        prompt_filename="prompts/runway.gen4_image_refs_prompts.md",
        supported=True,
        requires_reference_image=True,
    ),
    GROK_PROVIDER: ProviderAdapter(
        id=GROK_PROVIDER,
        label="Grok Imagine",
        prompt_filename="prompts/grok.imagine_prompts.md",
        supported=True,
        requires_reference_image=True,
    ),
}

SUPPORTED_PROVIDERS = tuple(
    provider.id for provider in PROVIDER_REGISTRY.values() if provider.supported
)


def get_provider(provider_id: str) -> ProviderAdapter:
    provider = PROVIDER_REGISTRY.get(provider_id)
    if provider is None or not provider.supported:
        supported = ", ".join(SUPPORTED_PROVIDERS)
        raise ValueError(f"Unsupported provider: {provider_id}. Supported providers: {supported}")
    return provider


def optional_provider_ids() -> list[str]:
    return [provider_id for provider_id in SUPPORTED_PROVIDERS if provider_id != DEFAULT_PROVIDER]


def optional_provider_adapters() -> list[ProviderAdapter]:
    return [PROVIDER_REGISTRY[provider_id] for provider_id in optional_provider_ids()]
