from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass
class Factor:
    type: str
    code: str
    name: str
    description: str = ""


@dataclass
class ScaleItem:
    linguistic: str
    code: str
    value: Any


@dataclass
class Expert:
    name: str
    username: str
    password: str
    respondent_id: str = ""
    organization: str = ""


@dataclass
class ProjectConfig:
    model_type: str = "DEMATEL"
    use_z_number: bool = False
    scale_type: str = "Category"
    continuous_min: float = 0.0
    continuous_max: float = 10.0
    expert_auth_mode: str = "Account"
    excel_path: str = ""
    factors: List[Factor] = field(default_factory=list)
    alternatives: List[Factor] = field(default_factory=list)
    standard_scales: List[ScaleItem] = field(default_factory=list)
    z_scales_a: List[ScaleItem] = field(default_factory=list)
    z_scales_b: List[ScaleItem] = field(default_factory=list)
    experts: List[Expert] = field(default_factory=list)


def config_to_dict(config: ProjectConfig) -> Dict[str, Any]:
    """Convert config to JSON-serializable data for immutable project storage."""
    data = asdict(config)
    # The source Excel path is useful during creation but is not part of the
    # project's identity. Keep it out of persisted configuration so projects
    # created from the same template at different paths can still be merged.
    data.pop("excel_path", None)
    return data


def _factor_from_dict(data: Dict[str, Any]) -> Factor:
    return Factor(
        type=str(data.get("type", "Factor")),
        code=str(data.get("code", "")),
        name=str(data.get("name", "")),
        description=str(data.get("description", "")),
    )


def _scale_from_dict(data: Dict[str, Any]) -> ScaleItem:
    return ScaleItem(
        linguistic=str(data.get("linguistic", "")),
        code=str(data.get("code", "")),
        value=data.get("value", ""),
    )


def _expert_from_dict(data: Dict[str, Any]) -> Expert:
    return Expert(
        name=str(data.get("name", "")),
        username=str(data.get("username", "")),
        password=str(data.get("password", "")),
        respondent_id=str(data.get("respondent_id", "")),
        organization=str(data.get("organization", "")),
    )


def config_from_dict(data: Dict[str, Any]) -> ProjectConfig:
    """Rebuild a ProjectConfig from project_db.config_json."""
    return ProjectConfig(
        model_type=str(data.get("model_type", "DEMATEL")),
        use_z_number=bool(data.get("use_z_number", False)),
        scale_type=str(data.get("scale_type", "Category")),
        continuous_min=float(data.get("continuous_min", 0.0)),
        continuous_max=float(data.get("continuous_max", 10.0)),
        expert_auth_mode=str(data.get("expert_auth_mode", "Account")),
        factors=[_factor_from_dict(x) for x in data.get("factors", [])],
        alternatives=[_factor_from_dict(x) for x in data.get("alternatives", [])],
        standard_scales=[_scale_from_dict(x) for x in data.get("standard_scales", [])],
        z_scales_a=[_scale_from_dict(x) for x in data.get("z_scales_a", [])],
        z_scales_b=[_scale_from_dict(x) for x in data.get("z_scales_b", [])],
        experts=[_expert_from_dict(x) for x in data.get("experts", [])],
    )
