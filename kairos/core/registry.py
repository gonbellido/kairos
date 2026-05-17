from collections.abc import Callable


class Registry:
    _profiles: dict[str, type] = {}
    _agents: dict[str, type] = {}
    _plugins: dict[str, type] = {}
    _scorers: dict[str, Callable] = {}

    @classmethod
    def register_profile(cls, key: str, cls_type: type) -> None:
        cls._profiles[key] = cls_type

    @classmethod
    def get_profile(cls, key: str) -> type | None:
        return cls._profiles.get(key)

    @classmethod
    def register_agent(cls, key: str, cls_type: type) -> None:
        cls._agents[key] = cls_type

    @classmethod
    def register_plugin(cls, key: str, cls_type: type) -> None:
        cls._plugins[key] = cls_type

    @classmethod
    def register_scorer(cls, name: str, fn: Callable) -> None:
        cls._scorers[name] = fn

    @classmethod
    def list_profiles(cls) -> list[str]:
        return list(cls._profiles.keys())

    @classmethod
    def list_agents(cls) -> list[str]:
        return list(cls._agents.keys())
