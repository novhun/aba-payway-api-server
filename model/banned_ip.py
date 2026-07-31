from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from model.database import Base

class BannedIp(Base):
    __tablename__ = "banned_ip"

    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String, unique=True, index=True, nullable=False)
    reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
