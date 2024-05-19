from dataclasses import dataclass
from typing import Any


@dataclass
class Resource:
    id: str
    type: str
    comment: str | None


@dataclass
class Index:
    version: str
    resources: dict[str, list[Resource]]

    @staticmethod
    def create(index_json: dict[str, Any]) -> 'Index':
        version: str = index_json['version']
        resources: dict[str, list[Resource]] = {}
        for resdict in index_json['resources']:
            id = resdict['@id']
            type = resdict['@type']
            comment = resdict['comment'] if 'comment' in resdict else None
            resource = Resource(id, type, comment)
            if resource.type not in resources:
                resources[resource.type] = []
            resources[resource.type].append(resource)
        return Index(version, resources)
