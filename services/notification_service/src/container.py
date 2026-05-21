"""Dependency injection container for notification-service."""

from typing import Any, Callable, Dict, Optional


class ServiceContainer:
    """Small DI container for event consumers and notification channels."""

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

    def register_instance(self, name: str, instance: Any) -> None:
        self._instances[name] = instance

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


_container: Optional[ServiceContainer] = None


def init_container(container: ServiceContainer) -> None:
    global _container
    _container = container


def get_container() -> ServiceContainer:
    global _container
    if _container is None:
        _container = ServiceContainer()
    return _container
