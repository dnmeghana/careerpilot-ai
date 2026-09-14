"""Company adapters and adapter registry for CareerPilot V2."""
from .base import BaseCompanyAdapter, DiscoveredJob, FormFieldDescriptor, StepResult
from .registry import CompanyAdapterRegistry, get_adapter_registry
from .generic_adapter import GenericCompanyAdapter
from .mock_adapter import MockCompanyAdapter

__all__ = [
    "BaseCompanyAdapter",
    "DiscoveredJob",
    "FormFieldDescriptor",
    "StepResult",
    "CompanyAdapterRegistry",
    "get_adapter_registry",
    "GenericCompanyAdapter",
    "MockCompanyAdapter",
]

