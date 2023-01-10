import datetime
import os
from dataclasses import dataclass, field

from vunnel import provider, result, schema
from vunnel.providers.nvd.manager import Manager


@dataclass
class Config:
    runtime: provider.RuntimeConfig = field(
        default_factory=lambda: provider.RuntimeConfig(
            result_store=result.StoreStrategy.SQLITE,
            existing_results=provider.ResultStatePolicy.DELETE_BEFORE_WRITE,
        )
    )
    request_timeout: int = 125
    start_year: int = 2002
    end_year: int | None = None
    api_key: str = "env:NVD_API_KEY"

    def __post_init__(self) -> None:
        if self.api_key.startswith("env:"):
            self.api_key = os.environ.get(self.api_key[4:], "")

    def __str__(self) -> str:
        # sanitize secrets from any output
        api_value = self.api_key
        str_value = super().__str__()
        if not api_value:
            return str_value
        return str_value.replace(api_value, "********")


class Provider(provider.Provider):
    def __init__(self, root: str, config: Config) -> None:
        super().__init__(root, runtime_cfg=config.runtime)
        self.config = config

        self.logger.debug(f"config: {config}")

        self.schema = schema.NVDSchema()
        self.manager = Manager(
            workspace=self.workspace,
            download_timeout=self.config.request_timeout,
            start_year=self.config.start_year,
            end_year=self.config.end_year,
            api_key=self.config.api_key,
            logger=self.logger,
        )

    @classmethod
    def name(cls) -> str:
        return "nvd"

    def update(self, last_updated: datetime.datetime | None) -> tuple[list[str], int]:
        with self.results_writer() as writer:
            for identifier, record in self.manager.get(
                skip_if_exists=self.config.runtime.skip_if_exists, last_updated=last_updated
            ):
                writer.write(
                    identifier=identifier.lower(),
                    schema=self.schema,
                    payload=record,
                )

        return self.manager.urls, len(writer)
