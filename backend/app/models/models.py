from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class Novel(Base):
    __tablename__ = "novels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    author = Column(String, nullable=True)
    cover_url = Column(String, nullable=True)
    source_url = Column(String, nullable=True, unique=True)
    genres = Column(String, nullable=True)
    status = Column(String, nullable=True, default="Ongoing")
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    chapters = relationship("Chapter", back_populates="novel", cascade="all, delete-orphan")
    glossaries = relationship("Glossary", back_populates="novel", cascade="all, delete-orphan")

class Chapter(Base):
    __tablename__ = "chapters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False)
    chapter_no = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    source_url = Column(String, nullable=True)
    raw_text = Column(Text, nullable=True)
    translated_text = Column(Text, nullable=True)
    status = Column(String, default="PENDING")  # PENDING, CRAWLING, TRANSLATING, COMPLETED, FAILED
    error_msg = Column(Text, nullable=True)
    token_count = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    novel = relationship("Novel", back_populates="chapters")

class Glossary(Base):
    __tablename__ = "glossaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=True)  # NULL means Global Glossary
    chinese_term = Column(String, nullable=False)
    vietnamese_term = Column(String, nullable=False)
    category = Column(String, default="NAME")  # NAME, PLACE, SECT, ITEM, OTHER
    notes = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)

    # Relationships
    novel = relationship("Novel", back_populates="glossaries")

class Setting(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True)
    value = Column(Text, nullable=False)

class TranslationCache(Base):
    __tablename__ = "translation_cache"

    key_hash = Column(String, primary_key=True) # MD5 hash of raw Chinese text
    raw_text = Column(Text, nullable=False)
    translated_text = Column(Text, nullable=False)

