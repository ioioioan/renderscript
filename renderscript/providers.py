from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionTemplate:
    id: str
    label: str
    prompt_filename: str
    supported: bool
    requires_reference_image: bool


ProviderAdapter = ExecutionTemplate
DEFAULT_PROVIDER = "universal"
RUNWAY_PROVIDER = "runway.gen4_image_refs"
GROK_PROVIDER = "grok.imagine"

EXECUTION_TEMPLATE_REGISTRY = {
    DEFAULT_PROVIDER: ExecutionTemplate(
        id=DEFAULT_PROVIDER,
        label="Universal",
        prompt_filename="DEVELOPER_FILES/prompt_packs/shot_prompts.md",
        supported=True,
        requires_reference_image=False,
    ),
    RUNWAY_PROVIDER: ExecutionTemplate(
        id=RUNWAY_PROVIDER,
        label="Runway Gen-4 References",
        prompt_filename="DEVELOPER_FILES/prompt_packs/runway.gen4_image_refs_prompts.md",
        supported=True,
        requires_reference_image=True,
    ),
    GROK_PROVIDER: ExecutionTemplate(
        id=GROK_PROVIDER,
        label="Grok Imagine",
        prompt_filename="DEVELOPER_FILES/prompt_packs/grok.imagine_prompts.md",
        supported=True,
        requires_reference_image=True,
    ),
}

PROVIDER_REGISTRY = EXECUTION_TEMPLATE_REGISTRY
SUPPORTED_PROVIDERS = tuple(
    template.id for template in EXECUTION_TEMPLATE_REGISTRY.values() if template.supported
)
SUPPORTED_EXECUTION_TEMPLATES = SUPPORTED_PROVIDERS


def get_execution_template(template_id: str) -> ExecutionTemplate:
    template = EXECUTION_TEMPLATE_REGISTRY.get(template_id)
    if template is None or not template.supported:
        supported = ", ".join(SUPPORTED_PROVIDERS)
        raise ValueError(f"Unsupported execution template: {template_id}. Supported templates: {supported}")
    return template


def get_provider(provider_id: str) -> ExecutionTemplate:
    try:
        return get_execution_template(provider_id)
    except ValueError as exc:
        supported = ", ".join(SUPPORTED_PROVIDERS)
        raise ValueError(f"Unsupported provider: {provider_id}. Supported providers: {supported}") from exc


def optional_execution_template_ids() -> list[str]:
    return [template_id for template_id in SUPPORTED_EXECUTION_TEMPLATES if template_id != DEFAULT_PROVIDER]


def optional_provider_ids() -> list[str]:
    return optional_execution_template_ids()


def optional_execution_templates() -> list[ExecutionTemplate]:
    return [EXECUTION_TEMPLATE_REGISTRY[template_id] for template_id in optional_execution_template_ids()]


def optional_provider_adapters() -> list[ExecutionTemplate]:
    return optional_execution_templates()
