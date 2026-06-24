from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from home_decision_ai.db.base import Base


class Region(Base):
    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    priority: Mapped[int] = mapped_column(Integer, default=99)
    commute_notes: Mapped[str | None] = mapped_column(Text)

    complexes: Mapped[list[ApartmentComplex]] = relationship(back_populates="region")


class ApartmentComplex(Base):
    __tablename__ = "apartment_complexes"

    id: Mapped[int] = mapped_column(primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"), index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    brand: Mapped[str | None] = mapped_column(String(120))
    built_year: Mapped[int | None] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    region: Mapped[Region] = relationship(back_populates="complexes")
    observations: Mapped[list[MarketObservation]] = relationship(back_populates="complex")


class MarketObservation(Base):
    __tablename__ = "market_observations"

    id: Mapped[int] = mapped_column(primary_key=True)
    complex_id: Mapped[int] = mapped_column(ForeignKey("apartment_complexes.id"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source: Mapped[str] = mapped_column(String(120))
    source_url: Mapped[str | None] = mapped_column(Text)
    area_m2: Mapped[float | None] = mapped_column(Float)
    transaction_price_krw: Mapped[int | None] = mapped_column(Integer)
    asking_price_krw: Mapped[int | None] = mapped_column(Integer)
    inventory_count: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    memo: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    complex: Mapped[ApartmentComplex] = relationship(back_populates="observations")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_type: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(200))
    body_markdown: Mapped[str] = mapped_column(Text)
    notion_page_id: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True,
    )
