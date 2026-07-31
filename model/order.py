from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, func
from model.database import Base

class OrderTracking(Base):
    __tablename__ = "order_tracking"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[str] = mapped_column(String, nullable=True)
    code_merchant: Mapped[str] = mapped_column(String, nullable=True)
    tran_id: Mapped[str] = mapped_column(String, nullable=True)
    amount: Mapped[str] = mapped_column(String, nullable=True)
    currency: Mapped[str] = mapped_column(String, nullable=True)
    merchant_name: Mapped[str] = mapped_column(String, default='KHQR MERCHANT')
    khqr_data: Mapped[str] = mapped_column(String, nullable=True)
    qr_base64: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default='PENDING')
    receipt_link: Mapped[str] = mapped_column(String, nullable=True)
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
