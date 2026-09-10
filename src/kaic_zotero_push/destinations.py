"""Explicit destination selection and consistent user-facing descriptions."""

from kaic_zotero_push.errors import CollectionError
from kaic_zotero_push.models import TargetLibrary
from kaic_zotero_push.zotero.models import Collection


def collection_path(collection: Collection, collections: list[Collection]) -> str:
    """Describe the parent chain, refusing a corrupt or incomplete hierarchy."""
    index = {item.key: item for item in collections}
    names = [collection.name]
    visited = {collection.key}
    parent = collection.parent_key
    while parent is not None:
        if parent in visited or parent not in index:
            raise CollectionError(detail="Collection hierarchy is incomplete or cyclic.")
        visited.add(parent)
        item = index[parent]
        names.append(item.name)
        parent = item.parent_key
    return " / ".join(reversed(names))


def resolve_collection(
    name: str | None,
    key: str | None,
    collections: list[Collection],
) -> Collection | None:
    """Resolve an exact name or explicitly selected key without guessing."""
    if name is None and key is None:
        return None
    matches = [
        item for item in collections if (item.key == key if key is not None else item.name == name)
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        if key is not None:
            raise CollectionError(detail=f"Collection key not found: {key}")
        return None
    candidates = "; ".join(
        f"{collection_path(item, collections)} [key={item.key}]" for item in matches
    )
    raise CollectionError(
        detail=f"Collection name is ambiguous: {candidates}. Select with --collection-key."
    )


def describe_target(target: TargetLibrary, resolved_key: str | None = None) -> str:
    """Use the same destination wording for preview, approval and receipts."""
    if target.user_id == 0:
        return "오프라인 검토 (등록 대상 미확정)"
    name = target.collection_path or target.collection_name
    key = resolved_key or target.collection_key
    if key is not None:
        description = f"개인 라이브러리 / {name or key} (컬렉션 키: {key})"
    elif target.create_collection:
        description = f"개인 라이브러리 / {name} (새 컬렉션 생성 예정)"
    else:
        description = "개인 라이브러리 루트 (컬렉션 없음)"
    if target.proposed_collection and resolved_key is None:
        description += " [제안된 컬렉션명; 승인 전]"
    return description
