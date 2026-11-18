"""Fonte validada e ordenação determinística para diagramas técnicos."""
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

NodeId = Annotated[str, StringConstraints(pattern=r'^[A-Za-z][A-Za-z0-9_-]{0,23}$')]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=42)]


class DiagramNode(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: NodeId
    label: Label
    group: Label | None = None


class DiagramEdge(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source: NodeId
    target: NodeId
    label: Label | None = None


def diagram_columns(nodes, edges):
    remaining = {node.id: node for node in nodes}
    columns = []
    while remaining:
        blocked = {edge.target for edge in edges if edge.source in remaining}
        column = [node for key, node in remaining.items() if key not in blocked]
        if not column:
            raise ValueError('O diagrama deve ter um fluxo sem ciclos.')
        if len(column) > 4 or len(columns) >= 4:
            raise ValueError('Use até quatro colunas e quatro nós por coluna.')
        columns.append(column)
        for node in column:
            del remaining[node.id]
    return columns


class Diagram(BaseModel):
    model_config = ConfigDict(extra='forbid')
    nodes: list[DiagramNode] = Field(min_length=1, max_length=12)
    edges: list[DiagramEdge] = Field(default_factory=list, max_length=16)

    @model_validator(mode='after')
    def validate_graph(self):
        ids = {node.id for node in self.nodes}
        links = {(edge.source, edge.target) for edge in self.edges}
        if len(ids) != len(self.nodes) or len(links) != len(self.edges):
            raise ValueError('IDs e conexões do diagrama devem ser únicos.')
        if any(source not in ids or target not in ids for source, target in links):
            raise ValueError('As conexões devem usar IDs de nós do diagrama.')
        diagram_columns(self.nodes, self.edges)
        return self
