"""Recognized outbound integration declarations, independent of call evidence.

Only exact resolved Spring types qualify. Library imports, local variables,
parameters and factory return types are not declarations in this inventory.
Feign's existing discovery and metadata remain unchanged.
"""

from dataclasses import dataclass

from .indexing import SourceIndex, index_module, index_source
from .module import Module


JPA_REPOSITORY = 'org.springframework.data.jpa.repository.JpaRepository'
CLIENT_FIELDS = {
    'org.springframework.jdbc.core.JdbcTemplate': ('Spring JDBC', 'database'),
    'org.springframework.web.client.RestTemplate': ('Spring HTTP', 'HTTP'),
    'org.springframework.web.reactive.function.client.WebClient': (
        'Spring reactive HTTP', 'HTTP'),
}


@dataclass(frozen=True)
class IntegrationDeclaration:
    mechanism: str
    category: str
    declaring_type: str
    source_path: str
    line: int
    field_name: str | None = None
    type_name: str = ''

    @property
    def identity(self) -> tuple[str, str, str | None]:
        """Repository/Feign interfaces are shared; each client field is separate."""
        return self.mechanism, self.declaring_type, self.field_name


def declarations_from_index(index: SourceIndex) -> tuple[IntegrationDeclaration, ...]:
    """Inventory declarations without resolving operations or library source.

    Inspect only direct repository parents and the fields owned by each type:
    inherited parents/fields and client subclasses deliberately do not qualify.
    Repository-typed fields do not create additional repository findings.
    """
    declarations: list[IntegrationDeclaration] = []
    # A source-defined type is not the library endpoint, even if its package
    # and simple name reproduce a Spring canonical name. Never reinterpret
    # a local declaration as an external dependency based on spelling alone.
    source_types = (set(index.declared_type_names) |
                    {java_type.qualified_name for java_type in index.types})
    for java_type in index.types:
        if java_type.kind == 'interface':
            if java_type.feign:
                declarations.append(IntegrationDeclaration(
                    'OpenFeign', 'HTTP', java_type.qualified_name,
                    java_type.source_path,
                    java_type.feign_line if java_type.feign_line is not None else java_type.line,
                    type_name=java_type.qualified_name))
            if (JPA_REPOSITORY in java_type.extends and
                    JPA_REPOSITORY not in source_types):
                declarations.append(IntegrationDeclaration(
                    'Spring Data JPA', 'database', java_type.qualified_name,
                    java_type.source_path, java_type.line,
                    type_name=java_type.qualified_name))
        for field in java_type.fields:
            supported = (CLIENT_FIELDS.get(field.type_name)
                         if field.type_name not in source_types else None)
            if supported is not None:
                mechanism, category = supported
                declarations.append(IntegrationDeclaration(
                    mechanism, category, java_type.qualified_name,
                    field.source_path,
                    field.name_line if field.name_line is not None else field.line,
                    field.name, field.type_name))
    ordered = sorted(declarations, key=lambda d: (
        d.source_path, d.line, d.declaring_type, d.field_name or '', d.mechanism))
    # Identity belongs to the declaration, not to the number of fields that
    # refer to it or repeated entries in a supplied source index. Prefer the
    # first source citation deterministically if duplicate identities occur.
    unique: dict[tuple[str, str, str | None], IntegrationDeclaration] = {}
    for declaration in ordered:
        unique.setdefault(declaration.identity, declaration)
    return tuple(unique.values())


def extract_declarations(source: str, source_path: str) -> tuple[IntegrationDeclaration, ...]:
    """Extract supported declarations from one Java compilation unit."""
    return declarations_from_index(index_source(source, source_path))


def discover_declarations(module: Module) -> tuple[IntegrationDeclaration, ...]:
    """Read only the module's production Java source, preserving source order."""
    return declarations_from_index(index_module(module))
