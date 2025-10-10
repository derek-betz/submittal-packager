"""Indiana Design Manual stage requirements dataset."""

from __future__ import annotations

from copy import deepcopy
from typing import Dict, List, Optional, TypedDict


class ArtifactDefinition(TypedDict, total=False):
    """A required or optional artifact definition."""

    key: str
    pattern: str
    description: str


class StageDefaults(TypedDict, total=False):
    """Curated defaults for a particular IDM stage."""

    name: str
    description: str
    required: List[ArtifactDefinition]
    optional: List[ArtifactDefinition]
    discipline_codes: List[str]
    forms: List[str]
    keywords_required: List[str]
    keywords_optional: List[str]


_IDM_STAGE_DEFAULTS: Dict[str, StageDefaults] = {
    "Stage1": {
        "name": "Stage 1 - Preliminary Field Check",
        "description": (
            "Early plan development package used for the preliminary field check "
            "review. The emphasis is on corridor definition, typical sections, "
            "and preliminary quantities so reviewers can identify major scope issues."
        ),
        "required": [
            {
                "key": "title_sheet",
                "pattern": "*TITLE*.pdf",
                "description": "Title sheet with designation, route, project limits, and PE seal block.",
            },
            {
                "key": "index_sheet",
                "pattern": "*INDEX*.pdf",
                "description": "Plan index identifying drawing sequence and sheet totals.",
            },
            {
                "key": "typical_sections",
                "pattern": "*TYP*.pdf",
                "description": "Typical section sheets covering each roadway segment.",
            },
            {
                "key": "plan_and_profile",
                "pattern": "*PLAN*PROFILE*.pdf",
                "description": "Combined plan and profile depicting horizontal and vertical control.",
            },
            {
                "key": "preliminary_quantities",
                "pattern": "*QTY*.pdf",
                "description": "Summary of preliminary quantities with pay item numbers.",
            },
        ],
        "optional": [
            {
                "key": "structure_concepts",
                "pattern": "*STRUCT*.pdf",
                "description": "Structure layout sheets or bridge concept report attachments.",
            },
            {
                "key": "traffic_memorandum",
                "pattern": "*TRAFFIC*.pdf",
                "description": "Supporting traffic engineering memorandum or capacity worksheets.",
            },
        ],
        "discipline_codes": ["GN", "TS", "PL", "RD", "TMP", "BR"],
        "forms": [
            "Form IC-701 Preliminary Field Check Transmittal",
            "Form IC-730 Stage 1 Quantities Checklist",
        ],
        "keywords_required": ["STAGE 1", "PRELIMINARY", "FIELD CHECK"],
        "keywords_optional": ["PFC", "CONCEPT"],
    },
    "Stage2": {
        "name": "Stage 2 - Design Development",
        "description": (
            "Approximately 60 percent design deliverable used for design "
            "development and coordination with specialty groups. Cross sections, "
            "traffic control, drainage, and quantity refinements are expected."
        ),
        "required": [
            {
                "key": "title_sheet",
                "pattern": "*TITLE*.pdf",
                "description": "Title sheet updated with design development revision block.",
            },
            {
                "key": "index_sheet",
                "pattern": "*INDEX*.pdf",
                "description": "Updated plan index reflecting added sheet series.",
            },
            {
                "key": "plan_and_profile",
                "pattern": "*PLAN*PROFILE*.pdf",
                "description": "Plan and profile sheets with design speeds, superelevation, and references.",
            },
            {
                "key": "cross_sections",
                "pattern": "*XS*.pdf",
                "description": "Cross section sheets covering the entire project limits.",
            },
            {
                "key": "traffic_control",
                "pattern": "*MOT*.pdf",
                "description": "Maintenance of traffic / traffic control plan set.",
            },
            {
                "key": "drainage_design",
                "pattern": "*DRAIN*.pdf",
                "description": "Drainage layout, structure sizing summaries, and hydraulics computations.",
            },
            {
                "key": "quantity_summary",
                "pattern": "*QTY*.pdf",
                "description": "Updated quantity summary and cost estimate.",
            },
        ],
        "optional": [
            {
                "key": "lighting_signing",
                "pattern": "*(SIGN|LIGHT)*.pdf",
                "description": "Signing and lighting layouts if applicable.",
            },
            {
                "key": "environmental_commitments",
                "pattern": "*ENV*.pdf",
                "description": "Environmental commitments status report.",
            },
        ],
        "discipline_codes": ["GN", "TS", "RD", "XS", "TMP", "DR", "SG", "LT"],
        "forms": [
            "Form IC-702 Stage 2 Transmittal",
            "Form IC-733 Stage 2 Design Development Checklist",
        ],
        "keywords_required": ["STAGE 2", "DESIGN DEVELOPMENT"],
        "keywords_optional": ["60%", "DESIGN REVIEW"],
    },
    "Stage3": {
        "name": "Stage 3 - Final Check Plans",
        "description": (
            "Ninety percent design package used for the final check review. All "
            "plan components, quantities, and special provisions should be close to "
            "final form with QA/QC completed."
        ),
        "required": [
            {
                "key": "title_sheet",
                "pattern": "*TITLE*.pdf",
                "description": "Title sheet with final check signature and revision history.",
            },
            {
                "key": "index_sheet",
                "pattern": "*INDEX*.pdf",
                "description": "Complete plan index cross-referencing sheet numbering.",
            },
            {
                "key": "plan_and_profile",
                "pattern": "*PLAN*PROFILE*.pdf",
                "description": "Plan and profile sheets incorporating final horizontal and vertical control.",
            },
            {
                "key": "cross_sections",
                "pattern": "*XS*.pdf",
                "description": "Cross sections annotated with earthwork quantities and slope limits.",
            },
            {
                "key": "traffic_control",
                "pattern": "*MOT*.pdf",
                "description": "Maintenance of traffic / traffic control plans including detours.",
            },
            {
                "key": "signing_and_marking",
                "pattern": "*(SIGN|MARKING)*.pdf",
                "description": "Signing and pavement marking sheets.",
            },
            {
                "key": "special_provisions",
                "pattern": "*SP*.pdf",
                "description": "Draft special provisions and unique project requirements.",
            },
            {
                "key": "final_quantities",
                "pattern": "*QTY*.pdf",
                "description": "Final quantity book and cost estimate.",
            },
        ],
        "optional": [
            {
                "key": "utility_coordination",
                "pattern": "*UTILITY*.pdf",
                "description": "Utility coordination status, agreements, and conflict matrix.",
            },
            {
                "key": "right_of_way",
                "pattern": "*ROW*.pdf",
                "description": "Right-of-way plans or parcel status summary.",
            },
        ],
        "discipline_codes": ["GN", "RD", "XS", "TMP", "SG", "MK", "UT", "RW"],
        "forms": [
            "Form IC-703 Stage 3 Transmittal",
            "Form IC-735 Final Check QA Checklist",
        ],
        "keywords_required": ["STAGE 3", "FINAL CHECK"],
        "keywords_optional": ["90%", "QC REVIEW"],
    },
    "Final": {
        "name": "Final Tracings / RFC",
        "description": (
            "Release for construction deliverable. Includes sealed plans, final "
            "quantities, specifications, and supporting forms needed for contract "
            "letting."
        ),
        "required": [
            {
                "key": "title_sheet",
                "pattern": "*TITLE*.pdf",
                "description": "Sealed title sheet with signatures and INDOT approval block.",
            },
            {
                "key": "index_sheet",
                "pattern": "*INDEX*.pdf",
                "description": "Index of final tracing sheets with revision references.",
            },
            {
                "key": "plan_set",
                "pattern": "*.pdf",
                "description": "Complete sealed plan set including all discipline sheet series.",
            },
            {
                "key": "as_readied_specifications",
                "pattern": "*SPEC*.pdf",
                "description": "Approved special provisions and unique project specifications.",
            },
            {
                "key": "final_quantities",
                "pattern": "*QTY*.pdf",
                "description": "Engineer\'s estimate and final quantities recap.",
            },
            {
                "key": "affidavit_of_approval",
                "pattern": "*AFFIDAVIT*.pdf",
                "description": "Affidavit of final plan approval and professional engineer certification.",
            },
        ],
        "optional": [
            {
                "key": "contract_documents",
                "pattern": "*CONTRACT*.pdf",
                "description": "Contract book excerpts for letting coordination.",
            },
            {
                "key": "as_built_supplements",
                "pattern": "*ASBUILT*.pdf",
                "description": "Known as-built constraints or supplemental survey data.",
            },
        ],
        "discipline_codes": ["GN", "RD", "XS", "TMP", "SG", "MK", "DR", "UT", "RW", "EL"],
        "forms": [
            "Form IC-704 Final Tracings Transmittal",
            "Form IC-736 RFC Certification",
            "Form IC-762 Design Approval Checklist",
        ],
        "keywords_required": ["FINAL", "RFC", "RELEASE FOR CONSTRUCTION"],
        "keywords_optional": ["SEALED", "ISSUED FOR CONSTRUCTION"],
    },
}


def available_stage_presets() -> List[str]:
    """Return the ordered list of supported IDM stage presets."""

    return list(_IDM_STAGE_DEFAULTS.keys())


def get_stage_defaults(stage: str) -> Optional[StageDefaults]:
    """Return a deep copy of the defaults for the requested stage."""

    defaults = _IDM_STAGE_DEFAULTS.get(stage)
    if defaults is None:
        return None
    return deepcopy(defaults)


__all__ = ["ArtifactDefinition", "StageDefaults", "available_stage_presets", "get_stage_defaults"]
