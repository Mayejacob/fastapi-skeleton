"""Reusable async pagination + search utility for SQLAlchemy models."""

import math
from dataclasses import dataclass, field
from typing import Any, Generic, Optional, Sequence, Type, TypeVar

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute, RelationshipProperty

T = TypeVar("T")


@dataclass
class Pagination:
    total: int
    page: int
    per_page: int
    pages: int
    has_next: bool
    has_prev: bool
    next_page: Optional[int]
    prev_page: Optional[int]

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "page": self.page,
            "per_page": self.per_page,
            "pages": self.pages,
            "has_next": self.has_next,
            "has_prev": self.has_prev,
            "next_page": self.next_page,
            "prev_page": self.prev_page,
        }


@dataclass
class PaginatedResult(Generic[T]):
    data: list[T]
    pagination: Pagination

    def to_dict(self, serializer=None) -> dict:
        """
        Return a plain dict ready for send_success(data=...).

        serializer: optional callable applied to each item (e.g. a Pydantic
        model_validate). If omitted the raw ORM objects are returned as-is.
        """
        items = [serializer(item) for item in self.data] if serializer else self.data
        return {
            "data": items,
            **self.pagination.to_dict(),
        }


async def paginate(
    db: AsyncSession,
    model: Type[T],
    *,
    # ---- filtering --------------------------------------------------------
    filters: Optional[list] = None,
    # ---- search -----------------------------------------------------------
    search: Optional[str] = None,
    search_fields: Optional[list[InstrumentedAttribute]] = None,
    # ---- joins (needed when search_fields touch related tables) -----------
    joins: Optional[list[tuple]] = None,
    # ---- eager loading ----------------------------------------------------
    load: Optional[list] = None,
    # ---- sorting ----------------------------------------------------------
    order_by: Optional[Any] = None,
    # ---- pagination -------------------------------------------------------
    page: int = 1,
    per_page: int = 20,
) -> PaginatedResult[T]:
    """
    Generic paginated query.

    Parameters
    ----------
    db            : AsyncSession
    model         : SQLAlchemy ORM model class to query.
    filters       : List of SQLAlchemy WHERE conditions applied to every query.
                    Example: [Employee.company_id == cid, Employee.deleted_at.is_(None)]
    search        : Free-text search term (case-insensitive ILIKE).
    search_fields : Columns to match the search term against.
                    Can include columns from JOINed models.
                    Example: [Employee.first_name, Employee.last_name, User.email]
    joins         : Extra JOIN clauses required by search_fields that live on
                    related tables.  Each entry is either:
                      - A mapped class  →  INNER JOIN via relationship
                      - A 2-tuple       →  (MappedClass, onclause)
                      - A 3-tuple       →  (MappedClass, onclause, {"isouter": True})
                    Example: [(User, CompanyMember.user_id == User.id)]
    load          : SQLAlchemy loading options (selectinload / joinedload).
                    Example: [selectinload(CompanyMember.user)]
    order_by      : Column or list of columns for ORDER BY.
                    Defaults to model.created_at DESC when available.
    page          : 1-based page number.
    per_page      : Rows per page (1–200).

    Returns
    -------
    PaginatedResult with .data (list of ORM instances) and .pagination metadata.
    """
    page = max(1, page)
    per_page = max(1, min(per_page, 200))

    filters = filters or []

    # ---- base queries --------------------------------------------------------
    count_q: Select = select(func.count()).select_from(model)
    list_q: Select = select(model)

    # ---- joins ---------------------------------------------------------------
    if joins:
        for join_entry in joins:
            if isinstance(join_entry, (list, tuple)):
                target = join_entry[0]
                onclause = join_entry[1] if len(join_entry) > 1 else None
                opts = join_entry[2] if len(join_entry) > 2 else {}
                isouter = opts.get("isouter", False) if isinstance(opts, dict) else False
                count_q = count_q.join(target, onclause, isouter=isouter)
                list_q = list_q.join(target, onclause, isouter=isouter)
            else:
                # bare model — join via ORM relationship
                count_q = count_q.join(join_entry)
                list_q = list_q.join(join_entry)

    # ---- static filters ------------------------------------------------------
    if filters:
        count_q = count_q.where(*filters)
        list_q = list_q.where(*filters)

    # ---- search --------------------------------------------------------------
    if search and search_fields:
        like = f"%{search}%"
        search_clause = or_(*[col.ilike(like) for col in search_fields])
        count_q = count_q.where(search_clause)
        list_q = list_q.where(search_clause)

    # ---- total count ---------------------------------------------------------
    total: int = (await db.execute(count_q)).scalar() or 0

    # ---- ordering ------------------------------------------------------------
    if order_by is None:
        if hasattr(model, "created_at"):
            order_by = model.created_at.desc()

    if order_by is not None:
        if isinstance(order_by, (list, tuple)):
            list_q = list_q.order_by(*order_by)
        else:
            list_q = list_q.order_by(order_by)

    # ---- eager loading -------------------------------------------------------
    if load:
        for loader in load:
            list_q = list_q.options(loader)

    # ---- pagination ----------------------------------------------------------
    list_q = list_q.offset((page - 1) * per_page).limit(per_page)
    data: list[T] = list((await db.execute(list_q)).scalars().all())

    # ---- pagination metadata -------------------------------------------------
    pages = max(1, math.ceil(total / per_page)) if per_page else 1
    has_prev = page > 1
    has_next = page < pages

    pagination = Pagination(
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
        has_prev=has_prev,
        has_next=has_next,
        prev_page=page - 1 if has_prev else None,
        next_page=page + 1 if has_next else None,
    )

    return PaginatedResult(data=data, pagination=pagination)
