from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, func
from model.database import Base

class Merchant(Base):
    __tablename__ = "merchant"
    
    code_merchant: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)
    merchant_logo_url: Mapped[str] = mapped_column(String, nullable=True)
    payment_link_khr: Mapped[str] = mapped_column(String, nullable=False)
    payment_link_usd: Mapped[str] = mapped_column(String, nullable=False)
    telegram_chat_id: Mapped[str] = mapped_column(String, nullable=True, default="")
    webhook_url: Mapped[str] = mapped_column(String, nullable=True, default="")
    status: Mapped[str] = mapped_column(String, default="ACTIVE")
    
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
