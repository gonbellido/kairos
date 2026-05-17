import yaml
from pathlib import Path

from kairos.core.profile import Profile
from kairos.core.impronta import Impronta, ImprontaConstraints
from kairos.core.exceptions import ProfileNotFoundError


class ProfileEngine:
    def __init__(self, profiles_dir: str = "./profiles"):
        self._dir = Path(profiles_dir)
        self._cache: dict[str, Profile] = {}

    async def get_profile(self, profile_id: str) -> Profile:
        if profile_id in self._cache:
            return self._cache[profile_id]

        path = self._dir / profile_id / "profile.yaml"
        if not path.exists():
            raise ProfileNotFoundError(profile_id)

        with open(path) as f:
            data = yaml.safe_load(f)

        impronta = Impronta(**data.pop("default_impronta", {}))

        constraints_raw = data.pop("impronta_constraints", None)
        constraints = None
        if constraints_raw:
            constraints = ImprontaConstraints(
                min=Impronta(**constraints_raw.get("min", {})),
                max=Impronta(**constraints_raw.get("max", {})),
            )

        profile = Profile(id=profile_id, default_impronta=impronta, impronta_constraints=constraints, **data)
        self._cache[profile_id] = profile
        return profile

    async def resolve_impronta(self, profile_id: str, overrides: dict | None = None) -> Impronta:
        profile = await self.get_profile(profile_id)
        impronta = profile.default_impronta
        if overrides:
            impronta = impronta.update(overrides)
        if profile.impronta_constraints:
            impronta = profile.impronta_constraints.clamp(impronta)
        return impronta
