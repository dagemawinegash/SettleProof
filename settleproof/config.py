from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    river_key: str
    createos_key: str
    model: str = "zai-org/GLM-5.3-Flash"
    river_base: str = "https://api.river.ai/v1"
    createos_base: str = "https://api-eu.sb.createos.sh"
    database_url: str | None = None

    @classmethod
    def load(cls):
        # Application-only loading; do not print managed environment contents.
        from dotenv import load_dotenv
        load_dotenv(Path.cwd() / '.env', override=False)
        missing = [k for k in ('RIVER_API_KEY','CREATEOS_API_KEY') if not os.getenv(k)]
        if missing:
            raise ValueError('Missing configuration: ' + ', '.join(missing))
        db = os.getenv('DATABASE_URL') or os.getenv('RUN_METADATA_DATABASE_URL')
        if not db:
            # Stripe prefixes credentials with the resource's name.
            candidates = [v for k,v in os.environ.items() if k.startswith('RUN_METADATA_')
                          and (k.endswith('DATABASE_URL') or k.endswith('CONNECTION_STRING'))]
            db = candidates[0] if len(candidates) == 1 else None
        return cls(os.environ['RIVER_API_KEY'], os.environ['CREATEOS_API_KEY'],
                   model=os.getenv('RIVER_MODEL', cls.model), database_url=db)
