#!/usr/bin/env python3
import asyncio
import yaml
from pathlib import Path
from kairos.db.session import create_session_factory
from kairos.db.models import Base, ProfileModel


async def seed(profiles_dir: str = "./profiles") -> None:
    sf = create_session_factory()
    async with sf() as session:
        async with session.begin():
            for yaml_file in Path(profiles_dir).glob("*/profile.yaml"):
                pid = yaml_file.parent.name
                with open(yaml_file) as f:
                    data = yaml.safe_load(f)
                existing = await session.get(ProfileModel, pid)
                if existing:
                    print(f"Skip {pid}: exists")
                    continue
                m = ProfileModel(id=pid, name=data["name"],
                                 description=data.get("description", ""),
                                 version=data.get("version", "0.1.0"),
                                 active=data.get("active", True),
                                 system_prompt_template=data.get("system_prompt_template", ""),
                                 default_impronta=data.get("default_impronta", {}),
                                 tags=data.get("tags", []),
                                 plugins=data.get("plugins", []))
                session.add(m)
                print(f"Seeded: {pid}")


if __name__ == "__main__":
    asyncio.run(seed())
