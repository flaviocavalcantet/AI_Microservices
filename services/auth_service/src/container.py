"""Dependency injection container for auth-service."""

from typing import Any, Callable, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class ServiceContainer:
    """Small DI container used to wire auth components at the app boundary."""

    def __init__(self):
        self._instances: Dict[str, Any] = {}
        self._factories: Dict[str, Callable[[], Any]] = {}
        self._singletons: Dict[str, Any] = {}
        self._singleton_services: set[str] = set()

    def register(self, name: str, factory: Callable[[], Any], singleton: bool = True) -> None:
        self._factories[name] = factory
        if singleton:
            self._singleton_services.add(name)
        else:
            self._singleton_services.discard(name)
        logger.debug("Registered service factory: %s", name)

    def register_instance(self, name: str, instance: Any) -> None:
        self._instances[name] = instance
        logger.debug("Registered service instance: %s", name)

    def resolve(self, name: str) -> Any:
        if name in self._instances:
            return self._instances[name]
        if name in self._singletons:
            return self._singletons[name]
        if name not in self._factories:
            raise ValueError(f"Service not registered: {name}")

        instance = self._factories[name]()
        if name in self._singleton_services:
            self._singletons[name] = instance
        return instance

    def has_service(self, name: str) -> bool:
        return name in self._instances or name in self._factories

    def clear(self) -> None:
        self._instances.clear()
        self._factories.clear()
        self._singletons.clear()
        self._singleton_services.clear()


_container: Optional[ServiceContainer] = None


def init_container(container: ServiceContainer) -> None:
    global _container
    _container = container


def get_container() -> ServiceContainer:
    global _container
    if _container is None:
        _container = ServiceContainer()
    return _container


def resolve_from_context(service_name: str) -> Any:
    return get_container().resolve(service_name)
