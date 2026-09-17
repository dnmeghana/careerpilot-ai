"""Company Adapter Registry."""

from typing import Dict, List, Optional
from .base import BaseCompanyAdapter


class CompanyAdapterRegistry:
    """Registry maintaining available company portal adapters."""

    def __init__(self) -> None:
        self._adapters: Dict[str, BaseCompanyAdapter] = {}
        self._generic_adapter: Optional[BaseCompanyAdapter] = None

    def register(self, adapter: BaseCompanyAdapter, is_generic: bool = False) -> None:
        """Register a new company adapter."""
        self._adapters[adapter.company_name.lower()] = adapter
        if is_generic:
            self._generic_adapter = adapter

    def get_adapter_by_name(self, name: str) -> Optional[BaseCompanyAdapter]:
        """Look up adapter by company name."""
        return self._adapters.get(name.lower())

    def get_adapter_for_url(self, url: str) -> BaseCompanyAdapter:
        """Find the matching adapter for a URL, falling back to GenericCompanyAdapter."""
        for adapter in self._adapters.values():
            if adapter is not self._generic_adapter and adapter.can_handle_url(url):
                return adapter

        if self._generic_adapter:
            return self._generic_adapter

        # Fallback to first registered adapter if generic not explicitly flagged
        if self._adapters:
            return next(iter(self._adapters.values()))

        raise RuntimeError("No company adapters registered in CompanyAdapterRegistry.")

    def list_adapters(self) -> List[dict[str, str]]:
        """List summary of all registered adapters."""
        return [
            {
                "company_name": a.company_name,
                "is_generic": a is self._generic_adapter,
            }
            for a in self._adapters.values()
        ]


_REGISTRY_INSTANCE: Optional[CompanyAdapterRegistry] = None


def get_adapter_registry() -> CompanyAdapterRegistry:
    """Return the global company adapter registry singleton."""
    global _REGISTRY_INSTANCE
    if _REGISTRY_INSTANCE is None:
        from .generic_adapter import GenericCompanyAdapter
        from .mock_adapter import MockCompanyAdapter
        from .naukri_adapter import NaukriCompanyAdapter

        reg = CompanyAdapterRegistry()
        generic = GenericCompanyAdapter()
        mock = MockCompanyAdapter()
        naukri = NaukriCompanyAdapter()
        reg.register(generic, is_generic=True)
        reg.register(mock, is_generic=False)
        reg.register(naukri, is_generic=False)
        _REGISTRY_INSTANCE = reg
    return _REGISTRY_INSTANCE

