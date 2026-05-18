# Service container for dependency injection

from typing import Any, Dict, Callable, Optional
import logging

logger = logging.getLogger(__name__)


class ServiceContainer:
    """Simple service container for dependency injection
    
    Allows registering services/dependencies and resolving them throughout
    the application without tight coupling.
    
    Example:
        >>> container = ServiceContainer()
        >>> container.register("database", lambda: MongoDatabase())
        >>> container.register("logger", get_logger)
        >>> 
        >>> db = container.resolve("database")
        >>> log = container.resolve("logger")("my_module")
    """
    
    def __init__(self):
        """Initialize empty service container"""
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
        self._singletons: Dict[str, Any] = {}
    
    def register(
        self,
        name: str,
        factory: Callable,
        singleton: bool = True
    ) -> None:
        """Register a service factory
        
        Args:
            name: Service name for resolution
            factory: Callable that creates the service
            singleton: If True, service is created once and reused
        
        Example:
            >>> container.register("db", create_database, singleton=True)
            >>> container.register("logger", get_logger, singleton=False)
        """
        self._factories[name] = factory
        
        if singleton:
            logger.debug(f"Registered singleton service: {name}")
        else:
            logger.debug(f"Registered transient service: {name}")
    
    def register_instance(self, name: str, instance: Any) -> None:
        """Register a pre-created instance
        
        Args:
            name: Service name for resolution
            instance: Pre-created service instance
        
        Example:
            >>> config = Config()
            >>> container.register_instance("config", config)
        """
        self._services[name] = instance
        logger.debug(f"Registered instance service: {name}")
    
    def resolve(self, name: str) -> Any:
        """Resolve a service by name
        
        Args:
            name: Service name to resolve
        
        Returns:
            Service instance
        
        Raises:
            ValueError: If service not registered
        
        Example:
            >>> db = container.resolve("database")
            >>> logger = container.resolve("logger")
        """
        
        # Check if pre-created instance exists
        if name in self._services:
            return self._services[name]
        
        # Check if factory exists
        if name not in self._factories:
            raise ValueError(f"Service not registered: {name}")
        
        factory = self._factories[name]
        
        # Check if should be singleton
        if name in self._singletons:
            return self._singletons[name]
        
        # Create instance
        try:
            instance = factory()
        except TypeError:
            # Factory might need arguments from Flask context
            instance = factory()
        
        # Store singleton if configured
        if name in self._factories and hasattr(factory, "__singleton__"):
            self._singletons[name] = instance
        
        return instance
    
    def has_service(self, name: str) -> bool:
        """Check if service is registered
        
        Args:
            name: Service name
        
        Returns:
            True if service is registered
        """
        return name in self._services or name in self._factories
    
    def clear(self) -> None:
        """Clear all registered services
        
        Useful for testing
        """
        self._services.clear()
        self._factories.clear()
        self._singletons.clear()
        logger.debug("Service container cleared")


# Global container instance
_container: Optional[ServiceContainer] = None


def get_container() -> ServiceContainer:
    """Get global service container
    
    Returns:
        Global ServiceContainer instance
    
    Example:
        >>> container = get_container()
        >>> db = container.resolve("database")
    """
    global _container
    if _container is None:
        _container = ServiceContainer()
    return _container


def init_container(container: ServiceContainer) -> None:
    """Set global service container
    
    Args:
        container: ServiceContainer instance to use globally
    
    Example:
        >>> container = ServiceContainer()
        >>> container.register("db", create_db)
        >>> init_container(container)
    """
    global _container
    _container = container
